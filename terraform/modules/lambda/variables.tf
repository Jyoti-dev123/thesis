variable "name_prefix" {
  description = "Name prefix for Lambda resources"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "lambda_role_arn" {
  description = "ARN of the Lambda execution IAM role"
  type        = string
}

variable "ecr_image_uri" {
  description = "ECR image URI for the Lambda container (repo:tag)"
  type        = string
}

variable "model_bucket" {
  description = "Name of the S3 bucket holding the model file"
  type        = string
}

variable "model_key" {
  description = "S3 object key of the model file"
  type        = string
}

variable "model_table" {
  description = "DynamoDB table name for model metadata"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the KMS key (for CloudWatch log encryption)"
  type        = string
}
