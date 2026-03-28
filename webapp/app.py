"""
Flask Web Application — Brain Tumor MRI Classification AaaS Demo

Run:  python webapp/app.py
      (from the f:\\jyoti_thesis directory, with venv activated)
"""

import json
import os
import statistics
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_from_directory

# Load .env from the project root (one level up from this file)
load_dotenv(Path(__file__).parent.parent / ".env")

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB upload limit

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
API_URL = os.environ.get(
    "API_URL",
    "https://whaveg4pu8.execute-api.us-east-1.amazonaws.com/dev/predict",
)
DATASET_DIR = Path(__file__).parent.parent / "dataset" / "Testing"

# ---------------------------------------------------------------------------
# Tumor class metadata (used in templates + result enrichment)
# ---------------------------------------------------------------------------
CLASSES_INFO = {
    "glioma": {
        "label": "Glioma",
        "badge_color": "danger",
        "hex_color": "#dc3545",
        "severity": "High",
        "description": (
            "Gliomas originate from glial cells in the brain or spine. "
            "They account for ~33% of all brain tumors and include subtypes such as "
            "astrocytomas and glioblastomas. Treatment typically involves surgery, "
            "radiation therapy, and chemotherapy."
        ),
    },
    "meningioma": {
        "label": "Meningioma",
        "badge_color": "warning",
        "hex_color": "#ffc107",
        "severity": "Moderate",
        "description": (
            "Meningiomas arise from the meninges, the membranes surrounding the brain "
            "and spinal cord. Most are benign and slow-growing. They are the most common "
            "primary brain tumor, representing ~30% of all brain tumors."
        ),
    },
    "notumor": {
        "label": "No Tumor",
        "badge_color": "success",
        "hex_color": "#198754",
        "severity": "None",
        "description": (
            "No tumor detected in this MRI scan. The scan appears normal with no visible "
            "abnormalities. Regular monitoring and clinical follow-up are still recommended "
            "based on the patient's symptoms."
        ),
    },
    "pituitary": {
        "label": "Pituitary Tumor",
        "badge_color": "info",
        "hex_color": "#0dcaf0",
        "severity": "Moderate",
        "description": (
            "Pituitary tumors develop in the pituitary gland at the base of the brain. "
            "Most are benign adenomas that can affect hormone production. Treatment may "
            "include medication, surgery, or radiation. They account for ~15% of all brain tumors."
        ),
    },
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_sample_images(n_per_class: int = 3) -> dict:
    """Return up to n_per_class test image filenames per class."""
    samples = {}
    for cls in CLASSES_INFO:
        cls_dir = DATASET_DIR / cls
        if cls_dir.exists():
            files = sorted(cls_dir.glob("*.jpg"))[:n_per_class]
            samples[cls] = [f.name for f in files]
        else:
            samples[cls] = []
    return samples


def call_predict_api(image_bytes: bytes, filename: str) -> dict:
    """Forward an image to the Lambda inference API and return a result dict."""
    start = time.perf_counter()
    try:
        resp = requests.post(
            API_URL,
            files={"image": (filename, image_bytes, "image/jpeg")},
            data={"metadata": json.dumps({"model": "mri"})},
            timeout=60,
        )
        latency_ms = round((time.perf_counter() - start) * 1000)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "success": True,
                "classification": data.get("classification", "unknown"),
                "confidence": data.get("confidence", 0.0),
                "model": data.get("model", "mri"),
                "latency_ms": latency_ms,
                "status_code": resp.status_code,
            }
        return {
            "success": False,
            "error": f"API returned HTTP {resp.status_code}",
            "latency_ms": latency_ms,
            "status_code": resp.status_code,
        }
    except requests.exceptions.Timeout:
        latency_ms = round((time.perf_counter() - start) * 1000)
        return {"success": False, "error": "Request timed out (60 s)", "latency_ms": latency_ms}
    except Exception as exc:
        latency_ms = round((time.perf_counter() - start) * 1000)
        return {"success": False, "error": str(exc), "latency_ms": latency_ms}


