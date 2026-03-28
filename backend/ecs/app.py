"""
Flask REST API for Brain Tumor MRI Classification (ECS/Fargate deployment).

Endpoint: POST /predict
  - multipart/form-data:
      metadata: JSON string {"model": "mri"}
      image:    binary JPG/PNG file

Response: {"classification": "<class_name>", "confidence": <float>, "model": "<name>"}
"""

import os
import io
import json
import logging
import threading

import boto3
import torch
import torch.nn as nn
from torchvision import transforms
from flask import Flask, request, jsonify
from PIL import Image

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# -------------------------------------------------------------------
# Configuration from environment (set by Terraform / ECS task def)
# -------------------------------------------------------------------
S3_BUCKET   = os.environ["MODEL_BUCKET"]
DEFAULT_KEY = os.environ.get("MODEL_KEY", "models/brain_tumor_model.pt")
REGION      = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
MODEL_TABLE = os.environ.get("MODEL_TABLE", "model-metadata")
PORT        = int(os.environ.get("PORT", "8080"))

CLASSES     = ["glioma", "meningioma", "notumor", "pituitary"]
LOCAL_MODEL = "/tmp/brain_tumor_model.pt"

# ECS tasks can have a GPU, but CPU is fine for inference throughput here
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")
logger.info("Inference device: %s", DEVICE)

VAL_TRANSFORMS = transforms.Compose([
    transforms.Resize((224, 224)),
    transforms.CenterCrop(224),
    transforms.ToTensor(),
    transforms.Normalize(mean=[0.485, 0.456, 0.406],
                         std=[0.229, 0.224, 0.225]),
])

_model = None
_model_lock = threading.Lock()


# -------------------------------------------------------------------
# Model loading
# -------------------------------------------------------------------

def _get_model_key(model_name: str) -> str:
    try:
        ddb = boto3.resource("dynamodb", region_name=REGION)
        table = ddb.Table(MODEL_TABLE)
        response = table.get_item(Key={"model_name": model_name})
        item = response.get("Item")
        if item:
            return item["storage_path"]
    except Exception as e:
        logger.warning("DynamoDB lookup failed: %s. Using default key.", e)
    return DEFAULT_KEY


def _load_model(model_name: str = "mri") -> nn.Module:
    global _model
    with _model_lock:
        if _model is None:
            logger.info("Loading model from S3 (model_name=%s)...", model_name)
            s3_key = _get_model_key(model_name)
            s3 = boto3.client("s3", region_name=REGION)
            s3.download_file(S3_BUCKET, s3_key, LOCAL_MODEL)
            _model = torch.load(LOCAL_MODEL, map_location=DEVICE)
            _model.eval()
            logger.info("Model loaded successfully (device=%s).", DEVICE)
    return _model


def _preprocess(image_bytes: bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = VAL_TRANSFORMS(img)      # (3, 224, 224)
    return tensor.unsqueeze(0)        # (1, 3, 224, 224)


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/predict", methods=["POST"])
def predict():
    if "image" not in request.files:
        return jsonify({"error": "Missing 'image' field in multipart body."}), 400

    model_name = "mri"
    if "metadata" in request.form:
        try:
            meta = json.loads(request.form["metadata"])
            model_name = meta.get("model", "mri")
        except (json.JSONDecodeError, TypeError):
            pass

    image_bytes = request.files["image"].read()
    if not image_bytes:
        return jsonify({"error": "Empty image file."}), 400

    try:
        model = _load_model(model_name)
        input_tensor = _preprocess(image_bytes).to(DEVICE)

        with torch.no_grad():
            logits = model(input_tensor)              # (1, 4)
            probs  = torch.softmax(logits, dim=1)[0]  # (4,)

        class_idx  = int(probs.argmax().item())
        confidence = float(probs[class_idx].item())
        class_name = CLASSES[class_idx]

        logger.info("Prediction: %s (%.4f)", class_name, confidence)
        return jsonify({
            "classification": class_name,
            "confidence":     round(confidence, 4),
            "model":          model_name,
        }), 200

    except ValueError as exc:
        logger.warning("Validation error: %s", exc)
        return jsonify({"error": str(exc)}), 400
    except Exception:
        logger.exception("Inference error")
        return jsonify({"error": "Internal server error."}), 500


# -------------------------------------------------------------------
# Startup
# -------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Pre-loading model at startup...")
    _load_model()
    app.run(host="0.0.0.0", port=PORT)


_model = None
_model_lock = threading.Lock()


# -------------------------------------------------------------------
# Model loading
# -------------------------------------------------------------------

def _get_model_key(model_name: str) -> str:
    try:
        ddb = boto3.resource("dynamodb", region_name=REGION)
        table = ddb.Table(MODEL_TABLE)
        response = table.get_item(Key={"model_name": model_name})
        item = response.get("Item")
        if item:
            return item["storage_path"]
    except Exception as e:
        logger.warning("DynamoDB lookup failed: %s. Using default key.", e)
    return DEFAULT_KEY


def _load_model(model_name: str = "mri") -> tf.keras.Model:
    global _model
    with _model_lock:
        if _model is None:
            logger.info("Loading model from S3 (model_name=%s)...", model_name)
            s3_key = _get_model_key(model_name)
            s3 = boto3.client("s3", region_name=REGION)
            s3.download_file(S3_BUCKET, s3_key, LOCAL_MODEL)
            _model = tf.keras.models.load_model(LOCAL_MODEL)
            logger.info("Model loaded successfully.")
    return _model


def _preprocess(image_bytes: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = img.resize(IMAGE_SIZE, Image.LANCZOS)
    arr = np.array(img, dtype=np.float32) / 255.0
    return np.expand_dims(arr, axis=0)


# -------------------------------------------------------------------
# Routes
# -------------------------------------------------------------------

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "healthy"}), 200


@app.route("/predict", methods=["POST"])
def predict():
    # Validate multipart request
    if "image" not in request.files:
        return jsonify({"error": "Missing 'image' field in multipart body."}), 400

    # Parse metadata
    model_name = "mri"
    if "metadata" in request.form:
        try:
            meta = json.loads(request.form["metadata"])
            model_name = meta.get("model", "mri")
        except (json.JSONDecodeError, TypeError):
            pass

    image_file = request.files["image"]
    image_bytes = image_file.read()
    if not image_bytes:
        return jsonify({"error": "Empty image file."}), 400

    try:
        model = _load_model(model_name)
        input_array = _preprocess(image_bytes)
        predictions = model.predict(input_array)
        class_idx = int(np.argmax(predictions[0]))
        confidence = float(predictions[0][class_idx])
        class_name = CLASSES[class_idx]

        logger.info("Prediction: %s (%.4f)", class_name, confidence)
        return jsonify({
            "classification": class_name,
            "confidence": round(confidence, 4),
            "model": model_name,
        }), 200

    except ValueError as exc:
        logger.warning("Validation error: %s", exc)
        return jsonify({"error": str(exc)}), 400
    except Exception:
        logger.exception("Inference error")
        return jsonify({"error": "Internal server error."}), 500


# -------------------------------------------------------------------
# Startup
# -------------------------------------------------------------------

if __name__ == "__main__":
    # Pre-load the model on startup
    logger.info("Pre-loading model at startup...")
    _load_model()
    app.run(host="0.0.0.0", port=PORT)
