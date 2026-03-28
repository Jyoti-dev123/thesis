variable "name_prefix" {
  description = "Name prefix for API Gateway resources"
  type        = string
}

variable "lambda_invoke_arn" {
  description = "Invoke ARN of the Lambda function"
  type        = string
}

variable "lambda_arn" {
  description = "ARN of the Lambda function (for resource policy)"
  type        = string
}

variable "environment" {
  description = "Deployment stage name (dev / staging / prod)"
  type        = string
}
