resource "aws_s3_bucket" "model_bucket" {
  bucket = "${var.name_prefix}-models-${random_id.suffix.hex}"

  force_destroy = true
}

resource "aws_s3_bucket" "image_bucket" {
  bucket = "${var.name_prefix}-images-${random_id.suffix.hex}"

  force_destroy = true
}

resource "random_id" "suffix" {
  byte_length = 4
}

# Block all public access
resource "aws_s3_bucket_public_access_block" "model_bucket_pab" {
  bucket                  = aws_s3_bucket.model_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "image_bucket_pab" {
  bucket                  = aws_s3_bucket.image_bucket.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Server-side encryption with KMS
resource "aws_s3_bucket_server_side_encryption_configuration" "model_enc" {
  bucket = aws_s3_bucket.model_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "image_enc" {
  bucket = aws_s3_bucket.image_bucket.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.kms_key_arn
    }
    bucket_key_enabled = true
  }
}

# Versioning for model lifecycle management
resource "aws_s3_bucket_versioning" "model_versioning" {
  bucket = aws_s3_bucket.model_bucket.id

  versioning_configuration {
    status = "Enabled"
  }
}

# Lifecycle policy: move old model versions to Glacier after 90 days
resource "aws_s3_bucket_lifecycle_configuration" "model_lifecycle" {
  bucket = aws_s3_bucket.model_bucket.id

  rule {
    id     = "archive-old-models"
    status = "Enabled"

    noncurrent_version_transition {
      noncurrent_days = 90
      storage_class   = "GLACIER"
    }
  }
}
