terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.4"
    }
  }

  # Optional: remote state in S3 (uncomment after first apply)
  # backend "s3" {
  #   bucket = "your-terraform-state-bucket"
  #   key    = "aaas/terraform.tfstate"
  #   region = "us-east-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = var.project_name
      Environment = var.environment
      ManagedBy   = "Terraform"
    }
  }
}

# ---------------------------------------------------------------
# Data sources
# ---------------------------------------------------------------
data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id
  region     = data.aws_region.current.name
  name_prefix = "${var.project_name}-${var.environment}"
}

# ---------------------------------------------------------------
# Module: KMS + Secrets Manager
# ---------------------------------------------------------------
module "security" {
  source       = "./modules/security"
  name_prefix  = local.name_prefix
  account_id   = local.account_id
  region       = local.region
}

# ---------------------------------------------------------------
# Module: S3 buckets
# ---------------------------------------------------------------
module "s3" {
  source       = "./modules/s3"
  name_prefix  = local.name_prefix
  kms_key_arn  = module.security.kms_key_arn
}

# ---------------------------------------------------------------
# Module: DynamoDB
# ---------------------------------------------------------------
module "dynamodb" {
  source      = "./modules/dynamodb"
  name_prefix = local.name_prefix
  kms_key_arn = module.security.kms_key_arn
}

# ---------------------------------------------------------------
# Module: ECR repositories
# ---------------------------------------------------------------
module "ecr" {
  source      = "./modules/ecr"
  name_prefix = local.name_prefix
}

# ---------------------------------------------------------------
# Module: IAM roles
# ---------------------------------------------------------------
module "iam" {
  source             = "./modules/iam"
  name_prefix        = local.name_prefix
  account_id         = local.account_id
  region             = local.region
  model_bucket_arn   = module.s3.model_bucket_arn
  image_bucket_arn   = module.s3.image_bucket_arn
  dynamodb_table_arn = module.dynamodb.table_arn
  kms_key_arn        = module.security.kms_key_arn
  secret_arn         = module.security.secret_arn
}

# ---------------------------------------------------------------
# Module: Lambda (serverless inference)
# ---------------------------------------------------------------
module "lambda" {
  source             = "./modules/lambda"
  name_prefix        = local.name_prefix
  region             = local.region
  lambda_role_arn    = module.iam.lambda_role_arn
  ecr_image_uri      = module.ecr.lambda_image_uri
  model_bucket       = module.s3.model_bucket_name
  model_key          = var.model_s3_key
  model_table        = module.dynamodb.table_name
  kms_key_arn        = module.security.kms_key_arn
}

# ---------------------------------------------------------------
# Module: API Gateway → Lambda
# ---------------------------------------------------------------
module "api_gateway" {
  source             = "./modules/api_gateway"
  name_prefix        = local.name_prefix
  lambda_invoke_arn  = module.lambda.lambda_invoke_arn
  lambda_arn         = module.lambda.lambda_arn
  environment        = var.environment
}

# ---------------------------------------------------------------
# Module: ECS/Fargate (container inference) — optional
# ---------------------------------------------------------------
module "ecs" {
  source            = "./modules/ecs"
  name_prefix       = local.name_prefix
  region            = local.region
  account_id        = local.account_id
  ecs_task_role_arn = module.iam.ecs_task_role_arn
  ecs_exec_role_arn = module.iam.ecs_exec_role_arn
  ecr_image_uri     = module.ecr.ecs_image_uri
  model_bucket      = module.s3.model_bucket_name
  model_key         = var.model_s3_key
  model_table       = module.dynamodb.table_name
  vpc_id            = var.vpc_id
  subnet_ids        = var.subnet_ids
}
