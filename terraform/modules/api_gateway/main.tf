resource "aws_apigatewayv2_api" "main" {
  name          = "${var.name_prefix}-api"
  protocol_type = "HTTP"
  description   = "AaaS Medical Image Classification API"

  cors_configuration {
    allow_headers = ["content-type", "x-api-key"]
    allow_methods = ["POST", "GET", "DELETE", "OPTIONS"]
    allow_origins = ["*"]
    max_age       = 300
  }

  tags = {
    Name = "${var.name_prefix}-api"
  }
}

# Lambda integration
resource "aws_apigatewayv2_integration" "lambda_integration" {
  api_id                 = aws_apigatewayv2_api.main.id
  integration_type       = "AWS_PROXY"
  integration_uri        = var.lambda_invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
}

# POST /predict route
resource "aws_apigatewayv2_route" "predict" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /predict"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# GET /health route
resource "aws_apigatewayv2_route" "health" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /health"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# ---- Model management routes ----

# GET /models — list all registered model versions
resource "aws_apigatewayv2_route" "models_list" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /models"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# POST /models — register a new model version
resource "aws_apigatewayv2_route" "models_register" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "POST /models"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# GET /models/{model_name} — get latest version info
resource "aws_apigatewayv2_route" "models_get" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "GET /models/{model_name}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# DELETE /models/{model_name}/{version} — remove a model version entry
resource "aws_apigatewayv2_route" "models_delete" {
  api_id    = aws_apigatewayv2_api.main.id
  route_key = "DELETE /models/{model_name}/{version}"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_integration.id}"
}

# Default deployment stage with access logging
resource "aws_cloudwatch_log_group" "api_logs" {
  name              = "/aws/apigateway/${var.name_prefix}"
  retention_in_days = 14
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.main.id
  name        = var.environment
  auto_deploy = true

  access_log_settings {
    destination_arn = aws_cloudwatch_log_group.api_logs.arn
    format = jsonencode({
      requestId      = "$context.requestId"
      sourceIp       = "$context.identity.sourceIp"
      requestTime    = "$context.requestTime"
      httpMethod     = "$context.httpMethod"
      routeKey       = "$context.routeKey"
      status         = "$context.status"
      responseLength = "$context.responseLength"
      integrationLatency = "$context.integrationLatency"
    })
  }

  default_route_settings {
    throttling_burst_limit = 100
    throttling_rate_limit  = 50
  }

  tags = {
    Name = "${var.name_prefix}-stage-${var.environment}"
  }
}

# Grant API Gateway permission to invoke Lambda
resource "aws_lambda_permission" "apigw_invoke" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_arn
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.main.execution_arn}/*/*"
}
