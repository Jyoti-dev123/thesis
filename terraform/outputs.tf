output "api_gateway_url" {
  description = "Base URL of the deployed API Gateway endpoint"
  value       = module.api_gateway.api_url
}

output "predict_endpoint" {
  description = "Full URL of the /predict endpoint"
  value       = "${module.api_gateway.api_url}/predict"
}

output "model_bucket_name" {
  description = "S3 bucket name for models and images"
  value       = module.s3.model_bucket_name
}

output "image_bucket_name" {
  description = "S3 bucket name for uploaded MRI images"
  value       = module.s3.image_bucket_name
}

output "dynamodb_table_name" {
  description = "DynamoDB table name for model metadata"
  value       = module.dynamodb.table_name
}

output "lambda_function_name" {
  description = "Name of the Lambda inference function"
  value       = module.lambda.lambda_name
}

output "lambda_ecr_repository_url" {
  description = "ECR repository URL for the Lambda container image"
  value       = module.ecr.lambda_repo_url
}

output "ecs_ecr_repository_url" {
  description = "ECR repository URL for the ECS container image"
  value       = module.ecr.ecs_repo_url
}

output "ecs_service_name" {
  description = "ECS service name"
  value       = module.ecs.service_name
}

output "kms_key_id" {
  description = "KMS key ID used for encryption"
  value       = module.security.kms_key_id
}

# ---------------------------------------------------------------
# EC2 compute tier
# ---------------------------------------------------------------
output "ec2_instance_id" {
  description = "EC2 inference instance ID"
  value       = module.ec2.instance_id
}

output "ec2_public_ip" {
  description = "Public IP of the EC2 inference instance"
  value       = module.ec2.public_ip
}

output "ec2_inference_url" {
  description = "Direct /predict endpoint on the EC2 instance"
  value       = module.ec2.inference_url
}

output "ec2_models_url" {
  description = "Direct /models management endpoint on the EC2 instance"
  value       = module.ec2.models_url
}
