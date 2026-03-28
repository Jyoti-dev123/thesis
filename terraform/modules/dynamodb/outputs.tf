output "table_name" {
  description = "Name of the DynamoDB model metadata table"
  value       = aws_dynamodb_table.model_metadata.name
}

output "table_arn" {
  description = "ARN of the DynamoDB model metadata table"
  value       = aws_dynamodb_table.model_metadata.arn
}
