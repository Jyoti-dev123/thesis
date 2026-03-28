resource "aws_cloudwatch_log_group" "lambda_logs" {
  name              = "/aws/lambda/${var.name_prefix}-inference"
  retention_in_days = 14
  kms_key_id        = var.kms_key_arn
}

resource "aws_lambda_function" "inference" {
  function_name = "${var.name_prefix}-inference"
  role          = var.lambda_role_arn
  package_type  = "Image"
  image_uri     = var.ecr_image_uri

  # Container image entry point overrides are inherited from the Dockerfile CMD
  architectures = ["x86_64"]
  memory_size   = 3008  # 3 GB for TF model loading
  timeout       = 120   # 2 minutes to cover cold start + inference

  environment {
    variables = {
      MODEL_BUCKET = var.model_bucket
      MODEL_KEY    = var.model_key
      MODEL_TABLE  = var.model_table
      APP_REGION   = var.region
    }
  }

  logging_config {
    log_format = "JSON"
    log_group  = aws_cloudwatch_log_group.lambda_logs.name
  }

  depends_on = [aws_cloudwatch_log_group.lambda_logs]

  tags = {
    Name = "${var.name_prefix}-inference"
  }
}

# Lambda provisioned concurrency to address cold-start (optional)
# Uncomment for warm-start benchmarking in Phase 4
# resource "aws_lambda_provisioned_concurrency_config" "warm" {
#   function_name                  = aws_lambda_function.inference.function_name
#   qualifier                      = aws_lambda_function.inference.version
#   provisioned_concurrent_executions = 1
# }
