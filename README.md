# Cloud Design Patterns — Analytics as a Service for Brain Tumor MRI Classification

> **MSc Thesis:** Design and Implementation of a Cloud-Agnostic *Analytics as a Service* (AaaS) Pattern for Medical Image Classification using Terraform

---

## Overview

This thesis demonstrates how established **cloud design patterns** can be applied to build a fully reproducible, provider-agnostic AaaS system. The chosen domain is automated brain tumor classification from MRI scans using a PyTorch MobileNetV2 deep learning model, achieving **94.56% test accuracy** across four classes:

**glioma · meningioma · notumor · pituitary**

The same Docker container image is deployed across three structurally different compute paradigms — proving portability, which is the central cloud-agnostic claim of the thesis:

| Architecture | Compute | Cold Start | Best For |
|---|---|---|---|
| **Serverless** | AWS Lambda (Docker container, 3008 MB) | ~10–30 s | Sporadic, event-driven inference |
| **Container Orchestration** | Amazon ECS Fargate (Docker container) | None (always warm) | High-throughput, sustained load |
| **VM-Based** | Amazon EC2 t3.medium, AL2023 (Docker app) | Minimal | Direct VM deployment comparison |

All infrastructure is declared as code in **9 modular Terraform configurations** — one `terraform apply` reproduces the entire environment.

---

## Live Deployed Infrastructure (us-east-1)

| Resource | Identifier / URL |
|---|---|
| API Gateway Base URL | `https://whaveg4pu8.execute-api.us-east-1.amazonaws.com/dev` |
| Predict Endpoint | `https://whaveg4pu8.execute-api.us-east-1.amazonaws.com/dev/predict` |
| Lambda Function | `aaas-mri-dev-inference` |
| Lambda ECR Repository | `069835412283.dkr.ecr.us-east-1.amazonaws.com/aaas-mri-dev-lambda-inference` |
| ECS Service | `aaas-mri-dev-inference-service` |
| ECS ECR Repository | `069835412283.dkr.ecr.us-east-1.amazonaws.com/aaas-mri-dev-ecs-inference` |
| EC2 Instance ID | `i-0832e29292f2e42a8` |
| EC2 Public IP | `98.92.207.44` |
| EC2 Inference Endpoint | `http://ec2-98-92-207-44.compute-1.amazonaws.com:8080/predict` |
| Model S3 Bucket | `aaas-mri-dev-models-12c3f89a` |
| Image S3 Bucket | `aaas-mri-dev-images-12c3f89a` |
| DynamoDB Model Registry | `aaas-mri-dev-model-metadata` (hash: `model_name`, range: `version`) |
| KMS Key ID | `010561d9-a0ed-4c4f-99b8-44f504393dd5` |

---

## Repository Structure

```
jyoti_thesis/
├── model/
│   ├── train_model.py          # MobileNetV2 two-phase transfer learning + ONNX export
│   ├── preprocess.py           # Image resize, normalise (224×224 RGB)
│   ├── brain_tumor_model.pt    # Trained PyTorch weights (tracked via Git LFS / S3)
│   ├── brain_tumor_model.onnx  # ONNX export
│   ├── class_labels.json       # {0: glioma, 1: meningioma, 2: notumor, 3: pituitary}
│   └── requirements.txt
│
├── backend/
│   ├── lambda/
│   │   ├── handler.py          # Lambda container handler — DynamoDB lookup, S3 model load, inference
│   │   ├── Dockerfile          # Lambda container image (pushed to ECR)
│   │   └── requirements.txt
│   └── ecs/
│       ├── app.py              # Flask REST API served by ECS Fargate and EC2 Docker app
│       ├── Dockerfile          # Fargate/EC2 container image (pushed to ECR)
│       └── requirements.txt
│
├── terraform/
│   ├── main.tf                 # Root module — wires all nine sub-modules
│   ├── variables.tf
│   ├── outputs.tf              # Exposes API URL, EC2 IP, bucket names, table name
│   ├── terraform.tfvars
│   └── modules/
│       ├── security/           # KMS customer-managed key + Secrets Manager
│       ├── s3/                 # Model & image buckets (versioned, KMS-encrypted, lifecycle)
│       ├── dynamodb/           # Model registry table (model_name + version composite key)
│       ├── ecr/                # Docker image repos for Lambda and ECS; lifecycle policies
│       ├── iam/                # Least-privilege roles for Lambda, ECS, EC2
│       ├── lambda/             # Lambda function (container image, 3008 MB)
│       ├── api_gateway/        # HTTP API v2 — POST /predict + model management routes
│       ├── ecs/                # ECS cluster, Fargate task/service, ALB
│       └── ec2/                # EC2 instance (AL2023, t3.medium, 30 GB gp3, IMDSv2)
│
├── scripts/
│   ├── upload_model.py         # Upload .pt / .onnx model artefact to S3
│   ├── register_model.py       # Register model metadata in DynamoDB
│   ├── build_and_push.py       # Docker build + tag + push to ECR for Lambda and ECS
│   ├── test_api.py             # End-to-end functional tests against /predict
│   └── measure_performance.py  # Latency / throughput / cost benchmarking
│
├── webapp/                     # Flask demo application (port 5000)
│   ├── app.py                  # Routes: /, /predict, /benchmark, /about, /api/health
│   ├── requirements.txt
│   ├── static/
│   │   ├── css/style.css
│   │   └── img/
│   │       ├── overview.png    # PlantUML-rendered overview architecture diagram
│   │       └── detailed.png    # PlantUML-rendered detailed infrastructure map
│   └── templates/
│       ├── base.html           # Shared Bootstrap 5 layout with navbar + footer
│       ├── index.html          # Upload & classify page
│       ├── benchmark.html      # Interactive latency benchmark with image selector
│       └── about.html          # Full project / thesis explanation page
│
├── diagrams/
│   ├── overview.puml           # PlantUML: high-level component + data flow diagram
│   └── detailed.puml           # PlantUML: detailed infra map (all AWS resources + IDs)
│
├── dataset/                    # Brain Tumor MRI Dataset (Kaggle, not committed)
├── deployed-details.txt        # Live terraform output — all resource endpoints and IDs
├── requirements.txt
└── .gitignore
```

