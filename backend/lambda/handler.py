"""
AWS Lambda handler for Brain Tumor MRI Classification inference.

Deployment: Container image via Amazon ECR → Lambda.
- On cold start: downloads the model from S3 into /tmp and caches it.
- Accepts multipart/form-data POST via API Gateway (proxy integration).
- Returns: {"classification": "<class_name>"}
"""

import json
import os
import io
import base64
import logging

import boto3
import torch
import torch.nn as nn
from torchvision import transforms
from PIL import Image

logger = logging.getLogger()
logger.setLevel(logging.INFO)

# -------------------------------------------------------------------
# Configuration from environment (set by Terraform)
# -------------------------------------------------------------------
S3_BUCKET   = os.environ["MODEL_BUCKET"]
MODEL_KEY   = os.environ.get("MODEL_KEY", "models/brain_tumor_model.pt")
REGION      = os.environ.get("APP_REGION", os.environ.get("AWS_REGION", "us-east-1"))
MODEL_TABLE = os.environ.get("MODEL_TABLE", "model-metadata")

CLASSES     = ["glioma", "meningioma", "notumor", "pituitary"]
LOCAL_MODEL = "/tmp/brain_tumor_model.pt"

# ImageNet normalisation (must match training)
VAL_TRANSFORMS = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

# Lambda runs on CPU; force that explicitly
DEVICE = torch.device("cpu")

# -------------------------------------------------------------------
# Module-level model cache (persists across warm invocations)
# -------------------------------------------------------------------
_model = None


def _get_model_key_from_dynamo(model_name: str) -> str:
    """Look up the S3 storage path for a model name from DynamoDB."""
    ddb = boto3.resource("dynamodb", region_name=REGION)
    table = ddb.Table(MODEL_TABLE)
    response = table.get_item(Key={"model_name": model_name})
    item = response.get("Item")
    if item:
        return item["storage_path"]
    return MODEL_KEY


def _load_model(model_name: str = "mri") -> nn.Module:
    """Download the model from S3 (if not cached) and load into memory."""
    global _model
    if _model is not None:
        return _model

    logger.info("Cold start: loading model from S3...")
    s3_key = _get_model_key_from_dynamo(model_name)

    s3 = boto3.client("s3", region_name=REGION)
    s3.download_file(S3_BUCKET, s3_key, LOCAL_MODEL)
    logger.info("Model downloaded to %s", LOCAL_MODEL)

    # torch.save(model, path) was used during training — load the full object
    _model = torch.load(LOCAL_MODEL, map_location=DEVICE, weights_only=False)
    _model.eval()
    logger.info("Model loaded successfully.")
    return _model


def _parse_multipart(event: dict):
    """
    Parse multipart/form-data from API Gateway proxy event.
    Returns (model_name, image_bytes).
    """
    import cgi

    body = event.get("body", "")
    is_b64 = event.get("isBase64Encoded", False)
    if is_b64:
        body_bytes = base64.b64decode(body)
    else:
        body_bytes = body.encode("utf-8") if isinstance(body, str) else body

    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    content_type = headers.get("content-type", "")

    fp = io.BytesIO(body_bytes)
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": content_type,
        "CONTENT_LENGTH": str(len(body_bytes)),
    }
    form = cgi.FieldStorage(fp=fp, environ=environ, keep_blank_values=True)

    model_name = "mri"
    if "metadata" in form:
        try:
            meta = json.loads(form["metadata"].value)
            model_name = meta.get("model", "mri")
        except (json.JSONDecodeError, AttributeError):
            pass

    image_bytes = None
    if "image" in form:
        image_bytes = form["image"].file.read()

    return model_name, image_bytes


