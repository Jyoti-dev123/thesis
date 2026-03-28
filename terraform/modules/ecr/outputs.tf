output "lambda_repo_url" {
  description = "ECR repository URL for the Lambda container image"
  value       = aws_ecr_repository.lambda_repo.repository_url
}

output "ecs_repo_url" {
  description = "ECR repository URL for the ECS container image"
  value       = aws_ecr_repository.ecs_repo.repository_url
}

# Placeholder image URI — callers use this before any image is pushed.
# After pushing, update the Lambda function to use the real :latest tag.
output "lambda_image_uri" {
  description = "Lambda container image URI (points to :latest)"
  value       = "${aws_ecr_repository.lambda_repo.repository_url}:latest"
}

output "ecs_image_uri" {
  description = "ECS container image URI (points to :latest)"
  value       = "${aws_ecr_repository.ecs_repo.repository_url}:latest"
}
