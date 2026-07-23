# 🚀 Ultimate AWS + GitHub Actions CI/CD + Terraform Deployment Plan for Papeer

This document is your master blueprint. It combines manual setup steps, automated GitHub Actions CI/CD, and **Terraform (Infrastructure as Code)**. 

Yes, when you are ready to implement this, **I can write all the Terraform files (`main.tf`, `variables.tf`, etc.) for you!** For now, here is the complete plan on how they work together.

---

## 🏗️ Architecture & Component Overview

```mermaid
graph TD
    User([User Browser]) -->|HTTP: 8501| StreamlitContainer[Streamlit Container (ECS Fargate)]
    StreamlitContainer -->|Mount /app/data| EFSVolume[(AWS EFS File System)]
    
    subgraph Terraform
        TF[Terraform Code] -->|Provisions automatically| AWS[ECS, EFS, VPC, Security Groups]
    end

    subgraph GitHub CI/CD Pipeline
        Developer[Developer Git Push] -->|Triggers| GHA[GitHub Actions]
        GHA -->|Builds Container & Pushes| ECR[AWS ECR Registry]
        GHA -->|Deploys Version| StreamlitContainer
    end
```

---

## 💰 2-Hour Cost Estimate (US-East-1 Region)
By using Fargate in a public subnet directly (bypassing Load Balancers and NAT gateways), the cost is extremely minimal:
1. **ECS Fargate Task (0.5 vCPU, 1 GB RAM)**: ~$0.025 / hour × 2 hours = **$0.05**
2. **AWS EFS Storage** (SQLite is ~5 MB): **$0.00**
3. **AWS ECR Container Registry** (Image storage): **$0.00**
4. **Total AWS Cost: ~$0.05 USD**

---

## 📦 Step 1: Create Docker Files Locally
Package the application inside your local project directory (`C:\Users\abhay\Desktop\papeer`).

1.### Proposed `Dockerfile` Structure
```dockerfile
# Use a slim, stable Python base image
FROM python:3.11-slim

# Install uv using the official pre-built binary image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set system-level environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Install system dependencies needed for compiling python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency configuration files
COPY pyproject.toml uv.lock ./

# Install project dependencies using uv (frozen resolves dependencies from uv.lock)
RUN uv sync --frozen --no-install-project

# Copy the rest of the application code
COPY . .

# Expose port 8501 for Streamlit
EXPOSE 8501

# Run the streamlit application using uv virtual environment
CMD ["uv", "run", "streamlit", "run", "app.py"]
```

2. Create a `.dockerignore`:
   ```text
   .venv/
   __pycache__/
   .git/
   .agents/
   .antigravitycli/
   .deepeval/
   embedding_cache/
   *.db-shm
   *.db-wal
   ```

---

## ⚙️ Step 2: Provision Infrastructure using Terraform
Terraform allows us to write configuration files to launch EFS, ECR, Task Definitions, and ECS Services in seconds, instead of clicking around the AWS Console interface.

*When you are ready, I will generate these files for you. Here is how we run them:*

1. Install **Terraform** on your computer.
2. We will create a folder named `terraform/` in your repository containing:
   * `main.tf`: Defines AWS provider, VPC, ECS Cluster, ECR Repository, EFS File System, Security Groups, and ECS Task/Service definitions.
   * `variables.tf`: Configures variables like AWS region and task ports.
3. Run these command in your terminal inside the `terraform/` folder:
   ```bash
   # Initialize Terraform and download AWS plug-ins
   terraform init

   # View what AWS resources will be created
   terraform plan

   # Provision all AWS resources (type 'yes' when prompted)
   terraform apply
   ```
4. After running `terraform apply`, Terraform will print out the ECR URI and the Public IP of your running Streamlit container.

---

## 📤 Step 3: Initial Build and Push to ECR
Once Terraform creates the ECR repository:
1. Run the AWS login command:
   ```bash
   aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com
   ```
2. Build, tag, and push your docker container to your new ECR repository:
   ```bash
   docker build -t papeer .
   docker tag papeer:latest <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com/papeer:latest
   docker push <aws_account_id>.dkr.ecr.us-east-1.amazonaws.com/papeer:latest
   ```

---

## 🤖 Step 6: Set up GitHub Actions CI/CD (Continuous Deployment)
Automate updates so every `git push` automatically redeploys.

### 1. Configure GitHub Secret Settings
Go to your **GitHub Repository** -> **Settings** -> **Secrets and variables** -> **Actions** -> Add:
* `AWS_ACCESS_KEY_ID`: Your AWS credential ID.
* `AWS_SECRET_ACCESS_KEY`: Your AWS secret credential key.

*(Note: We do not need to manually commit a static JSON file for the task definition anymore; the pipeline dynamically downloads the active task definition from your AWS ECS cluster automatically!)*

### 2. Add the Workflow configuration
Create a file at `.github/workflows/deploy.yml` with this content:
```yaml
name: Deploy to Amazon ECS

on:
  push:
    branches:
      - main

env:
  AWS_REGION: us-east-1
  ECR_REPOSITORY: papeer
  ECS_SERVICE: papeer-service
  ECS_CLUSTER: papeer-cluster
  CONTAINER_NAME: papeer-container

jobs:
  deploy:
    name: Build & Deploy
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Configure AWS Credentials
        uses: aws-actions/configure-aws-credentials@v4
        with:
          aws-access-key-id: ${{ secrets.AWS_ACCESS_KEY_ID }}
          aws-secret-access-key: ${{ secrets.AWS_SECRET_ACCESS_KEY }}
          aws-region: ${{ env.AWS_REGION }}

      - name: Log in to Amazon ECR
        id: login-ecr
        uses: aws-actions/amazon-ecr-login@v2

      - name: Build, tag, and push image to Amazon ECR
        id: build-image
        env:
          ECR_REGISTRY: ${{ steps.login-ecr.outputs.registry }}
          IMAGE_TAG: ${{ github.sha }}
        run: |
          docker build -t $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG .
          docker push $ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG
          echo "image=$ECR_REGISTRY/$ECR_REPOSITORY:$IMAGE_TAG" >> $GITHUB_OUTPUT

      - name: Download Active Task Definition
        run: |
          aws ecs describe-task-definition --task-definition ${{ env.ECR_REPOSITORY }}-task --query taskDefinition > task-definition.json

      - name: Fill in the new image ID in the Amazon ECS task definition
        id: render-task-def
        uses: aws-actions/amazon-ecs-render-task-definition@v1
        with:
          task-definition: task-definition.json
          container-name: ${{ env.CONTAINER_NAME }}
          image: ${{ steps.build-image.outputs.image }}

      - name: Deploy Amazon ECS task definition
        uses: aws-actions/amazon-ecs-deploy-task-definition@v2
        with:
          task-definition: ${{ steps.render-task-def.outputs.task-definition }}
          service: ${{ env.ECS_SERVICE }}
          cluster: ${{ env.ECS_CLUSTER }}
          wait-for-service-stability: true
```

---

## 🧹 Step 5: Delete All Resources (Teardown via Terraform)
To completely delete all AWS resources and stop billing, you do not need to delete items one by one in the UI. 

Since everything was provisioned using Terraform, you simply run a single command in your `terraform/` directory:

```bash
# Deletes all provisioned resources (EFS, ECR, Task Definitions, ECS Clusters, and security groups)
terraform destroy
```
*Confirm with `yes` when prompted, and Terraform will clean up everything.*
