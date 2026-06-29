import os
import subprocess
import sys

def load_env(filepath=".env"):
    """Simple parser to load env variables from a local .env file."""
    env_vars = {}
    if not os.path.exists(filepath):
        print(f"Error: {filepath} file not found. Please create it first.")
        sys.exit(1)
    
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                env_vars[key] = val
    return env_vars

def main():
    # 1. Load keys from the secure local .env file
    env_data = load_env(".env")
    
    aws_access_key = env_data.get("AWS_ACCESS_KEY_ID")
    aws_secret_key = env_data.get("AWS_SECRET_ACCESS_KEY")
    aws_region = env_data.get("AWS_DEFAULT_REGION", "us-east-1")
    
    if not aws_access_key or not aws_secret_key:
        print("Error: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY must be set in your .env file.")
        sys.exit(1)
        
    # 2. Check if the terraform directory exists
    if not os.path.isdir("terraform"):
        print("Error: 'terraform' directory not found.")
        sys.exit(1)

    # 3. Setup environment variables for Terraform
    env = os.environ.copy()
    env["AWS_ACCESS_KEY_ID"] = aws_access_key
    env["AWS_SECRET_ACCESS_KEY"] = aws_secret_key
    env["AWS_DEFAULT_REGION"] = aws_region

    # Map application variables to TF_VAR_* environment variables to satisfy Terraform inputs
    env["TF_VAR_groq_api_key"] = env_data.get("GROQ_API_KEY", "")
    env["TF_VAR_google_api_key"] = env_data.get("GOOGLE_API_KEY", "")
    env["TF_VAR_cohere_api_key"] = env_data.get("COHERE_API_KEY", "")
    env["TF_VAR_tavily_api_key"] = env_data.get("TAVILY_API_KEY", "")
    env["TF_VAR_qdrant_url"] = env_data.get("QDRANT_URL", "")
    env["TF_VAR_qdrant_api_key"] = env_data.get("QDRANT_API_KEY", "")
    env["TF_VAR_langchain_tracing_v2"] = env_data.get("LANGCHAIN_TRACING_V2", "false")
    env["TF_VAR_langchain_api_key"] = env_data.get("LANGCHAIN_API_KEY", "")
    env["TF_VAR_langchain_project"] = env_data.get("LANGCHAIN_PROJECT", "papeer")
    env["TF_VAR_langchain_endpoint"] = env_data.get("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

    # 4. Verify Terraform is installed
    try:
        subprocess.run(["terraform", "--version"], check=True, capture_output=True, text=True)
    except FileNotFoundError:
        print("Error: Terraform CLI was not found in your system PATH.")
        sys.exit(1)

    # 5. Run Terraform Destroy with -auto-approve
    print("Destroying all AWS Infrastructure (Teardown to prevent billing)...")
    try:
        subprocess.run(
            ["terraform", "destroy", "-auto-approve"],
            cwd="terraform",
            env=env,
            check=True
        )
        print("SUCCESS: All AWS resources destroyed successfully. Your billing has been stopped.")
    except subprocess.CalledProcessError as e:
        print(f"Error during 'terraform destroy': {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
