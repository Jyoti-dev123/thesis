"""
Performance measurement script for the AaaS inference endpoint.

Measures:
  - Cold-start vs warm-start latency (Lambda)
  - Throughput (requests/sec)
  - P50 / P90 / P99 latency
  - Approximate execution cost

Usage:
    python scripts/measure_performance.py \
        --url https://<api-id>.execute-api.us-east-1.amazonaws.com/dev \
        --image dataset/Testing/glioma/<any_image>.jpg \
        --requests 20
"""

import os
import sys
import json
import argparse
import time
import statistics
import concurrent.futures
from pathlib import Path

import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Approximate Lambda pricing (us-east-1, arm64, 3008 MB)
LAMBDA_PRICE_PER_GB_SEC   = 0.0000166667   # USD per GB-second
LAMBDA_PRICE_PER_REQUEST  = 0.0000002      # USD per request


def send_request(url: str, image_path: str, timeout: int = 120) -> dict:
    with open(image_path, "rb") as f:
        img_bytes = f.read()

    start = time.perf_counter()
    try:
        response = requests.post(
            f"{url.rstrip('/')}/predict",
            files={"image": (os.path.basename(image_path), img_bytes, "image/jpeg")},
            data={"metadata": json.dumps({"model": "mri"})},
            timeout=timeout,
        )
        response.raise_for_status()
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {"latency_ms": elapsed_ms, "status": response.status_code, "error": None}
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - start) * 1000
        return {"latency_ms": elapsed_ms, "status": 0, "error": str(exc)}


def percentile(data, p):
    """Compute the p-th percentile of a sorted list."""
    s = sorted(data)
    k = (len(s) - 1) * p / 100
    f, c = int(k), min(int(k) + 1, len(s) - 1)
    return s[f] + (s[c] - s[f]) * (k - f)


def estimate_lambda_cost(num_requests: int, avg_duration_ms: float,
                          memory_mb: int = 3008) -> float:
    """Estimate Lambda cost for the given workload."""
    duration_sec = avg_duration_ms / 1000
    gb_seconds = (memory_mb / 1024) * duration_sec * num_requests
    compute_cost = gb_seconds * LAMBDA_PRICE_PER_GB_SEC
    request_cost = num_requests * LAMBDA_PRICE_PER_REQUEST
    return compute_cost + request_cost


def main():
    parser = argparse.ArgumentParser(description="Measure AaaS API performance.")
    parser.add_argument("--url",          required=True,
                        help="API base URL")
    parser.add_argument("--image",        default="",
                        help="Path to test image (defaults to first glioma test image)")
    parser.add_argument("--requests",     type=int, default=20,
                        help="Total number of requests to send")
    parser.add_argument("--concurrency",  type=int, default=1,
                        help="Number of concurrent requests")
    parser.add_argument("--timeout",      type=int, default=120,
                        help="Request timeout in seconds")
    args = parser.parse_args()

    # Resolve test image
    image_path = args.image
    if not image_path:
        glioma_dir = os.path.join(BASE_DIR, "dataset", "Testing", "glioma")
        imgs = list(Path(glioma_dir).glob("*.jpg"))
        if not imgs:
            print("ERROR: No test images found. Provide --image.")
            sys.exit(1)
        image_path = str(imgs[0])

    if not os.path.isfile(image_path):
        print(f"ERROR: Image not found: {image_path}")
        sys.exit(1)

    print("=" * 60)
    print("Performance Measurement — AaaS Inference Endpoint")
    print(f"URL:         {args.url}/predict")
    print(f"Image:       {os.path.basename(image_path)}")
    print(f"Requests:    {args.requests}")
    print(f"Concurrency: {args.concurrency}")
    print("=" * 60)

    latencies = []
    errors = 0

    print(f"\nSending {args.requests} requests (concurrency={args.concurrency})...")

    if args.concurrency == 1:
        # Sequential: first request is cold start, rest are warm
        for i in range(args.requests):
            label = "cold" if i == 0 else "warm"
            r = send_request(args.url, image_path, args.timeout)
            if r["error"]:
                print(f"  [{i+1:3d}] ERROR ({r['latency_ms']:.0f}ms): {r['error']}")
                errors += 1
            else:
                print(f"  [{i+1:3d}] {label:<5} {r['latency_ms']:7.0f} ms  HTTP {r['status']}")
                latencies.append(r["latency_ms"])
    else:
        with concurrent.futures.ThreadPoolExecutor(max_workers=args.concurrency) as executor:
            futures = [executor.submit(send_request, args.url, image_path, args.timeout)
                       for _ in range(args.requests)]
            for i, fut in enumerate(concurrent.futures.as_completed(futures)):
                r = fut.result()
                if r["error"]:
                    print(f"  [{i+1:3d}] ERROR ({r['latency_ms']:.0f}ms): {r['error']}")
                    errors += 1
                else:
                    print(f"  [{i+1:3d}] {r['latency_ms']:7.0f} ms  HTTP {r['status']}")
                    latencies.append(r["latency_ms"])

    if not latencies:
        print("\nNo successful requests — cannot compute statistics.")
        sys.exit(1)

    # Statistics
    total_time_s = sum(latencies) / 1000
    throughput = len(latencies) / total_time_s if total_time_s > 0 else 0
    cold_latency = latencies[0] if latencies else 0
    warm_latencies = latencies[1:] if len(latencies) > 1 else latencies

    print("\n" + "=" * 60)
    print("Results Summary")
    print("=" * 60)
    print(f"  Successful requests:  {len(latencies)}/{args.requests}")
    print(f"  Errors:               {errors}")
    print(f"  Cold-start latency:   {cold_latency:.0f} ms")
    if warm_latencies:
        print(f"  Warm avg latency:     {statistics.mean(warm_latencies):.0f} ms")
        print(f"  Warm min latency:     {min(warm_latencies):.0f} ms")
        print(f"  Warm max latency:     {max(warm_latencies):.0f} ms")
        print(f"  P50 latency:          {percentile(warm_latencies, 50):.0f} ms")
        print(f"  P90 latency:          {percentile(warm_latencies, 90):.0f} ms")
        print(f"  P99 latency:          {percentile(warm_latencies, 99):.0f} ms")
    print(f"  Throughput:           {throughput:.2f} req/s")

    # Cost estimate (Lambda)
    if warm_latencies:
        avg_ms = statistics.mean(latencies)
        cost_usd = estimate_lambda_cost(len(latencies), avg_ms)
        print(f"\n  Estimated Lambda cost (3008 MB): ${cost_usd:.6f} USD")
        cost_per_1k = estimate_lambda_cost(1000, avg_ms)
        print(f"  Estimated cost per 1000 requests: ${cost_per_1k:.4f} USD")

    print("=" * 60)


if __name__ == "__main__":
    main()
