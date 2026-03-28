"""
Upload trained model to S3 and optionally register it in DynamoDB.

Usage:
    python scripts/upload_model.py

Environment variables (loaded from .env):
    AWS_REGION, MODEL_BUCKET (output from terraform)

Or pass explicitly:
    python scripts/upload_model.py --bucket <bucket> --key models/brain_tumor_model.pt
"""

import os
import sys
import argparse
import hashlib
from datetime import datetime

import boto3
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

BASE_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_PT   = os.path.join(BASE_DIR, "model", "brain_tumor_model.pt")
MODEL_ONNX = os.path.join(BASE_DIR, "model", "brain_tumor_model.onnx")


def md5_of_file(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def upload_file(s3_client, local_path: str, bucket: str, key: str) -> None:
    size_mb = os.path.getsize(local_path) / (1024 * 1024)
    print(f"  Uploading {os.path.basename(local_path)} ({size_mb:.1f} MB) → s3://{bucket}/{key}")
    s3_client.upload_file(
        Filename=local_path,
        Bucket=bucket,
        Key=key,
        ExtraArgs={"ServerSideEncryption": "aws:kms"},
    )
    print(f"  Done.")


def register_in_dynamodb(ddb_resource, table_name: str, model_name: str,
                          bucket: str, key: str, version: str, checksum: str) -> None:
    table = ddb_resource.Table(table_name)
    item = {
        "model_name":    model_name,
        "version":       version,
        "storage_path":  key,
        "bucket":        bucket,
        "checksum_md5":  checksum,
        "uploaded_at":   datetime.utcnow().isoformat(),
        "framework":     "pytorch",
        "classes":       ["glioma", "meningioma", "notumor", "pituitary"],
        "input_shape":   [3, 224, 224],
    }
    table.put_item(Item=item)
    print(f"  Registered in DynamoDB table '{table_name}': {model_name} v{version}")


def main():
    parser = argparse.ArgumentParser(description="Upload model to S3 and register in DynamoDB.")
    parser.add_argument("--bucket",  default=os.environ.get("MODEL_BUCKET", ""),
                        help="S3 bucket name (or set MODEL_BUCKET env var)")
    parser.add_argument("--key",     default="models/brain_tumor_model.pt",
                        help="S3 object key for the .pt model")
    parser.add_argument("--table",   default=os.environ.get("MODEL_TABLE", ""),
                        help="DynamoDB table name (or set MODEL_TABLE env var)")
    parser.add_argument("--version", default=datetime.utcnow().strftime("%Y%m%d%H%M%S"),
                        help="Model version string")
    parser.add_argument("--region",  default=os.environ.get("AWS_REGION", "us-east-1"))
    args = parser.parse_args()

    if not args.bucket:
        print("ERROR: --bucket is required (or set MODEL_BUCKET env var).")
        print("       Run 'terraform output model_bucket_name' to get the bucket name.")
        sys.exit(1)

    if not os.path.isfile(MODEL_PT):
        print(f"ERROR: Model file not found at {MODEL_PT}")
        print("       Run 'python model/train_model.py' first.")
        sys.exit(1)

    region = args.region
    s3  = boto3.client("s3", region_name=region)
    ddb = boto3.resource("dynamodb", region_name=region)

    print("=" * 60)
    print("Uploading Brain Tumor Model to S3")
    print("=" * 60)

    # Upload .pt model
    checksum = md5_of_file(MODEL_PT)
    print(f"\n[1/3] MD5: {checksum}")
    upload_file(s3, MODEL_PT, args.bucket, args.key)

    # Upload ONNX model if available
    if os.path.isfile(MODEL_ONNX):
        onnx_key = args.key.replace(".pt", ".onnx")
        print(f"\n[2/3] Uploading ONNX model...")
        upload_file(s3, MODEL_ONNX, args.bucket, onnx_key)
    else:
        print("\n[2/3] ONNX model not found — skipping.")

    # Register in DynamoDB
    if args.table:
        print(f"\n[3/3] Registering in DynamoDB...")
        register_in_dynamodb(ddb, args.table, "mri", args.bucket, args.key,
                             args.version, checksum)
    else:
        print("\n[3/3] --table not provided — skipping DynamoDB registration.")
        print("       Run scripts/register_model.py separately, or provide --table.")

    print("\nUpload complete.")
    print(f"  S3 URI: s3://{args.bucket}/{args.key}")


if __name__ == "__main__":
    main()
