"""
Flask REST API for Brain Tumor MRI Classification (ECS/Fargate deployment).

Inference endpoint:
  POST /predict
    multipart/form-data:
      metadata: JSON string {"model": "mri"}
      image:    binary JPG/PNG file
    Response: {"classification": "<class_name>", "confidence": <float>, "model": "<name>"}

Model Management endpoints:
  GET  /models                          - list all registered models
  GET  /models/<model_name>             - get latest version info for a model
  POST /models                          - register a new model version
  DELETE /models/<model_name>/<version> - remove a model version entry
"""

import os
import io
import json
import logging
import threading
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Key
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
# DynamoDB helpers
# -------------------------------------------------------------------

def _ddb_table():
    ddb = boto3.resource("dynamodb", region_name=REGION)
    return ddb.Table(MODEL_TABLE)


def _get_latest_model_item(model_name: str) -> dict | None:
    """Return the DynamoDB item for the latest version of model_name, or None."""
    try:
        table = _ddb_table()
        response = table.query(
            KeyConditionExpression=Key("model_name").eq(model_name),
            ScanIndexForward=False,   # descending = most recent version first
            Limit=1,
        )
        items = response.get("Items", [])
        return items[0] if items else None
    except Exception as exc:
        logger.warning("DynamoDB query failed: %s", exc)
        return None


# -------------------------------------------------------------------
# Model loading
# -------------------------------------------------------------------

def _load_model(model_name: str = "mri") -> nn.Module:
    global _model
    with _model_lock:
        if _model is None:
            logger.info("Loading model from S3 (model_name=%s)...", model_name)
            item = _get_latest_model_item(model_name)
            s3_key = item["storage_path"] if item else DEFAULT_KEY
            s3 = boto3.client("s3", region_name=REGION)
            s3.download_file(S3_BUCKET, s3_key, LOCAL_MODEL)
            _model = torch.load(LOCAL_MODEL, map_location=DEVICE, weights_only=False)
            _model.eval()
            logger.info("Model loaded (key=%s, device=%s).", s3_key, DEVICE)
    return _model


def _preprocess(image_bytes: bytes):
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    tensor = VAL_TRANSFORMS(img)
    return tensor.unsqueeze(0)


# -------------------------------------------------------------------
# Routes — inference
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
            logits = model(input_tensor)
            probs  = torch.softmax(logits, dim=1)[0]

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
# Routes — model management (CRUD)
# -------------------------------------------------------------------

@app.route("/models", methods=["GET"])
def list_models():
    """Return all model entries registered in DynamoDB."""
    try:
        table = _ddb_table()
        response = table.scan()
        items = response.get("Items", [])
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
        return jsonify({"models": items}), 200
    except Exception as exc:
        logger.exception("Failed to list models")
        return jsonify({"error": str(exc)}), 500


@app.route("/models/<model_name>", methods=["GET"])
def get_model(model_name: str):
    """Return the latest version metadata for a given model."""
    item = _get_latest_model_item(model_name)
    if item is None:
        return jsonify({"error": f"Model '{model_name}' not found."}), 404
    return jsonify(item), 200


@app.route("/models", methods=["POST"])
def register_model():
    """
    Register a new model version.

    JSON body:
      {
        "model_name":   "mri",
        "version":      "20250401120000",   // optional; auto-generated if omitted
        "storage_path": "models/mri_v2.pt",
        "description":  "Improved accuracy"  // optional
      }
    """
    body = request.get_json(silent=True)
    if not body:
        return jsonify({"error": "JSON body required."}), 400

    model_name   = body.get("model_name")
    storage_path = body.get("storage_path")
    if not model_name or not storage_path:
        return jsonify({"error": "'model_name' and 'storage_path' are required."}), 400

    version = body.get("version") or datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")

    # Validate that the S3 object actually exists before registering
    try:
        s3 = boto3.client("s3", region_name=REGION)
        s3.head_object(Bucket=S3_BUCKET, Key=storage_path)
    except Exception:
        return jsonify({"error": f"S3 object '{storage_path}' not found in bucket '{S3_BUCKET}'."}), 400

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
        table = _ddb_table()
        table.put_item(Item=item)
        logger.info("Registered model '%s' version '%s'.", model_name, version)
        return jsonify(item), 201
    except Exception as exc:
        logger.exception("Failed to register model")
        return jsonify({"error": str(exc)}), 500


@app.route("/models/<model_name>/<version>", methods=["DELETE"])
def delete_model(model_name: str, version: str):
    """Remove a specific model version entry from DynamoDB."""
    try:
        table = _ddb_table()
        response = table.get_item(Key={"model_name": model_name, "version": version})
        if "Item" not in response:
            return jsonify({"error": f"Model '{model_name}' version '{version}' not found."}), 404

        table.delete_item(Key={"model_name": model_name, "version": version})
        logger.info("Deleted model '%s' version '%s'.", model_name, version)
        return jsonify({"deleted": {"model_name": model_name, "version": version}}), 200
    except Exception as exc:
        logger.exception("Failed to delete model")
        return jsonify({"error": str(exc)}), 500


# -------------------------------------------------------------------
# Startup
# -------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Pre-loading default model at startup...")
    _load_model()
    app.run(host="0.0.0.0", port=PORT)

