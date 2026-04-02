#!/bin/bash
# =============================================================================
# EC2 User Data — AaaS Inference Container Bootstrap
#
# This script runs once on first boot.  It installs Docker, authenticates
# to Amazon ECR, pulls the inference container image, and starts it as a
# systemd-managed service so it restarts automatically on instance reboot.
# =============================================================================
set -euo pipefail
exec > /var/log/aaas-bootstrap.log 2>&1

echo "=== AaaS EC2 bootstrap started ==="

# ---- 1. Install Docker -------------------------------------------------------
yum update -y
yum install -y docker
systemctl enable docker
systemctl start docker
usermod -aG docker ec2-user

# ---- 2. Authenticate Docker to Amazon ECR ------------------------------------
echo "Logging in to ECR registry: ${ecr_registry}"
aws ecr get-login-password --region ${region} \
  | docker login --username AWS --password-stdin ${ecr_registry}

# ---- 3. Pull the inference container image -----------------------------------
echo "Pulling image: ${ecr_image_uri}"
docker pull ${ecr_image_uri}

# ---- 4. Create a systemd unit to manage the container -----------------------
cat > /etc/systemd/system/aaas-inference.service << 'EOF'
[Unit]
Description=AaaS Inference Container
After=docker.service
Requires=docker.service

[Service]
Restart=always
RestartSec=5
ExecStartPre=-/usr/bin/docker stop aaas-inference
ExecStartPre=-/usr/bin/docker rm   aaas-inference
ExecStart=/usr/bin/docker run \
  --name aaas-inference \
  --rm \
  -p 8080:8080 \
  -e MODEL_BUCKET=${model_bucket} \
  -e MODEL_KEY=${model_key} \
  -e MODEL_TABLE=${model_table} \
  -e AWS_DEFAULT_REGION=${region} \
  ${ecr_image_uri}
ExecStop=/usr/bin/docker stop aaas-inference

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable aaas-inference
systemctl start aaas-inference

echo "=== AaaS EC2 bootstrap complete ==="
