"""
Register (or update) model metadata in DynamoDB.

Usage:
    python scripts/register_model.py \
        --table aaas-mri-dev-model-metadata \
        --bucket aaas-mri-dev-models-xxxx \
        --key models/brain_tumor_model.h5 \
        --version v1.0

Environment variables (loaded from .env):
    AWS_REGION, MODEL_TABLE, MODEL_BUCKET
"""

import os
import sys
import argparse
from datetime import datetime

import boto3
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))


def main():
    parser = argparse.ArgumentParser(description="Register model metadata in DynamoDB.")
    parser.add_argument("--table",   required=True,
                        help="DynamoDB table name (terraform output: dynamodb_table_name)")
    parser.add_argument("--bucket",  required=True,
                        help="S3 bucket name containing the model")
    parser.add_argument("--key",     default="models/brain_tumor_model.h5",
                        help="S3 object key of the model file")
    parser.add_argument("--name",    default="mri",
                        help="Logical model name used in API requests (e.g. 'mri')")
    parser.add_argument("--version", default=datetime.utcnow().strftime("%Y%m%d%H%M%S"),
                        help="Version string for the model")
    parser.add_argument("--region",  default=os.environ.get("AWS_REGION", "us-east-1"))
    args = parser.parse_args()

    ddb = boto3.resource("dynamodb", region_name=args.region)
    table = ddb.Table(args.table)

    item = {
        "model_name":   args.name,
        "version":      args.version,
        "storage_path": args.key,
        "bucket":       args.bucket,
        "registered_at": datetime.utcnow().isoformat(),
        "framework":    "tensorflow",
        "classes":      ["glioma", "meningioma", "notumor", "pituitary"],
        "input_shape":  [224, 224, 3],
        "image_size":   224,
        "status":       "active",
    }

    print(f"Registering model '{args.name}' v{args.version} in table '{args.table}'...")
    table.put_item(Item=item)
    print("Done.")
    print(f"  model_name:   {item['model_name']}")
    print(f"  version:      {item['version']}")
    print(f"  storage_path: {item['storage_path']}")
    print(f"  bucket:       {item['bucket']}")


if __name__ == "__main__":
    main()
