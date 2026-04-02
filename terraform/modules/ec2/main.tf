# ---------------------------------------------------------------
# EC2 Compute Module — "Pluggable Compute" Cloud Design Pattern
#
# Runs the same Docker container image (from ECR) as the ECS/Fargate
# deployment on a traditional EC2 instance.  This demonstrates that
# the Analytics-as-a-Service pattern is compute-agnostic: the same
# containerised inference workload can be swapped between
#   • Lambda (serverless, event-driven)
#   • ECS / Fargate (managed containers)
#   • EC2 (IaaS, full control)
# without any change to the API contract or the application code.
# ---------------------------------------------------------------

# ---------------------------------------------------------------
# Networking — resolve VPC / subnet if not provided
# ---------------------------------------------------------------
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [local.vpc_id]
  }
}

locals {
  vpc_id    = var.vpc_id != "" ? var.vpc_id : data.aws_vpc.default.id
  subnet_id = var.subnet_id != "" ? var.subnet_id : tolist(data.aws_subnets.default.ids)[0]
  # ECR registry hostname is account_id.dkr.ecr.region.amazonaws.com
  ecr_registry = "${var.account_id}.dkr.ecr.${var.region}.amazonaws.com"
}

# ---------------------------------------------------------------
# AMI — latest Amazon Linux 2023
# ---------------------------------------------------------------
data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# ---------------------------------------------------------------
# IAM — EC2 instance role
# ---------------------------------------------------------------
resource "aws_iam_role" "ec2_role" {
  name = "${var.name_prefix}-ec2-inference-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect    = "Allow"
        Principal = { Service = "ec2.amazonaws.com" }
        Action    = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.name_prefix}-ec2-inference-role"
  }
}

resource "aws_iam_role_policy" "ec2_policy" {
  name = "${var.name_prefix}-ec2-inference-policy"
  role = aws_iam_role.ec2_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "S3ModelAccess"
        Effect = "Allow"
        Action = ["s3:GetObject", "s3:PutObject", "s3:ListBucket"]
        Resource = [
          var.model_bucket_arn,
          "${var.model_bucket_arn}/*",
          var.image_bucket_arn,
          "${var.image_bucket_arn}/*",
        ]
      },
      {
        Sid    = "DynamoDBAccess"
        Effect = "Allow"
        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:UpdateItem",
          "dynamodb:DeleteItem",
          "dynamodb:Query",
          "dynamodb:Scan",
        ]
        Resource = [
          var.dynamodb_table_arn,
          "${var.dynamodb_table_arn}/index/*",
        ]
      },
      {
        Sid    = "KMSAccess"
        Effect = "Allow"
        Action = ["kms:Decrypt", "kms:GenerateDataKey", "kms:DescribeKey"]
        Resource = [var.kms_key_arn]
      },
      {
        Sid    = "ECRPull"
        Effect = "Allow"
        Action = [
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:GetAuthorizationToken",
        ]
        Resource = "*"
      },
      {
        Sid    = "CloudWatchLogs"
        Effect = "Allow"
        Action = [
          "logs:CreateLogGroup",
          "logs:CreateLogStream",
          "logs:PutLogEvents",
        ]
        Resource = "arn:aws:logs:${var.region}:${var.account_id}:log-group:/ec2/${var.name_prefix}*:*"
      },
    ]
  })
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.name_prefix}-ec2-inference-profile"
  role = aws_iam_role.ec2_role.name

  tags = {
    Name = "${var.name_prefix}-ec2-inference-profile"
  }
}

# ---------------------------------------------------------------
# Security group
# ---------------------------------------------------------------
resource "aws_security_group" "ec2_sg" {
  name        = "${var.name_prefix}-ec2-sg"
  description = "Security group for AaaS EC2 inference instance"
  vpc_id      = local.vpc_id

  ingress {
    description = "Inference API"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # SSH — only enabled when a key pair is provided
  dynamic "ingress" {
    for_each = var.key_pair_name != "" ? [1] : []
    content {
      description = "SSH access"
      from_port   = 22
      to_port     = 22
      protocol    = "tcp"
      cidr_blocks = ["0.0.0.0/0"]
    }
  }

  egress {
    description = "All outbound (ECR, S3, DynamoDB)"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.name_prefix}-ec2-sg"
  }
}

# ---------------------------------------------------------------
# EC2 instance — runs the inference container from ECR
# ---------------------------------------------------------------
resource "aws_instance" "inference" {
  ami                         = data.aws_ami.al2023.id
  instance_type               = var.instance_type
  subnet_id                   = local.subnet_id
  vpc_security_group_ids      = [aws_security_group.ec2_sg.id]
  iam_instance_profile        = aws_iam_instance_profile.ec2_profile.name
  associate_public_ip_address = true
  key_name                    = var.key_pair_name != "" ? var.key_pair_name : null

  # Boot script: install Docker, pull image from ECR, start container
  user_data = base64encode(templatefile("${path.module}/user_data.sh.tpl", {
    region        = var.region
    ecr_registry  = local.ecr_registry
    ecr_image_uri = var.ecr_image_uri
    model_bucket  = var.model_bucket
    model_key     = var.model_key
    model_table   = var.model_table
  }))

  root_block_device {
      volume_size = 30
      volume_type = "gp3"
      encrypted   = true
    }

  metadata_options {
    http_tokens = "required"   # enforce IMDSv2
  }

  tags = {
    Name = "${var.name_prefix}-ec2-inference"
  }
}
