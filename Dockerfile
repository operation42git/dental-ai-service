FROM python:3.11-slim

# 1. Basic OS deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 2. Working dir for our service
WORKDIR /app

# 3. Install Python deps for the FastAPI service
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Clone the dental-pano-ai repo
RUN git clone https://github.com/stmharry/dental-pano-ai.git /app/dental-pano-ai

# 5. Install its dependencies via Poetry or pip
# The README uses Poetry, but installing via pip from pyproject is usually fine.
# If needed, you can switch to Poetry-based install here.
RUN pip install --no-cache-dir "poetry==1.8.3" && \
    cd /app/dental-pano-ai && \
    poetry install --no-root && \
    rm -rf /root/.cache/pypoetry

# 6. Download and extract the model from your S3/Spaces into dental-pano-ai/models
# You must pass MODEL_URL at build time:
#   docker build --build-arg MODEL_URL=https://your-bucket/models.tar.gz ...
ARG MODEL_URL
RUN test -n "$MODEL_URL" || (echo "MODEL_URL build arg is required" && false) && \
    cd /app/dental-pano-ai && \
    mkdir -p models && \
    wget -O /tmp/models.tar.gz "$MODEL_URL" && \
    tar -xzf /tmp/models.tar.gz -C /app/dental-pano-ai && \
    rm /tmp/models.tar.gz

# 7. Copy our FastAPI service code
COPY app/ ./app

# 8. Create upload directory
RUN mkdir -p /app/uploads

# 9. Expose port and run the API
EXPOSE 8000

CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
