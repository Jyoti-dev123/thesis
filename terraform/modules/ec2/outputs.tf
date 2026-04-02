output "instance_id" {
  description = "EC2 instance ID of the inference server"
  value       = aws_instance.inference.id
}

output "public_ip" {
  description = "Public IP address of the EC2 inference server"
  value       = aws_instance.inference.public_ip
}

output "public_dns" {
  description = "Public DNS name of the EC2 inference server"
  value       = aws_instance.inference.public_dns
}

output "inference_url" {
  description = "URL of the /predict endpoint on the EC2 instance"
  value       = "http://${aws_instance.inference.public_dns}:8080/predict"
}

output "models_url" {
  description = "URL of the /models management endpoint on the EC2 instance"
  value       = "http://${aws_instance.inference.public_dns}:8080/models"
}

output "security_group_id" {
  description = "Security group ID attached to the EC2 instance"
  value       = aws_security_group.ec2_sg.id
}
