"""
Build Docker container images and push them to Amazon ECR.

Builds:
  1. Lambda inference image  → ECR lambda repository
  2. ECS inference image     → ECR ecs repository
  3. EC2  inference image    → same ECR ecs repository (re-tagged :ec2)

The EC2 deployment reuses the ECS image (both backend/ecs/app.py).
Pushing a fresh tag and running `systemctl restart aaas-inference` on
the instance is all that is needed to deploy a new version to EC2.

Usage:
    python scripts/build_and_push.py \
        --lambda-repo <lambda_ecr_url> \
        --ecs-repo    <ecs_ecr_url>    \
        --region      us-east-1

Get repo URLs from Terraform:
    cd terraform && terraform output lambda_ecr_repository_url
    cd terraform && terraform output ecs_ecr_repository_url
"""

import os
import sys
import argparse
import subprocess
import shlex

import boto3
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

BASE_DIR        = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LAMBDA_CONTEXT  = os.path.join(BASE_DIR, "backend", "lambda")
ECS_CONTEXT     = os.path.join(BASE_DIR, "backend", "ecs")


def run(cmd: str, cwd: str = None) -> None:
    """Run a shell command and raise on failure."""
    print(f"  $ {cmd}")
    result = subprocess.run(shlex.split(cmd), cwd=cwd)
    if result.returncode != 0:
        print(f"ERROR: command failed with exit code {result.returncode}")
        sys.exit(result.returncode)


def ecr_login(region: str, account_id: str) -> None:
    """Authenticate Docker to ECR."""
    ecr = boto3.client("ecr", region_name=region)
    token = ecr.get_authorization_token()
    endpoint = token["authorizationData"][0]["proxyEndpoint"]
    import base64
    creds = base64.b64decode(
        token["authorizationData"][0]["authorizationToken"]
    ).decode()
    _, password = creds.split(":", 1)
    run(f"docker login --username AWS --password-stdin {endpoint}",
        cwd=BASE_DIR)
    # NOTE: password piped via stdin is handled by Docker CLI; pass via env
    print(f"  Logged in to {endpoint}")


def build_and_push(context_dir: str, repo_url: str, tag: str = "latest") -> None:
    image_tag = f"{repo_url}:{tag}"
    print(f"\nBuilding image: {image_tag}")
    run(f"docker build -t {image_tag} {context_dir}")
    print(f"Pushing image: {image_tag}")
    run(f"docker push {image_tag}")
    print(f"Done: {image_tag}")


def main():
    parser = argparse.ArgumentParser(description="Build and push Docker images to ECR.")
    parser.add_argument("--lambda-repo", required=True,
                        help="ECR repo URL for Lambda container (terraform output: lambda_ecr_repository_url)")
    parser.add_argument("--ecs-repo",    required=True,
                        help="ECR repo URL for ECS container (terraform output: ecs_ecr_repository_url)")
    parser.add_argument("--tag",    default="latest", help="Docker image tag")
    parser.add_argument("--region", default=os.environ.get("AWS_REGION", "us-east-1"))
    parser.add_argument("--account-id", default=os.environ.get("AWS_ACCOUNT_ID", ""))
    args = parser.parse_args()

    region     = args.region
    account_id = args.account_id

    print("=" * 60)
    print("Build & Push Docker Images to Amazon ECR")
    print("=" * 60)

    # ECR authentication
    print("\n[1/3] Authenticating with Amazon ECR...")
    registry = f"{account_id}.dkr.ecr.{region}.amazonaws.com"
    ecr_password_cmd = f"aws ecr get-login-password --region {region}"
    login_cmd = f"docker login --username AWS --password-stdin {registry}"
    ps_cmd = f"{ecr_password_cmd} | {login_cmd}"
    result = subprocess.run(ps_cmd, shell=True)
    if result.returncode != 0:
        print("ERROR: ECR login failed. Check AWS credentials.")
        sys.exit(1)
    print("ECR login successful.")

    # Build and push Lambda image
    print("\n[2/3] Building and pushing Lambda inference image...")
    build_and_push(LAMBDA_CONTEXT, args.lambda_repo, args.tag)

    # Build and push ECS image — also used by EC2 (same Dockerfile)
    print("\n[3/3] Building and pushing ECS/EC2 inference image...")
    build_and_push(ECS_CONTEXT, args.ecs_repo, args.tag)
    # Tag the same image as :ec2 so the EC2 instance can pull it explicitly
    ec2_tag = f"{args.ecs_repo}:ec2"
    run(f"docker tag {args.ecs_repo}:{args.tag} {ec2_tag}")
    run(f"docker push {ec2_tag}")

    print("\n" + "=" * 60)
    print("All images pushed successfully.")
    print("=" * 60)
    print(f"\nLambda image:  {args.lambda_repo}:{args.tag}")
    print(f"ECS image:     {args.ecs_repo}:{args.tag}")
    print(f"EC2 image:     {ec2_tag}  (same as ECS, re-tagged)")
    print(
        "\nTo deploy the new image to EC2, SSH in and run:\n"
        "  sudo systemctl restart aaas-inference\n"
        "(The systemd unit will pull the latest :ec2 image automatically.)"
    )
    print(
        "\nTo update the Lambda function:\n"
        f"  aws lambda update-function-code \\\n"
        f"    --function-name <lambda_function_name> \\\n"
        f"    --image-uri {args.lambda_repo}:{args.tag}"
    )


if __name__ == "__main__":
    main()
