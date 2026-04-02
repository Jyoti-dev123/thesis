variable "name_prefix" {
  description = "Name prefix for EC2 resources"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

variable "ecr_image_uri" {
  description = "Full ECR image URI to pull and run on EC2 (e.g. 123456789.dkr.ecr.us-east-1.amazonaws.com/repo:latest)"
  type        = string
}

variable "model_bucket" {
  description = "S3 bucket name containing the model files"
  type        = string
}

variable "model_bucket_arn" {
  description = "ARN of the S3 model bucket (for IAM policy)"
  type        = string
}

variable "image_bucket_arn" {
  description = "ARN of the S3 image bucket (for IAM policy)"
  type        = string
}

variable "model_key" {
  description = "Default S3 key for the model file"
  type        = string
  default     = "models/brain_tumor_model.pt"
}

variable "model_table" {
  description = "DynamoDB table name for model metadata"
  type        = string
}

variable "dynamodb_table_arn" {
  description = "ARN of the DynamoDB table (for IAM policy)"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the KMS key used for encryption"
  type        = string
}

variable "instance_type" {
  description = "EC2 instance type for the inference server"
  type        = string
  default     = "t3.medium"
}

variable "vpc_id" {
  description = "VPC ID to deploy the EC2 instance into (empty = default VPC)"
  type        = string
  default     = ""
}

variable "subnet_id" {
  description = "Subnet ID for the EC2 instance (empty = first default subnet)"
  type        = string
  default     = ""
}

variable "key_pair_name" {
  description = "EC2 key pair name for SSH access (leave empty to disable SSH)"
  type        = string
  default     = ""
}
