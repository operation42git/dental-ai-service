FROM python:3.11-slim

# 1. Basic OS deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    wget \
    && rm -rf /var/lib/apt/lists/*

# 2. Working dir for our service
WORKDIR /app

# 3. Clone the dental-pano-ai repo first
RUN git clone https://github.com/stmharry/dental-pano-ai.git /app/dental-pano-ai

# 4. Install dental-pano-ai dependencies via Poetry first
# Configure Poetry to install into system Python (no virtualenv) for Docker
RUN pip install --no-cache-dir "poetry==1.8.3" && \
    cd /app/dental-pano-ai && \
    poetry config virtualenvs.create false && \
    poetry install --no-root && \
    rm -rf /root/.cache/pypoetry

# 5. Install FastAPI service dependencies (after Poetry to ensure compatible versions)
# Also upgrade typing_extensions to ensure compatibility with pydantic
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt && \
    pip install --no-cache-dir --upgrade typing_extensions

# 6. Download and extract the model from original S3 into dental-pano-ai/models
RUN cd /app/dental-pano-ai && \
    mkdir -p models && \
    wget -O /tmp/models.tar.gz https://dental-pano-ai.s3.ap-southeast-1.amazonaws.com/models.tar.gz && \
    tar -xzf /tmp/models.tar.gz -C /app/dental-pano-ai && \
    rm /tmp/models.tar.gz

# 7. Copy our FastAPI service code
COPY app/ ./app

# 8. Create upload directory
RUN mkdir -p /app/uploads

# 9. Expose port and run the API
EXPOSE 8000

CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
