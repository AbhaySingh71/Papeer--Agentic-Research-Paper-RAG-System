FROM python:3.11-slim

# Install uv using the official pre-built binary image
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set system environment variables for Streamlit and Python
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    STREAMLIT_SERVER_PORT=8501 \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0

# Install dependencies needed to build Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependency configuration files
COPY pyproject.toml uv.lock ./

# Install project dependencies using uv (frozen resolves dependencies from uv.lock)
RUN uv sync --frozen --no-install-project

# Copy all project files into the container
COPY . .

# Expose Streamlit default port
EXPOSE 8501

# Command to run Streamlit app using uv's managed environment
CMD ["uv", "run", "streamlit", "run", "app.py"]
