# Production Deployment Guide

## Environment Variables (Secrets)

Set these as **secrets** in your production environment (e.g., Docker secrets, Kubernetes secrets, or environment variables):

### Required for S3/Spaces Upload

**For DigitalOcean Spaces:**
```bash
DO_SPACES_ACCESS_KEY=your_access_key_here
DO_SPACES_SECRET_KEY=your_secret_key_here
DO_SPACES_REGION=fra1  # Optional, can be inferred from bucket URL
```

**OR for AWS S3:**
```bash
AWS_ACCESS_KEY_ID=your_access_key_here
AWS_SECRET_ACCESS_KEY=your_secret_key_here
AWS_REGION=us-east-1  # Your AWS region
```

**Note:** You can use either set of variables. The code checks both.

### Optional Configuration Variables

These have defaults but can be overridden if needed:

```bash
# Base directory (defaults to /app in Docker)
BASE_DIR=/app

# Dental Pano AI repository directory (defaults to {BASE_DIR}/dental-pano-ai)
DENTAL_PANO_AI_REPO_DIR=/app/dental-pano-ai

# Upload directory for temporary files (defaults to {BASE_DIR}/uploads)
UPLOAD_DIR=/app/uploads

# Python executable (defaults to "python")
PYTHON_EXECUTABLE=python

# Poetry executable (defaults to "poetry")
POETRY_EXECUTABLE=poetry
```

## Docker Build

Build the Docker image (models are downloaded automatically from the original S3):

```bash
docker build -t your-registry/dental-ai-service:latest .
```

**Note:** The Dockerfile is configured to download models from: https://dental-pano-ai.s3.ap-southeast-1.amazonaws.com/models.tar.gz

## Docker Run

Run the container with environment variables:

```bash
docker run -d \
  -p 8000:8000 \
  -e DO_SPACES_ACCESS_KEY=your_key \
  -e DO_SPACES_SECRET_KEY=your_secret \
  -e DO_SPACES_REGION=fra1 \
  your-registry/dental-ai-service:latest
```

Or use a `.env` file:
```bash
docker run -d \
  -p 8000:8000 \
  --env-file .env.production \
  your-registry/dental-ai-service:latest
```

## Kubernetes Deployment

Example secret:
```yaml
apiVersion: v1
kind: Secret
metadata:
  name: dental-ai-secrets
type: Opaque
stringData:
  DO_SPACES_ACCESS_KEY: your_access_key
  DO_SPACES_SECRET_KEY: your_secret_key
  DO_SPACES_REGION: fra1
```

Example deployment:
```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: dental-ai-service
spec:
  replicas: 1
  selector:
    matchLabels:
      app: dental-ai-service
  template:
    metadata:
      labels:
        app: dental-ai-service
    spec:
      containers:
      - name: dental-ai-service
        image: your-registry/dental-ai-service:latest
        ports:
        - containerPort: 8000
        env:
        - name: DO_SPACES_ACCESS_KEY
          valueFrom:
            secretKeyRef:
              name: dental-ai-secrets
              key: DO_SPACES_ACCESS_KEY
        - name: DO_SPACES_SECRET_KEY
          valueFrom:
            secretKeyRef:
              name: dental-ai-secrets
              key: DO_SPACES_SECRET_KEY
        - name: DO_SPACES_REGION
          valueFrom:
            secretKeyRef:
              name: dental-ai-secrets
              key: DO_SPACES_REGION
```

## Health Check

The service exposes a health check endpoint:
```bash
curl http://your-server:8000/health
```

Expected response:
```json
{"status": "ok"}
```

## API Usage

Example API call:
```bash
curl -X POST "http://your-server:8000/analyze-ortopan?s3_bucket=https://kisdentalchart.fra1.digitaloceanspaces.com&s3_prefix=Test/photos/Patient%20Name/2024-01-15/&debug=false" \
  -F "file=@image.jpg"
```

## Security Considerations

1. **Never commit secrets** - Use environment variables or secrets management
2. **Use IAM roles** - If running on AWS/DO infrastructure, prefer IAM roles over access keys
3. **Restrict S3 permissions** - Give the service only the minimum permissions needed (read models, write results)
4. **Use HTTPS** - Always use HTTPS in production
5. **Rate limiting** - Consider adding rate limiting for production use
6. **Monitoring** - Set up logging and monitoring for the service

## DigitalOcean App Platform Configuration

### Timeout Settings

**IMPORTANT:** AI inference can take 5-15 minutes per image. You **must** configure DigitalOcean App Platform to allow long-running requests:

1. **In DigitalOcean App Platform Dashboard:**
   - Go to your app → Settings → App Spec
   - Find your service component
   - Add or update the `http_port` configuration with timeout settings

2. **Recommended App Spec Configuration:**
   ```yaml
   name: dental-ai-service
   services:
   - name: api
     http_port: 8000
     health_check:
       http_path: /health
     timeout_seconds: 900  # 15 minutes
     instance_count: 1
     instance_size_slug: basic-xxs  # Adjust based on your needs
   ```

3. **Alternative: Via Environment Variables:**
   - Some platforms allow setting `UVICORN_TIMEOUT_KEEP_ALIVE` or similar
   - Check DigitalOcean documentation for timeout configuration options

4. **If timeouts persist:**
   - Consider using a job queue (e.g., Celery, RQ) for long-running inference tasks
   - Implement a polling endpoint to check job status
   - Or use DigitalOcean's background worker component type

## Troubleshooting

### 504 Gateway Timeout
- **Cause:** Request exceeded platform timeout (usually 60-300 seconds default)
- **Solution:** 
  - Configure timeout settings in DigitalOcean App Platform (see above)
  - Inference typically takes 5-15 minutes, so timeout must be at least 900 seconds (15 minutes)
  - Check application logs to see if inference is actually running or if it's failing early

### Credentials not found
- Verify environment variables are set correctly
- Check that secrets are mounted/available in the container
- Ensure variable names match exactly (case-sensitive)

### Model files not found
- Verify MODEL_URL was provided during Docker build
- Check that models.tar.gz was downloaded and extracted correctly
- Verify models directory exists at `/app/dental-pano-ai/models/`

### S3 upload fails
- Verify S3/Spaces credentials are correct
- Check bucket name and region
- Ensure the service has write permissions to the bucket
- Verify the s3_prefix path is correct (no leading/trailing spaces)

