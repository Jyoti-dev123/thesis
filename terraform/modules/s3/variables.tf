variable "name_prefix" {
  description = "Name prefix for S3 bucket names"
  type        = string
}

variable "kms_key_arn" {
  description = "ARN of the KMS key for server-side encryption"
  type        = string
}