---

## Cloud Design Patterns Applied

| Pattern | Implementation |
|---|---|
| **Serverless / Event-Driven** | AWS Lambda triggered by API Gateway HTTP events |
| **Container Microservice** | Docker images on ECS Fargate; same image on EC2 |
| **VM-Based Deployment** | EC2 instance running Docker Engine — third compute target |
| **Infrastructure as Code** | 9 Terraform modules; full environment from `terraform apply` |
| **Model Registry** | DynamoDB table + S3 versioned bucket; runtime model resolution |
| **Security by Default** | KMS encryption, least-privilege IAM, IMDSv2, Secrets Manager |

---

## Docker — Portability Layer

All inference workloads run as Docker container images stored in **Amazon ECR**. The *same image* is deployed across Lambda, ECS Fargate, and EC2 — demonstrating cloud-agnostic portability without any code changes to the inference service.

```
ECR repositories:
  069835412283.dkr.ecr.us-east-1.amazonaws.com/aaas-mri-dev-lambda-inference
  069835412283.dkr.ecr.us-east-1.amazonaws.com/aaas-mri-dev-ecs-inference
```

---

## API Contract

### `POST /predict`

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

### Model Management Routes

| Method | Route | Description |
|---|---|---|
| `GET` | `/models` | List all registered models |
| `POST` | `/models` | Register a new model version |
| `GET` | `/models/{name}` | Get metadata for a specific model |
| `DELETE` | `/models/{name}/{version}` | Deregister a model version |

---

## Web Application

The Flask webapp at `webapp/` connects to the live Lambda API and provides:

- **Classify page** (`/`) — drag-and-drop MRI image upload; returns class, confidence, severity badge, and clinical description
- **Benchmark page** (`/benchmark`) — interactive thumbnail selector across all 4 tumor classes; runs up to 50 sequential requests; reports cold-start vs warm-start latency, p50/p90/p99 percentiles, throughput (req/s), and estimated Lambda cost in USD
- **About page** (`/about`) — full thesis explanation covering all 6 cloud design patterns, Docker portability layer, MobileNetV2 training strategy, live infrastructure table (all resource IDs), 9-module Terraform breakdown, and both architecture diagrams with lightbox zoom
- **Health probe** (`/api/health`) — real end-to-end API call returning live latency

Run locally:
```bash
# from project root, with venv activated
pip install -r webapp/requirements.txt
python webapp/app.py
# → http://localhost:5000
```

---

## Step-by-Step Deployment

### Prerequisites
- Python 3.10+, Terraform ≥ 1.5, AWS CLI (us-east-1), Docker Desktop

### 1. Clone and install dependencies
```bash
git clone https://github.com/Jyoti-dev123/thesis.git
cd thesis
pip install -r requirements.txt
```

### 2. Configure AWS credentials
```bash
aws configure
# or export AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY
```

### 3. Train the model
```bash
python model/train_model.py
# Outputs: model/brain_tumor_model.pt, model/brain_tumor_model.onnx
```

### 4. Deploy all infrastructure with Terraform
```bash
cd terraform
terraform init
terraform plan -out=tfplan
terraform apply tfplan
```

### 5. Upload model artefact to S3 and register in DynamoDB
```bash
python scripts/upload_model.py
python scripts/register_model.py
```

### 6. Build and push Docker images to ECR
```bash
python scripts/build_and_push.py
```

### 7. Run functional tests
```bash
python scripts/test_api.py
```

### 8. Run performance benchmarks
```bash
python scripts/measure_performance.py --requests 20
```

### 9. Launch the demo webapp
```bash
python webapp/app.py
# → http://localhost:5000
```

---

## Security Architecture

| Layer | Mechanism |
|---|---|
| Transport | HTTPS via API Gateway TLS |
| Encryption at rest | AWS KMS CMK (`010561d9-a0ed-4c4f-99b8-44f504393dd5`) — S3, DynamoDB, CloudWatch Logs, EC2 volume |
| Secrets | AWS Secrets Manager |
| Access control | Least-privilege IAM roles per compute backend |
| Instance metadata | IMDSv2 enforced on EC2 (`http_tokens = required`) |
| Container scanning | ECR image scanning on push |

---

## Performance Metrics

Measured via the webapp benchmark page and `scripts/measure_performance.py`:

- Cold-start vs warm-start latency (first request vs subsequent)
- P50 / P90 / P99 latency percentiles
- Throughput (requests/second)
- Estimated Lambda execution cost in USD (3008 MB × GB-seconds × $0.0000166667)

---

## Architecture Diagrams

PlantUML source files are in `diagrams/`. Rendered PNGs are served by the webapp at `/about`.

| Diagram | Source | Description |
|---|---|---|
| Overview | `diagrams/overview.puml` | High-level components, data flows, cloud design patterns |
| Detailed | `diagrams/detailed.puml` | All AWS resources with IDs, security layers, Terraform modules |

---

## Dataset

[Brain Tumor MRI Dataset](https://www.kaggle.com/datasets/masoudnickparvar/brain-tumor-mri-dataset) — Masoud Nickparvar, Kaggle.

Classes: `glioma` · `meningioma` · `notumor` · `pituitary`  
Split: pre-divided `Training/` and `Testing/` directories (not committed to repo — download separately).

---

## License

Academic use only. All rights reserved.
