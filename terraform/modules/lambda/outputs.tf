output "lambda_arn" {
  description = "ARN of the Lambda inference function"
  value       = aws_lambda_function.inference.arn
}

output "lambda_name" {
  description = "Name of the Lambda inference function"
  value       = aws_lambda_function.inference.function_name
}

output "lambda_invoke_arn" {
  description = "Invoke ARN of the Lambda function (used by API Gateway)"
  value       = aws_lambda_function.inference.invoke_arn
}
