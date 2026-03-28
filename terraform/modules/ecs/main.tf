# ---------------------------------------------------------------
# Networking — use default VPC/subnets if none provided
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
  vpc_id     = var.vpc_id != "" ? var.vpc_id : data.aws_vpc.default.id
  subnet_ids = length(var.subnet_ids) > 0 ? var.subnet_ids : data.aws_subnets.default.ids
}

# ---------------------------------------------------------------
# Security Group for ECS tasks
# ---------------------------------------------------------------
resource "aws_security_group" "ecs_sg" {
  name        = "${var.name_prefix}-ecs-sg"
  description = "Security group for AaaS ECS Fargate tasks"
  vpc_id      = local.vpc_id

  ingress {
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow inbound on port 8080 (Flask app)"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound (S3, DynamoDB, ECR access)"
  }

  tags = {
    Name = "${var.name_prefix}-ecs-sg"
  }
}

# ---------------------------------------------------------------
# CloudWatch Log Group for ECS containers
# ---------------------------------------------------------------
resource "aws_cloudwatch_log_group" "ecs_logs" {
  name              = "/ecs/${var.name_prefix}-inference"
  retention_in_days = 14

  tags = {
    Name = "${var.name_prefix}-ecs-logs"
  }
}

# ---------------------------------------------------------------
# ECS Cluster
# ---------------------------------------------------------------
resource "aws_ecs_cluster" "main" {
  name = "${var.name_prefix}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.name_prefix}-cluster"
  }
}

resource "aws_ecs_cluster_capacity_providers" "fargate" {
  cluster_name       = aws_ecs_cluster.main.name
  capacity_providers = ["FARGATE", "FARGATE_SPOT"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
    base              = 1
  }
}

# ---------------------------------------------------------------
# ECS Task Definition
# ---------------------------------------------------------------
resource "aws_ecs_task_definition" "inference" {
  family                   = "${var.name_prefix}-inference"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "2048"  # 2 vCPU
  memory                   = "4096"  # 4 GB
  task_role_arn            = var.ecs_task_role_arn
  execution_role_arn       = var.ecs_exec_role_arn

  container_definitions = jsonencode([
    {
      name      = "inference"
      image     = var.ecr_image_uri
      essential = true

      portMappings = [
        {
          containerPort = 8080
          hostPort      = 8080
          protocol      = "tcp"
        }
      ]

      environment = [
        { name = "MODEL_BUCKET",        value = var.model_bucket },
        { name = "MODEL_KEY",           value = var.model_key },
        { name = "MODEL_TABLE",         value = var.model_table },
        { name = "AWS_DEFAULT_REGION",  value = var.region },
        { name = "PORT",                value = "8080" },
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_logs.name
          "awslogs-region"        = var.region
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"]
        interval    = 30
        timeout     = 10
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name = "${var.name_prefix}-inference-task"
  }
}

# ---------------------------------------------------------------
# Application Load Balancer
# ---------------------------------------------------------------
resource "aws_lb" "ecs_alb" {
  name               = "${var.name_prefix}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.ecs_sg.id]
  subnets            = local.subnet_ids

  enable_deletion_protection = false

  tags = {
    Name = "${var.name_prefix}-alb"
  }
}

resource "aws_lb_target_group" "ecs_tg" {
  name        = "${var.name_prefix}-tg"
  port        = 8080
  protocol    = "HTTP"
  target_type = "ip"
  vpc_id      = local.vpc_id

  health_check {
    path                = "/health"
    interval            = 30
    timeout             = 10
    healthy_threshold   = 2
    unhealthy_threshold = 3
    matcher             = "200"
  }

  tags = {
    Name = "${var.name_prefix}-tg"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.ecs_alb.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.ecs_tg.arn
  }
}

# ---------------------------------------------------------------
# ECS Service
# ---------------------------------------------------------------
resource "aws_ecs_service" "inference" {
  name            = "${var.name_prefix}-inference-service"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.inference.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = local.subnet_ids
    security_groups  = [aws_security_group.ecs_sg.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.ecs_tg.arn
    container_name   = "inference"
    container_port   = 8080
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  depends_on = [aws_lb_listener.http]

  tags = {
    Name = "${var.name_prefix}-inference-service"
  }
}
