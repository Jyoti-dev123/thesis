# terraform.tfvars
# Override default variable values here.
# Do NOT commit secrets to version control.

aws_region   = "us-east-1"
project_name = "aaas-mri"
environment  = "dev"
model_s3_key = "models/brain_tumor_model.pt"

# Networking: leave empty to use defaults computed by the ECS / EC2 modules,
# or supply specific IDs for a custom VPC.
vpc_id     = ""
subnet_ids = []

# EC2 compute option
ec2_instance_type = "t3.medium"
ec2_subnet_id     = ""         # empty = first default subnet
ec2_key_pair_name = ""         # empty = no SSH key (IMDSv2 only)
