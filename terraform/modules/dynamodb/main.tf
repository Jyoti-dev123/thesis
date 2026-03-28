resource "aws_dynamodb_table" "model_metadata" {
  name         = "${var.name_prefix}-model-metadata"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "model_name"

  attribute {
    name = "model_name"
    type = "S"
  }

  # Global secondary index for querying by version
  global_secondary_index {
    name            = "version-index"
    hash_key        = "model_name"
    range_key       = "version"
    projection_type = "ALL"
  }

  attribute {
    name = "version"
    type = "S"
  }

  # Encryption at rest with KMS
  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }

  # Point-in-time recovery
  point_in_time_recovery {
    enabled = true
  }

  tags = {
    Name = "${var.name_prefix}-model-metadata"
  }
}
