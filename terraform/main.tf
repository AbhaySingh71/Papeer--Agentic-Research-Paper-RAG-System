terraform {
  required_version = ">= 1.0.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

#=========================================================
# VPC & Networking (Using AWS Default resources for ease)
#=========================================================
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

#=========================================================
# Security Groups
#=========================================================
resource "aws_security_group" "ecs_tasks" {
  name        = "${var.project_name}-ecs-sg"
  description = "Allow inbound traffic on port 8501 for Streamlit"
  vpc_id      = data.aws_vpc.default.id



  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    from_port   = 8501
    to_port     = 8501
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_security_group" "efs" {
  name        = "${var.project_name}-efs-sg"
  description = "Allow NFS traffic from ECS tasks"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.ecs_tasks.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

#=========================================================
# Elastic File System (EFS)
#=========================================================
resource "aws_efs_file_system" "storage" {
  creation_token = "${var.project_name}-efs"
  encrypted      = true

  tags = {
    Name = "${var.project_name}-efs"
  }
}

resource "aws_efs_mount_target" "mount" {
  count           = length(data.aws_subnets.default.ids)
  file_system_id  = aws_efs_file_system.storage.id
  subnet_id       = data.aws_subnets.default.ids[count.index]
  security_groups = [aws_security_group.efs.id]
}

#=========================================================
# Elastic Container Registry (ECR)
#=========================================================
resource "aws_ecr_repository" "repo" {
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"
  force_delete         = true

  image_scanning_configuration {
    scan_on_push = true
  }
}

#=========================================================
# CloudWatch Logs
#=========================================================
resource "aws_cloudwatch_log_group" "ecs_log_group" {
  name              = "/ecs/${var.project_name}"
  retention_in_days = 7
}

#=========================================================
# IAM Roles for ECS
#=========================================================
# Task Execution Role (Pull image, write logs)
resource "aws_iam_role" "ecs_execution_role" {
  name = "${var.project_name}-ecs-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Task Role (Interacts with EFS and external APIs)
resource "aws_iam_role" "ecs_task_role" {
  name = "${var.project_name}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
      }
    ]
  })
}

resource "aws_iam_role_policy" "efs_access" {
  name = "${var.project_name}-efs-policy"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "elasticfilesystem:ClientMount",
          "elasticfilesystem:ClientWrite",
          "elasticfilesystem:ClientRootAccess"
        ]
        Resource = aws_efs_file_system.storage.arn
      }
    ]
  })
}

#=========================================================
# ECS Task Definition
#=========================================================
resource "aws_ecs_task_definition" "task" {
  family                   = "${var.project_name}-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "512"
  memory                   = "1024"
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "${var.project_name}-container"
      image     = "${aws_ecr_repository.repo.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8501
          hostPort      = 8501
        }
      ]

      environment = [
        { name = "GROQ_API_KEY", value = var.groq_api_key },
        { name = "GOOGLE_API_KEY", value = var.google_api_key },
        { name = "COHERE_API_KEY", value = var.cohere_api_key },
        { name = "TAVILY_API_KEY", value = var.tavily_api_key },
        { name = "QDRANT_URL", value = var.qdrant_url },
        { name = "QDRANT_API_KEY", value = var.qdrant_api_key },
        { name = "LANGCHAIN_TRACING_V2", value = var.langchain_tracing_v2 },
        { name = "LANGCHAIN_API_KEY", value = var.langchain_api_key },
        { name = "LANGCHAIN_PROJECT", value = var.langchain_project },
        { name = "LANGSMITH_ENDPOINT", value = var.langchain_endpoint },
        { name = "PAPEER_DATA_DIR", value = "/app/data" }
      ]

      mountPoints = [
        {
          sourceVolume  = "efs-storage"
          containerPath = "/app/data"
          readOnly      = false
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_log_group.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "streamlit"
        }
      }
    }
  ])

  volume {
    name = "efs-storage"

    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.storage.id
      transit_encryption = "ENABLED"
    }
  }
}

#=========================================================
# ECS Cluster & Service
#=========================================================
resource "aws_ecs_cluster" "cluster" {
  name = "${var.project_name}-cluster"
}

resource "aws_ecs_service" "service" {
  name            = "${var.project_name}-service"
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.task.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  # Ensure mounts are created before starting Fargate instances
  depends_on = [aws_efs_mount_target.mount]
}
