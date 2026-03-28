output "model_bucket_name" {
  description = "Name of the S3 bucket for ML models"
  value       = aws_s3_bucket.model_bucket.bucket
}

output "model_bucket_arn" {
  description = "ARN of the S3 bucket for ML models"
  value       = aws_s3_bucket.model_bucket.arn
}

output "image_bucket_name" {
  description = "Name of the S3 bucket for uploaded MRI images"
  value       = aws_s3_bucket.image_bucket.bucket
}

output "image_bucket_arn" {
  description = "ARN of the S3 bucket for uploaded MRI images"
  value       = aws_s3_bucket.image_bucket.arn
}
