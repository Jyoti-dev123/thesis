# terraform.tfvars
# Override default variable values here.
# Do NOT commit secrets to version control.

aws_region   = "us-east-1"
project_name = "aaas-mri"
environment  = "dev"
model_s3_key = "models/brain_tumor_model.pt"

# Networking: leave empty to use defaults computed by the ECS module,
# or supply specific IDs for a custom VPC.
vpc_id     = ""
subnet_ids = []
