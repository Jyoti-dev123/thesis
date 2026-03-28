"""
Functional test script for the AaaS /predict endpoint.

Sends test MRI images from the Testing/ dataset to the deployed API
and verifies classification accuracy.

Usage:
    python scripts/test_api.py --url https://<api-id>.execute-api.us-east-1.amazonaws.com/dev

Optional:
    --samples   Number of images to test per class (default: 5)
    --timeout   Request timeout in seconds (default: 60)
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


def main():
    parser = argparse.ArgumentParser(description="Functional test for the /predict endpoint.")
    parser.add_argument("--url",     required=True,
                        help="Base API URL (e.g. https://xxx.execute-api.us-east-1.amazonaws.com/dev)")
    parser.add_argument("--samples", type=int, default=5,
                        help="Number of test images per class")
    parser.add_argument("--timeout", type=int, default=60,
                        help="HTTP request timeout in seconds")
    args = parser.parse_args()

    print("=" * 60)
    print("Functional API Test — Brain Tumor MRI Classification")
    print(f"Endpoint: {args.url}/predict")
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

    return 0 if overall_acc >= 70 else 1


if __name__ == "__main__":
    sys.exit(main())
