variable "name_prefix" {
  description = "Name prefix for ECS resources"
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

variable "ecs_task_role_arn" {
  description = "ARN of the ECS task role"
  type        = string
}

variable "ecs_exec_role_arn" {
  description = "ARN of the ECS execution role"
  type        = string
}

variable "ecr_image_uri" {
  description = "ECR container image URI for the ECS task"
  type        = string
}

variable "model_bucket" {
  description = "Name of the S3 model bucket"
  type        = string
}

variable "model_key" {
  description = "S3 object key for the model file"
  type        = string
}

variable "model_table" {
  description = "DynamoDB table name for model metadata"
  type        = string
}

variable "vpc_id" {
  description = "VPC ID (empty = use default VPC)"
  type        = string
  default     = ""
}

variable "subnet_ids" {
  description = "Subnet IDs for ECS tasks (empty = use default subnets)"
  type        = list(string)
  default     = []
}
