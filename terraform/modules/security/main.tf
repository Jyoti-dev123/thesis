# KMS key for encrypting S3, DynamoDB, and Secrets Manager resources
resource "aws_kms_key" "main" {
  description             = "${var.name_prefix} - AaaS encryption key"
  deletion_window_in_days = 7
  enable_key_rotation     = true

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "Enable IAM User Permissions"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.account_id}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "Allow Lambda and ECS to use the key"
        Effect = "Allow"
        Principal = {
          Service = [
            "lambda.amazonaws.com",
            "ecs-tasks.amazonaws.com",
          ]
        }
        Action = [
          "kms:Decrypt",
          "kms:GenerateDataKey",
          "kms:DescribeKey",
        ]
        Resource = "*"
      },
      {
        Sid    = "Allow CloudWatch Logs to use the key"
        Effect = "Allow"
        Principal = {
          Service = "logs.us-east-1.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey",
        ]
        Resource = "*"
        Condition = {
          ArnLike = {
            "kms:EncryptionContext:aws:logs:arn" = "arn:aws:logs:us-east-1:${var.account_id}:*"
          }
        }
      },
    ]
  })

  tags = {
    Name = "${var.name_prefix}-kms-key"
  }
}

resource "aws_kms_alias" "main" {
  name          = "alias/${var.name_prefix}-key"
  target_key_id = aws_kms_key.main.key_id
}

# Secrets Manager secret for API keys / future sensitive config
resource "aws_secretsmanager_secret" "api_secret" {
  name                    = "${var.name_prefix}/api-credentials"
  description             = "API credentials for the AaaS inference endpoint"
  kms_key_id              = aws_kms_key.main.arn
  recovery_window_in_days = 7

  tags = {
    Name = "${var.name_prefix}-api-secret"
  }
}

resource "aws_secretsmanager_secret_version" "api_secret_init" {
  secret_id = aws_secretsmanager_secret.api_secret.id

  secret_string = jsonencode({
    api_key = "REPLACE_WITH_GENERATED_KEY"
  })

  lifecycle {
    ignore_changes = [secret_string]
  }
}
