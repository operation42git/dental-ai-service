# Dental AI Inference Service

Small HTTP service that wraps the **dental-pano-ai** project and exposes it as a REST API.

- Original repo: https://github.com/stmharry/dental-pano-ai
- Endpoint: `POST /analyze-ortopan`
- Framework: FastAPI
- Model weights are **not stored in git**; they are downloaded during Docker build or manually for local development.

## Local Development

### Prerequisites

- Python 3.11+
- Git
- Poetry (for installing dental-pano-ai dependencies)
- wget or curl (for downloading models)

### Setup Steps

1. **Clone and navigate to the repository:**
   ```bash
   git clone <this-repo>
   cd dental-ai-service
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   
   # On Windows:
   venv\Scripts\activate
   
   # On Linux/Mac:
   source venv/bin/activate
   ```

3. **Install FastAPI dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Clone the dental-pano-ai repository:**
   ```bash
   git clone https://github.com/stmharry/dental-pano-ai.git dental-pano-ai
   ```

5. **Install dental-pano-ai dependencies:**
   ```bash
   cd dental-pano-ai
   pip install poetry
   poetry install --no-root
   cd ..
   ```

6. **Download and extract models:**
   ```bash
   # Download models
   wget https://dental-pano-ai.s3.ap-southeast-1.amazonaws.com/models.tar.gz
   # Or on Windows without wget, use PowerShell:
   # Invoke-WebRequest -Uri https://dental-pano-ai.s3.ap-southeast-1.amazonaws.com/models.tar.gz -OutFile models.tar.gz
   
   # Extract to dental-pano-ai directory
   cd dental-pano-ai
   tar -xzf ../models.tar.gz
   # Or on Windows, use 7-Zip or similar tool
   cd ..
   
   # Clean up
   rm models.tar.gz  # or del models.tar.gz on Windows
   ```

7. **Configure environment variables (optional):**
   
   Create a `.env` file in the project root (optional, defaults work for local dev):
   ```bash
   cp .env.example .env
   ```
   
   Edit `.env` if needed. The defaults should work for local development:
   - `DENTAL_PANO_AI_REPO_DIR=./dental-pano-ai`
   - `UPLOAD_DIR=./uploads`
   - `PYTHON_EXECUTABLE=python`

8. **Run the service:**
   ```bash
   uvicorn app.api:app --host 0.0.0.0 --port 8000 --reload
   ```

9. **Test the service:**
   ```bash
   # Health check
   curl http://localhost:8000/health
   
   # Analyze an image (replace test-image.png with your image)
   curl -X POST http://localhost:8000/analyze-ortopan \
     -F "file=@test-image.png"
   ```

   Or visit http://localhost:8000/docs for the interactive API documentation.

### Environment Variables

The service supports the following environment variables:

- `BASE_DIR` - Base directory (defaults to `/app` for Docker)
- `DENTAL_PANO_AI_REPO_DIR` - Path to dental-pano-ai repository (defaults to `{BASE_DIR}/dental-pano-ai`)
- `UPLOAD_DIR` - Directory for temporary uploads (defaults to `{BASE_DIR}/uploads`)
- `PYTHON_EXECUTABLE` - Python executable command (defaults to `python`)

For local development, you typically only need to set:
- `DENTAL_PANO_AI_REPO_DIR=./dental-pano-ai` (or absolute path)

## Docker Build

You must provide a URL to `models.tar.gz` (hosted on your S3/DO Spaces, or the original S3):
- Original S3: https://dental-pano-ai.s3.ap-southeast-1.amazonaws.com/models.tar.gz
- Original git: https://github.com/stmharry/dental-pano-ai

```bash
docker build \
  --build-arg MODEL_URL=https://your-bucket-or-space/models.tar.gz \
  -t your-docker-user/dental-ai-service:latest .
```

### Run Docker Container

```bash
docker run -p 8000:8000 your-docker-user/dental-ai-service:latest
```

## API Endpoints

- `GET /health` - Health check endpoint
- `POST /analyze-ortopan` - Upload and analyze a dental panoramic image
  - Request: multipart/form-data with `file` field
  - Response: JSON with analysis results including output directory and files

## Notes

- Model files are large and not stored in git
- The service requires the dental-pano-ai repository to be cloned locally
- Upload directory is created automatically if it doesn't exist
- Results are stored in `{DENTAL_PANO_AI_REPO_DIR}/results/` directory
