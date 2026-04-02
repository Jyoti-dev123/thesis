"""
AWS Lambda handler for Brain Tumor MRI Classification.

Deployment: Container image via Amazon ECR → Lambda.
- On cold start: downloads the latest model version from S3 (via DynamoDB lookup) and caches it.
- Accepts multipart/form-data POST via API Gateway (proxy integration).

Routes handled:
  POST   /predict                          - run inference
  GET    /health                           - health check
  GET    /models                           - list all model versions
  GET    /models/{model_name}              - get latest version info
  POST   /models                           - register a new model version
  DELETE /models/{model_name}/{version}    - remove a model version entry
"""

import json
import os
import io
import base64
import logging
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
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
DEFAULT_KEY = os.environ.get("MODEL_KEY", "models/brain_tumor_model.pt")
REGION      = os.environ.get("APP_REGION", os.environ.get("AWS_REGION", "us-east-1"))
MODEL_TABLE = os.environ.get("MODEL_TABLE", "model-metadata")

CLASSES     = ["glioma", "meningioma", "notumor", "pituitary"]
LOCAL_MODEL = "/tmp/brain_tumor_model.pt"

VAL_TRANSFORMS = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

DEVICE = torch.device("cpu")

# -------------------------------------------------------------------
# Module-level model cache (persists across warm invocations)
# -------------------------------------------------------------------
_model = None


def _ddb_table():
    return boto3.resource("dynamodb", region_name=REGION).Table(MODEL_TABLE)


def _get_latest_model_item(model_name: str) -> dict | None:
    """Return the DynamoDB item for the latest version of model_name."""
    try:
        table = _ddb_table()
        response = table.query(
            KeyConditionExpression=Key("model_name").eq(model_name),
            ScanIndexForward=False,   # descending — most recent version first
            Limit=1,
        )
        items = response.get("Items", [])
        return items[0] if items else None
    except Exception as exc:
        logger.warning("DynamoDB query failed: %s", exc)
        return None


def _load_model(model_name: str = "mri") -> nn.Module:
    """Download the latest model from S3 (if not cached) and load into memory."""
    global _model
    if _model is not None:
        return _model

    logger.info("Cold start: loading model from S3...")
    item = _get_latest_model_item(model_name)
    s3_key = item["storage_path"] if item else DEFAULT_KEY

    s3 = boto3.client("s3", region_name=REGION)
    s3.download_file(S3_BUCKET, s3_key, LOCAL_MODEL)
    logger.info("Model downloaded to %s (key=%s).", LOCAL_MODEL, s3_key)

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
    """Lambda entry point — routes to inference or model management handlers."""
    logger.info("Event: %s", json.dumps(event))

    http_method = event.get("requestContext", {}).get("http", {}).get("method", "").upper()
    raw_path    = event.get("requestContext", {}).get("http", {}).get("path", "")

    # ---- Health check ----
    if http_method == "GET" and raw_path == "/health":
        return _build_response(200, {"status": "healthy"})

    # ---- Model management routes ----
    if raw_path == "/models" and http_method == "GET":
        return _handle_list_models()

    if raw_path.startswith("/models/") and http_method == "GET":
        parts = raw_path.strip("/").split("/")
        if len(parts) == 2:
            return _handle_get_model(parts[1])

    if raw_path == "/models" and http_method == "POST":
        body = {}
        if event.get("body"):
            try:
                body = json.loads(event["body"])
            except json.JSONDecodeError:
                return _build_response(400, {"error": "Invalid JSON body."})
        return _handle_register_model(body)

    if raw_path.startswith("/models/") and http_method == "DELETE":
        parts = raw_path.strip("/").split("/")
        if len(parts) == 3:
            return _handle_delete_model(parts[1], parts[2])

    # ---- Inference ----
    if http_method == "POST" and raw_path == "/predict":
        return _handle_predict(event)

    return _build_response(404, {"error": "Route not found."})


# -------------------------------------------------------------------
# Inference handler
# -------------------------------------------------------------------

def _handle_predict(event: dict) -> dict:
    try:
        model_name, image_bytes = _parse_multipart(event)
        if image_bytes is None:
            return _build_response(400, {"error": "Missing 'image' field in multipart body."})

        model = _load_model(model_name)
        input_tensor = _preprocess(image_bytes).to(DEVICE)

        with torch.no_grad():
            logits = model(input_tensor)
            probs  = torch.softmax(logits, dim=1)[0]

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
# Model management handlers
# -------------------------------------------------------------------

def _handle_list_models() -> dict:
    try:
        table = _ddb_table()
        response = table.scan()
        items = response.get("Items", [])
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
        return _build_response(200, {"models": items})
    except Exception as exc:
        logger.exception("Failed to list models")
        return _build_response(500, {"error": str(exc)})


def _handle_get_model(model_name: str) -> dict:
    item = _get_latest_model_item(model_name)
    if item is None:
        return _build_response(404, {"error": f"Model '{model_name}' not found."})
    return _build_response(200, item)


def _handle_register_model(body: dict) -> dict:
    model_name   = body.get("model_name")
    storage_path = body.get("storage_path")
    if not model_name or not storage_path:
        return _build_response(400, {"error": "'model_name' and 'storage_path' are required."})

    version = body.get("version") or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    try:
        s3 = boto3.client("s3", region_name=REGION)
        s3.head_object(Bucket=S3_BUCKET, Key=storage_path)
    except Exception:
        return _build_response(400, {"error": f"S3 object '{storage_path}' not found in bucket '{S3_BUCKET}'."})

    item = {
        "model_name":    model_name,
        "version":       version,
        "storage_path":  storage_path,
        "registered_at": datetime.now(timezone.utc).isoformat(),
        "status":        "active",
    }
    if body.get("description"):
        item["description"] = body["description"]

    try:
        _ddb_table().put_item(Item=item)
        logger.info("Registered model '%s' version '%s'.", model_name, version)
        return _build_response(201, item)
    except Exception as exc:
        logger.exception("Failed to register model")
        return _build_response(500, {"error": str(exc)})


def _handle_delete_model(model_name: str, version: str) -> dict:
    try:
        table = _ddb_table()
        response = table.get_item(Key={"model_name": model_name, "version": version})
        if "Item" not in response:
            return _build_response(404, {"error": f"Model '{model_name}' version '{version}' not found."})
        table.delete_item(Key={"model_name": model_name, "version": version})
        logger.info("Deleted model '%s' version '%s'.", model_name, version)
        return _build_response(200, {"deleted": {"model_name": model_name, "version": version}})
    except Exception as exc:
        logger.exception("Failed to delete model")
        return _build_response(500, {"error": str(exc)})
