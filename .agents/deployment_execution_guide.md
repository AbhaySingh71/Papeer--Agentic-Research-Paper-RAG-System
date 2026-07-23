# 📋 Complete Chronological Deployment Guide for Papeer (AWS Fargate & CI/CD)

This guide walks you through deploying Papeer on AWS ECS Fargate, fully managed via Terraform infrastructure provisioning and automated GitHub Actions CI/CD workflows.

Since you are bypassing the local installation of the AWS CLI, you can choose between two methods to connect AWS to Terraform: the **Python wrapper script** (simplest, uses boto3) or **Temporary environment variables**.

---

## 🏗️ Step 1: Pre-requisites
Ensure you have the following installed:
1. **Terraform CLI** (Installed and configured in your System PATH)
2. **Git** (Configured with your GitHub repository)
3. **Python 3** (To run the helper deployment script)

---

## 🔑 Step 2: Configure Credentials & Deploy (Choose Option A or B)

### Option A: The Python Script Wrapper (Recommended)
This method uses the secure [deploy.py](file:///C:/Users/abhay/Desktop/papeer/deploy.py) script. It reads your credentials from your local gitignored `.env` file and executes Terraform automatically.

1. Open your local [.env](file:///C:/Users/abhay/Desktop/papeer/.env) file and add your AWS credentials:
   ```text
   AWS_ACCESS_KEY_ID=YOUR_AWS_ACCESS_KEY_ID
   AWS_SECRET_ACCESS_KEY=YOUR_AWS_SECRET_ACCESS_KEY
   AWS_DEFAULT_REGION=us-east-1
   ```

3. Run the secure deployment script:
   ```powershell
   python deploy.py
   ```
   *The script will automatically authenticate, run `terraform init`, and run `terraform apply` with all variable values passed.*

---

### Option B: Temporary Environment Variables (CLI alternative)
If you prefer not to use Python, you can inject the credentials directly into your active PowerShell session.

1. Open PowerShell and run the following to authenticate the terminal session:
   ```powershell
   $env:AWS_ACCESS_KEY_ID="YOUR_AWS_ACCESS_KEY_ID"
   $env:AWS_SECRET_ACCESS_KEY="YOUR_SECRET_ACCESS_KEY"
   $env:AWS_DEFAULT_REGION="us-east-1"
   ```

2. Navigate to the `terraform` directory:
   ```powershell
   cd terraform
   ```

3. Initialize and apply Terraform (replace placeholders with your actual API keys):
   ```powershell
   terraform init

   terraform apply `
     -var="groq_api_key=your_groq_key" `
     -var="google_api_key=your_google_key" `
     -var="cohere_api_key=your_cohere_key" `
     -var="tavily_api_key=your_tavily_key" `
     -var="qdrant_url=your_qdrant_url" `
     -var="qdrant_api_key=your_qdrant_key" `
     -var="langchain_tracing_v2=true" `
     -var="langchain_api_key=lsv2_p_..."
   ```

---

## 🤖 Step 3: Configure GitHub Secrets
Store your AWS credentials securely in GitHub so the Action workflow can access your AWS resources:

1. Open your repository on GitHub.
2. Go to **Settings** -> **Secrets and variables** -> **Actions** -> click **New repository secret**.
3. Create the following secrets:
   * **Name**: `AWS_ACCESS_KEY_ID` | **Value**: *(Your AWS access key)*
   * **Name**: `AWS_SECRET_ACCESS_KEY` | **Value**: *(Your AWS secret key)*

---

## 📤 Step 4: Commit & Push to Trigger CI/CD
Trigger the deployment pipeline by pushing your files (including `Dockerfile` and `.github/workflows/deploy.yml`) to GitHub:

1. Make sure you are in the root directory:
   ```powershell
   cd C:\Users\abhay\Desktop\papeer
   ```

2. Commit and push the code:
   ```powershell
   git add .
   git commit -m "chore: setup deployment and CI/CD pipelines"
   git push origin main
   ```

3. Open the **Actions** tab in your GitHub repository to monitor the live deployment logs. Once the job succeeds, the container will be running on AWS.

---

## 🕸️ Step 5: Test the App on AWS
To check the running instance and obtain its URL:

1. Log into your **AWS Console**.
2. Navigate to **Elastic Container Service (ECS)** -> **Clusters** -> click **papeer-cluster**.
3. Click on the **Tasks** tab.
4. Click on the running Task ID.
5. Under the **Network** configuration, copy the **Public IP**.
6. Access your deployed app in your browser at:
   ```http
   http://<YOUR_PUBLIC_IP>:8501
   ```

---

## 🧹 Step 6: Teardown (Avoid Charges)
When you are done testing and want to destroy all AWS resources to avoid billing:

1. Go into the `terraform` folder:
   ```powershell
   cd terraform
   ```

2. Destroy all resources:
   ```powershell
   terraform destroy
   ```
   *Type `yes` and press Enter to confirm.*
