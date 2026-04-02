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

# ---------------------------------------------------------------
# EC2 compute option
# ---------------------------------------------------------------
variable "ec2_instance_type" {
  description = "EC2 instance type for the inference server"
  type        = string
  default     = "t3.medium"
}

variable "ec2_subnet_id" {
  description = "Subnet ID for the EC2 instance (empty = first default subnet)"
  type        = string
  default     = ""
}

variable "ec2_key_pair_name" {
  description = "Name of an existing EC2 key pair for SSH access (leave empty to disable SSH)"
  type        = string
  default     = ""
}
