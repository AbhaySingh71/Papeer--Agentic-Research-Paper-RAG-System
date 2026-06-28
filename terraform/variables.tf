variable "aws_region" {
  type        = string
  description = "AWS Region to deploy resources"
  default     = "us-east-1"
}

variable "project_name" {
  type        = string
  description = "Name of the project"
  default     = "papeer"
}

variable "groq_api_key" {
  type        = string
  description = "API Key for Groq"
  sensitive   = true
  default     = ""
}

variable "google_api_key" {
  type        = string
  description = "API Key for Google Gemini"
  sensitive   = true
  default     = ""
}

variable "cohere_api_key" {
  type        = string
  description = "API Key for Cohere"
  sensitive   = true
  default     = ""
}

variable "tavily_api_key" {
  type        = string
  description = "API Key for Tavily"
  sensitive   = true
  default     = ""
}

variable "qdrant_url" {
  type        = string
  description = "URL for Qdrant Cloud Cluster"
  default     = ""
}

variable "qdrant_api_key" {
  type        = string
  description = "API Key for Qdrant Cloud"
  sensitive   = true
  default     = ""
}

variable "langchain_tracing_v2" {
  type        = string
  description = "Enable LangChain Tracing"
  default     = "false"
}

variable "langchain_api_key" {
  type        = string
  description = "API Key for LangChain/LangSmith"
  sensitive   = true
  default     = ""
}

variable "langchain_project" {
  type        = string
  description = "Project name in LangChain"
  default     = "papeer"
}

variable "langchain_endpoint" {
  type        = string
  description = "LangChain API Endpoint"
  default     = "https://api.smith.langchain.com"
}
