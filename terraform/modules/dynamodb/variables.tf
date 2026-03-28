variable "name_prefix" {
  description = "Name prefix for the DynamoDB table"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the KMS key for DynamoDB encryption at rest"
  type        = string
}
