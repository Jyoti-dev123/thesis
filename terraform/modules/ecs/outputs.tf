output "cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.main.name
}

output "service_name" {
  description = "ECS service name"
  value       = aws_ecs_service.inference.name
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer"
  value       = aws_lb.ecs_alb.dns_name
}

output "alb_url" {
  description = "HTTP URL of the ALB inference endpoint"
  value       = "http://${aws_lb.ecs_alb.dns_name}/predict"
}
