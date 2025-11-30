# Dental AI Inference Service

Small HTTP service that wraps the **dental-pano-ai** project and exposes it as a REST API.

- Original repo: https://github.com/stmharry/dental-pano-ai
- Endpoint: `POST /analyze-ortopan`
- Framework: FastAPI
- Model weights are **not stored in git**; they are downloaded during Docker build.

## Build

You must provide a URL to `models.tar.gz` (hosted on your S3/DO Spaces, or the original S3):
Original S3 -https://dental-pano-ai.s3.ap-southeast-1.amazonaws.com/models.tar.gz
Original git - https://github.com/stmharry/dental-pano-ai

```bash
docker build \
  --build-arg MODEL_URL=https://your-bucket-or-space/models.tar.gz \
  -t your-docker-user/dental-ai-service:latest .


