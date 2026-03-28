variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Short name prefix applied to all resource names"
  type        = string
  default     = "aaas-mri"
}

variable "environment" {
  description = "Deployment environment (dev / staging / prod)"
  type        = string
  default     = "dev"
}

variable "model_s3_key" {
  description = "S3 object key for the trained model file"
  type        = string
  default     = "models/brain_tumor_model.pt"
}

# ---------------------------------------------------------------
# Networking — used by ECS/Fargate module
# Pass the default VPC/subnets or create a dedicated one.
# ---------------------------------------------------------------
variable "vpc_id" {
  description = "VPC ID where ECS tasks are deployed"
  type        = string
  default     = ""
}

variable "subnet_ids" {
  description = "List of subnet IDs for ECS Fargate tasks"
  type        = list(string)
  default     = []
}