def _preprocess(image_bytes: bytes):
    """Decode and normalise the image into a PyTorch tensor."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = VAL_TRANSFORMS(img)       # (3, 224, 224)
    return tensor.unsqueeze(0)         # (1, 3, 224, 224)


def _build_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def handler(event, context):
    """Lambda entry point."""
    logger.info("Event: %s", json.dumps(event))

    try:
        model_name, image_bytes = _parse_multipart(event)

        if image_bytes is None:
            return _build_response(400, {"error": "Missing 'image' field in multipart body."})

        model = _load_model(model_name)
        input_tensor = _preprocess(image_bytes).to(DEVICE)

        with torch.no_grad():
            logits = model(input_tensor)               # (1, 4)
            probs  = torch.softmax(logits, dim=1)[0]   # (4,)

        class_idx  = int(probs.argmax().item())
        confidence = float(probs[class_idx].item())
        class_name = CLASSES[class_idx]

        logger.info("Prediction: %s (confidence: %.4f)", class_name, confidence)
        return _build_response(200, {
            "classification": class_name,
            "confidence":     round(confidence, 4),
            "model":          model_name,
        })

    except ValueError as exc:
        logger.warning("Validation error: %s", exc)
        return _build_response(400, {"error": str(exc)})
    except Exception:
        logger.exception("Inference error")
        return _build_response(500, {"error": "Internal server error."})


# -------------------------------------------------------------------
# Module-level model cache (persists across warm invocations)
# -------------------------------------------------------------------
_model = None


def _get_model_key_from_dynamo(model_name: str) -> str:
    """Look up the S3 storage path for a model name from DynamoDB."""
    ddb = boto3.resource("dynamodb", region_name=REGION)
    table = ddb.Table(MODEL_TABLE)
    response = table.get_item(Key={"model_name": model_name})
    item = response.get("Item")
    if item:
        return item["storage_path"]
    return MODEL_KEY


def _load_model(model_name: str = "mri") -> tf.keras.Model:
    """Download model from S3 (if not cached) and load into memory."""
    global _model
    if _model is not None:
        return _model

    logger.info("Cold start: loading model from S3...")
    s3_key = _get_model_key_from_dynamo(model_name)

    s3 = boto3.client("s3", region_name=REGION)
    s3.download_file(S3_BUCKET, s3_key, LOCAL_MODEL)
    logger.info("Model downloaded to %s", LOCAL_MODEL)

    _model = tf.keras.models.load_model(LOCAL_MODEL)
    logger.info("Model loaded successfully.")
    return _model


def _parse_multipart(event: dict):
    """
    Parse multipart/form-data from API Gateway proxy event.
    Returns (model_name, image_bytes).
    """
    import cgi

    # API Gateway can base64-encode the binary body
    body = event.get("body", "")
    is_b64 = event.get("isBase64Encoded", False)
    if is_b64:
        body_bytes = base64.b64decode(body)
    else:
        body_bytes = body.encode("utf-8") if isinstance(body, str) else body

    # Extract content-type header (case-insensitive)
    headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}
    content_type = headers.get("content-type", "")

    # Parse multipart using cgi module
    fp = io.BytesIO(body_bytes)
    environ = {
        "REQUEST_METHOD": "POST",
        "CONTENT_TYPE": content_type,
        "CONTENT_LENGTH": str(len(body_bytes)),
    }
    form = cgi.FieldStorage(fp=fp, environ=environ, keep_blank_values=True)

    # Extract model name from JSON metadata field
    model_name = "mri"
    if "metadata" in form:
        try:
            meta = json.loads(form["metadata"].value)
            model_name = meta.get("model", "mri")
        except (json.JSONDecodeError, AttributeError):
            pass

    # Extract image bytes
    image_bytes = None
    if "image" in form:
        image_bytes = form["image"].file.read()

    return model_name, image_bytes


def _preprocess(image_bytes: bytes) -> np.ndarray:
    """Decode, resize and normalize the image."""
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize(IMAGE_SIZE, Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)  # shape: (1, 224, 224, 3)


def _build_response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body),
    }


def handler(event, context):
    """Lambda entry point."""
    logger.info("Event: %s", json.dumps(event))

    try:
        model_name, image_bytes = _parse_multipart(event)

        if image_bytes is None:
            return _build_response(400, {"error": "Missing 'image' field in multipart body."})

        model = _load_model(model_name)
        input_array = _preprocess(image_bytes)

        predictions = model.predict(input_array)
        class_idx = int(np.argmax(predictions[0]))
        confidence = float(predictions[0][class_idx])
        class_name = CLASSES[class_idx]

        logger.info("Prediction: %s (confidence: %.4f)", class_name, confidence)
        return _build_response(200, {
            "classification": class_name,
            "confidence": round(confidence, 4),
            "model": model_name,
        })

    except ValueError as exc:
        logger.warning("Validation error: %s", exc)
        return _build_response(400, {"error": str(exc)})
    except Exception as exc:
        logger.exception("Inference error")
        return _build_response(500, {"error": "Internal server error."})
