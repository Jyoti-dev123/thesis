"""
Functional test script for the AaaS API.

Tests both the /predict endpoint (classification accuracy) and the
model management endpoints (CRUD /models).

Usage:
    python scripts/test_api.py --url https://<api-id>.execute-api.us-east-1.amazonaws.com/dev

Optional:
    --samples   Number of images to test per class (default: 5)
    --timeout   Request timeout in seconds (default: 60)
    --skip-crud Skip model management CRUD tests
"""

import os
import sys
import json
import argparse
import time
from pathlib import Path

import requests

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEST_DIR  = os.path.join(BASE_DIR, "dataset", "Testing")
CLASSES   = ["glioma", "meningioma", "notumor", "pituitary"]


def send_predict(url: str, image_path: str, timeout: int = 60) -> dict:
    """Send a single image to the /predict endpoint and return the result."""
    with open(image_path, "rb") as f:
        image_bytes = f.read()

    start = time.perf_counter()
    response = requests.post(
        f"{url.rstrip('/')}/predict",
        files={"image": (os.path.basename(image_path), image_bytes, "image/jpeg")},
        data={"metadata": json.dumps({"model": "mri"})},
        timeout=timeout,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    response.raise_for_status()
    result = response.json()
    result["_latency_ms"] = round(elapsed_ms, 2)
    return result


def test_model_management(base_url: str, timeout: int = 30) -> bool:
    """
    Smoke-test the model management CRUD endpoints.
    Returns True if all tests pass.
    """
    url = base_url.rstrip("/")
    passed = 0
    failed = 0

    print("\n" + "=" * 60)
    print("Model Management CRUD Tests")
    print("=" * 60)

    # 1. GET /models — list (may be empty)
    try:
        r = requests.get(f"{url}/models", timeout=timeout)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"
        assert "models" in r.json(), "Response missing 'models' key"
        print("  PASS  GET  /models")
        passed += 1
    except Exception as e:
        print(f"  FAIL  GET  /models — {e}")
        failed += 1

    # 2. POST /models — register a test entry (points to the real model key)
    test_version = "00000000000000"  # fixed version for idempotent re-runs
    test_payload = {
        "model_name":   "mri",
        "version":      test_version,
        "storage_path": "models/brain_tumor_model.pt",
        "description":  "Test entry created by test_api.py",
    }
    try:
        r = requests.post(f"{url}/models", json=test_payload, timeout=timeout)
        assert r.status_code in (200, 201), f"Expected 201, got {r.status_code}: {r.text}"
        item = r.json()
        assert item.get("model_name") == "mri", "model_name mismatch"
        print("  PASS  POST /models")
        passed += 1
    except Exception as e:
        print(f"  FAIL  POST /models — {e}")
        failed += 1

    # 3. GET /models/mri — retrieve latest version
    try:
        r = requests.get(f"{url}/models/mri", timeout=timeout)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        item = r.json()
        assert item.get("model_name") == "mri", "model_name mismatch"
        assert "storage_path" in item, "Response missing 'storage_path'"
        print(f"  PASS  GET  /models/mri  (version={item.get('version')})")
        passed += 1
    except Exception as e:
        print(f"  FAIL  GET  /models/mri — {e}")
        failed += 1

    # 4. DELETE /models/mri/{test_version} — clean up the test entry
    try:
        r = requests.delete(f"{url}/models/mri/{test_version}", timeout=timeout)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        print(f"  PASS  DELETE /models/mri/{test_version}")
        passed += 1
    except Exception as e:
        print(f"  FAIL  DELETE /models/mri/{test_version} — {e}")
        failed += 1

    print(f"\nModel Management: {passed} passed, {failed} failed")
    return failed == 0


def main():
    parser = argparse.ArgumentParser(description="Functional test for the AaaS API.")
    parser.add_argument("--url",       required=True,
                        help="Base API URL (e.g. https://xxx.execute-api.us-east-1.amazonaws.com/dev)")
    parser.add_argument("--samples",   type=int, default=5,
                        help="Number of test images per class")
    parser.add_argument("--timeout",   type=int, default=60,
                        help="HTTP request timeout in seconds")
    parser.add_argument("--skip-crud", action="store_true",
                        help="Skip model management CRUD tests")
    args = parser.parse_args()

    print("=" * 60)
    print("Functional API Test — Brain Tumor MRI Classification")
    print(f"Endpoint: {args.url}/predict")
    print("=" * 60)

    # Run model management CRUD tests first
    crud_ok = True
    if not args.skip_crud:
        crud_ok = test_model_management(args.url, timeout=args.timeout)

    print("\n" + "=" * 60)
    print("Inference Tests — /predict")
    print("=" * 60)

    total = 0
    correct = 0
    results_by_class = {}

    for class_name in CLASSES:
        class_dir = os.path.join(TEST_DIR, class_name)
        if not os.path.isdir(class_dir):
            print(f"WARNING: Test directory not found: {class_dir}")
            continue

        images = sorted(Path(class_dir).glob("*.jpg"))[:args.samples]
        if not images:
            images = sorted(Path(class_dir).glob("*.jpeg"))[:args.samples]

        print(f"\nClass: {class_name} ({len(images)} images)")
        class_correct = 0

        for img_path in images:
            try:
                result = send_predict(args.url, str(img_path), args.timeout)
                predicted = result.get("classification", "")
                confidence = result.get("confidence", 0.0)
                latency = result.get("_latency_ms", 0)
                is_correct = predicted == class_name
                if is_correct:
                    class_correct += 1
                    correct += 1
                total += 1

                status = "✓" if is_correct else "✗"
                print(f"  {status} {img_path.name:<40} "
                      f"predicted={predicted:<15} conf={confidence:.3f} "
                      f"latency={latency:.0f}ms")

            except requests.exceptions.Timeout:
                print(f"  TIMEOUT: {img_path.name}")
                total += 1
            except Exception as e:
                print(f"  ERROR: {img_path.name}: {e}")
                total += 1

        class_acc = class_correct / len(images) * 100 if images else 0
        results_by_class[class_name] = {"correct": class_correct,
                                        "total": len(images),
                                        "accuracy": class_acc}
        print(f"  Class accuracy: {class_acc:.1f}% ({class_correct}/{len(images)})")

    print("\n" + "=" * 60)
    overall_acc = correct / total * 100 if total else 0
    print(f"Overall Accuracy: {overall_acc:.1f}% ({correct}/{total})")
    print("=" * 60)

    # Summary table
    print("\nPer-class Summary:")
    print(f"  {'Class':<15} {'Correct':>8} {'Total':>8} {'Accuracy':>10}")
    print(f"  {'-'*45}")
    for cls, stats in results_by_class.items():
        print(f"  {cls:<15} {stats['correct']:>8} {stats['total']:>8} {stats['accuracy']:>9.1f}%")

    return 0 if overall_acc >= 70 and crud_ok else 1


if __name__ == "__main__":
    sys.exit(main())