def _percentile(sorted_data: list, p: float) -> float:
    n = len(sorted_data)
    if n == 0:
        return 0.0
    k = (n - 1) * p / 100
    f, c = int(k), min(int(k) + 1, n - 1)
    return sorted_data[f] + (sorted_data[c] - sorted_data[f]) * (k - f)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    samples = get_sample_images(3)
    return render_template("index.html", samples=samples, classes_info=CLASSES_INFO)


@app.route("/predict", methods=["POST"])
def predict():
    if "image" not in request.files:
        return jsonify({"success": False, "error": "No image field in request"}), 400
    file = request.files["image"]
    if not file.filename:
        return jsonify({"success": False, "error": "Empty filename"}), 400

    image_bytes = file.read()
    result = call_predict_api(image_bytes, file.filename)

    if result.get("success"):
        cls = result["classification"]
        result["class_info"] = CLASSES_INFO.get(cls, {})

    return jsonify(result)


@app.route("/sample-image/<cls>/<filename>")
def sample_image(cls, filename):
    """Serve a sample image from the testing dataset (read-only)."""
    if cls not in CLASSES_INFO:
        return "Not found", 404
    cls_dir = DATASET_DIR / cls
    return send_from_directory(str(cls_dir), filename)


@app.route("/benchmark")
def benchmark():
    return render_template("benchmark.html", api_url=API_URL)


@app.route("/api/benchmark", methods=["POST"])
def run_benchmark():
    """Run N sequential requests to the Lambda API and return latency metrics."""
    data = request.get_json() or {}
    n = max(1, min(int(data.get("requests", 20)), 50))  # cap at 50

    # Find a test image
    test_img_path = None
    for cls in CLASSES_INFO:
        candidate = DATASET_DIR / cls / "Te-gl_1.jpg"
        if candidate.exists():
            test_img_path = candidate
            break
        files = list((DATASET_DIR / cls).glob("*.jpg"))
        if files:
            test_img_path = files[0]
            break

    if test_img_path is None:
        return jsonify({"error": "No test images found in dataset/Testing"}), 500

    with open(test_img_path, "rb") as f:
        img_bytes = f.read()

    # Run requests sequentially (preserves cold-start ordering)
    results = []
    for i in range(n):
        r = call_predict_api(img_bytes, test_img_path.name)
        r["request_num"] = i + 1
        r["is_cold"] = i == 0
        results.append(r)

    # Compute statistics
    successful = [r for r in results if r.get("success")]
    latencies = [r["latency_ms"] for r in successful]
    warm = latencies[1:] if len(latencies) > 1 else latencies
    sorted_l = sorted(latencies)

    stats = {
        "total": n,
        "successful": len(successful),
        "errors": n - len(successful),
        "cold_start_ms": latencies[0] if latencies else 0,
        "warm_avg_ms": round(statistics.mean(warm)) if warm else 0,
        "warm_min_ms": round(min(warm)) if warm else 0,
        "warm_max_ms": round(max(warm)) if warm else 0,
        "p50_ms": round(_percentile(sorted_l, 50)),
        "p90_ms": round(_percentile(sorted_l, 90)),
        "p99_ms": round(_percentile(sorted_l, 99)),
        "throughput": round(len(successful) / (sum(latencies) / 1000), 2) if latencies else 0,
    }

    # Lambda cost estimate (3008 MB, us-east-1)
    if latencies:
        avg_dur_sec = statistics.mean(latencies) / 1000
        gb_sec = (3008 / 1024) * avg_dur_sec * n
        stats["estimated_cost_usd"] = round(gb_sec * 0.0000166667 + n * 0.0000002, 6)
    else:
        stats["estimated_cost_usd"] = 0.0

    return jsonify({"results": results, "stats": stats})


@app.route("/api/health")
def health():
    """Quick health probe — send one request and report latency."""
    test_img_path = DATASET_DIR / "glioma" / "Te-gl_1.jpg"
    if not test_img_path.exists():
        return jsonify({"status": "dataset_missing"}), 500
    with open(test_img_path, "rb") as f:
        img_bytes = f.read()
    result = call_predict_api(img_bytes, test_img_path.name)
    status = "ok" if result.get("success") else "error"
    return jsonify({"status": status, **result})


if __name__ == "__main__":
    app.run(debug=True, port=5000, host="0.0.0.0")
