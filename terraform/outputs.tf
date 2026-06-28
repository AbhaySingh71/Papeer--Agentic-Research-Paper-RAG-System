output "ecr_repository_url" {
  value       = aws_ecr_repository.repo.repository_url
  description = "The URL of the ECR repository"
}

output "ecs_cluster_name" {
  value       = aws_ecs_cluster.cluster.name
  description = "The name of the ECS cluster"
}

output "ecs_service_name" {
  value       = aws_ecs_service.service.name
  description = "The name of the ECS service"
}

output "efs_file_system_id" {
  value       = aws_efs_file_system.storage.id
  description = "The ID of the EFS File System"
}
