# Cloud-Agnostic Analytics as a Service (AaaS) — Brain Tumor MRI Classification

> **Thesis**: Design and Implementation of a Cloud-Agnostic 'Analytics as a Service' (AaaS) Pattern for Medical Image Classification using Terraform

---

## Project Overview

This project implements a full AaaS pattern for classifying Brain Tumor MRI images into four categories:
- **glioma** · **meningioma** · **notumor** · **pituitary**

Three deployment architectures are provisioned and compared via Terraform on AWS:

| Architecture | Compute | Cold Start | Best For |
|---|---|---|---|
| **Serverless** | Lambda (container) | ~10–30 s | Sporadic, event-driven inference |
| **Container** | ECS / Fargate | None (always warm) | High-throughput, sustained load |
| **Managed** | Elastic Beanstalk | Minimal | Simplified deployment/scaling |

---

## Repository Structure

```
jyoti_thesis/
├── model/
│   ├── train_model.py       # CNN (MobileNetV2) training + ONNX export
│   ├── preprocess.py        # Dataset loading and image preprocessing
│   └── requirements.txt
│
├── backend/
│   ├── lambda/
│   │   ├── handler.py       # Lambda handler (multipart → TF inference)
│   │   ├── Dockerfile       # Lambda container image (ECR)
│   │   └── requirements.txt
│   └── ecs/
│       ├── app.py           # Flask REST API for ECS/Fargate
│       ├── Dockerfile       # Fargate container image (ECR)
│       └── requirements.txt
│
├── terraform/
│   ├── main.tf              # Root module — wires all sub-modules
│   ├── variables.tf
│   ├── outputs.tf
│   ├── terraform.tfvars
│   └── modules/
│       ├── security/        # KMS key + Secrets Manager
│       ├── s3/              # Model & image buckets (encrypted, versioned)
│       ├── dynamodb/        # Model metadata table
│       ├── ecr/             # Container image repositories
│       ├── iam/             # Lambda + ECS IAM roles & policies
│       ├── lambda/          # Lambda function (container image)
│       ├── api_gateway/     # HTTP API Gateway → Lambda
│       └── ecs/             # ECS cluster, Fargate service, ALB
│
├── scripts/
│   ├── upload_model.py      # Upload .h5 model to S3
│   ├── register_model.py    # Register model metadata in DynamoDB
│   ├── build_and_push.py    # Docker build + ECR push
│   ├── test_api.py          # Functional testing of /predict endpoint
│   └── measure_performance.py  # Latency / throughput benchmarking
│
├── dataset/                 # Brain Tumor MRI Dataset (Kaggle)
├── requirements.txt
└── .gitignore
```

---

## API Contract

**Endpoint:** `POST /predict`

**Request** (multipart/form-data):
```
metadata: {"model": "mri"}
image:    <binary JPG/PNG MRI image>
```

**Response:**
```json
{
  "classification": "glioma",
  "confidence": 0.9847,
  "model": "mri"
}
```

---

## Step-by-Step Deployment

### Prerequisites
- Python 3.10+
- Terraform >= 1.5
- AWS CLI (configured with `us-east-1`)
- Docker Desktop

### 1. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 2. Train the model
```bash
python model/train_model.py
```
Outputs: `model/brain_tumor_model.h5`, `model/brain_tumor_model.onnx`

### 3. Deploy infrastructure with Terraform
```bash
cd terraform
terraform init
terraform plan
terraform apply
```

Note the outputs — you will need:
- `model_bucket_name`
- `dynamodb_table_name`
- `lambda_ecr_repository_url`
- `ecs_ecr_repository_url`
- `predict_endpoint`

### 4. Upload model to S3
```bash
python scripts/upload_model.py \
  --bucket $(cd terraform && terraform output -raw model_bucket_name) \
  --table  $(cd terraform && terraform output -raw dynamodb_table_name)
```

### 5. Build and push Docker images to ECR
```bash
python scripts/build_and_push.py \
  --lambda-repo $(cd terraform && terraform output -raw lambda_ecr_repository_url) \
  --ecs-repo    $(cd terraform && terraform output -raw ecs_ecr_repository_url)
```

### 6. Update Lambda to use the new image
```bash
aws lambda update-function-code \
  --function-name $(cd terraform && terraform output -raw lambda_function_name) \
  --image-uri $(cd terraform && terraform output -raw lambda_ecr_repository_url):latest
```

### 7. Run functional tests
```bash
python scripts/test_api.py \
  --url $(cd terraform && terraform output -raw predict_endpoint | sed 's|/predict||')
```

### 8. Measure performance
```bash
python scripts/measure_performance.py \
  --url $(cd terraform && terraform output -raw predict_endpoint | sed 's|/predict||') \
  --requests 20
```

---

## Security Architecture

| Layer | Mechanism |
|---|---|
| Transport | HTTPS (API Gateway TLS) |
| Encryption at rest | AWS KMS (S3, DynamoDB, CloudWatch Logs) |
| Secrets | AWS Secrets Manager |
| Access control | IAM roles with least-privilege policies |
| Container scanning | ECR image scanning on push |

---

## Performance Metrics (Phase 4)

Collected automatically by `scripts/measure_performance.py`:
- Cold-start vs warm-start latency
- P50 / P90 / P99 latency
- Throughput (req/s)
- Estimated execution cost (Lambda)

---

## Dataset

[Brain Tumor MRI Dataset](https://www.kaggle.com/datasets/masoudnickparvar/brain-tumor-mri-dataset) from Kaggle.

Classes: `glioma`, `meningioma`, `notumor`, `pituitary`  
Split: `Training/` + `Testing/` directories (pre-split)

---

## License

Academic use only. All rights reserved.
