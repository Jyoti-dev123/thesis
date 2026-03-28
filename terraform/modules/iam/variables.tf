variable "name_prefix" {
  description = "Name prefix for IAM role names"
  type        = string
}

variable "account_id" {
  description = "AWS account ID"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "model_bucket_arn" {
  description = "ARN of the S3 model bucket"
  type        = string
}

variable "image_bucket_arn" {
  description = "ARN of the S3 image bucket"
  type        = string
}

variable "dynamodb_table_arn" {
  description = "ARN of the DynamoDB model metadata table"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the KMS key"
  type        = string
}

variable "secret_arn" {
  description = "ARN of the Secrets Manager secret"
  type        = string
}
