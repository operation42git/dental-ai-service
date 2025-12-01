from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import JSONResponse
from pathlib import Path
import shutil
import uuid
import os
import re
import asyncio
import logging
import traceback

from .inference import run_dental_pano_ai
from .config import settings
from .s3_upload import upload_results_to_s3

# Set up logging
logger = logging.getLogger(__name__)

# Import model_manager with error handling
try:
    from .models import model_manager
    MODELS_AVAILABLE = True
except Exception as e:
    logger.error(f"Failed to import model_manager: {e}")
    logger.error(traceback.format_exc())
    model_manager = None
    MODELS_AVAILABLE = False

app = FastAPI(title="Dental AI Inference Service")


async def _load_models_background():
    """Load models in the background (non-blocking)."""
    if not MODELS_AVAILABLE or not model_manager:
        logger.error("Model manager not available. Models will be loaded on first request (slower).")
        return
    
    logger.info("Starting background model loading...")
    try:
        # Run model loading in a thread pool since it's CPU/memory intensive
        # This prevents blocking the event loop
        await asyncio.to_thread(model_manager.load_models, debug=True)
        logger.info("AI models loaded successfully in background!")
    except Exception as e:
        logger.error(f"Failed to load models in background: {e}")
        logger.error(traceback.format_exc())
        logger.warning("Models will be loaded on first request (slower)")


@app.on_event("startup")
async def startup_event():
    """Validate configuration and start background model loading."""
    try:
        logger.info("Starting application startup...")
        settings.validate()
        logger.info("Configuration validated successfully")
        
        # Start model loading in the background (non-blocking)
        # This allows the app to start immediately and pass health checks
        # Models will be ready when the first request comes in (or shortly after)
        asyncio.create_task(_load_models_background())
        logger.info("Application startup complete. Models loading in background...")
        
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        logger.error(traceback.format_exc())
        # Re-raise to fail fast if it's a critical error
        raise


@app.get("/health")
def health():
    """
    Health check endpoint.
    Returns immediately - models may still be loading in background.
    """
    models_loaded = False
    if MODELS_AVAILABLE and model_manager:
        models_loaded = model_manager.is_loaded()
    
    status = {
        "status": "ok",
        "models_loaded": models_loaded,
        "models_available": MODELS_AVAILABLE,
    }
    return status


@app.post("/analyze-ortopan")
async def analyze_ortopan(
    file: UploadFile = File(...),
    s3_bucket: str = Query(..., description="S3 bucket name for storing results"),
    s3_prefix: str = Query(..., description="Full S3 folder path (e.g., 'patients/john-doe/2024-01-15/')"),
    patient_name: str = Query(None, description="Optional patient name for logging"),
    debug: bool = Query(default=False, description="Enable debug mode to generate visualization images")
):
    """
    Accept a DPR/ortopan image upload and run the dental-pano-ai inference.
    Results are uploaded to the specified S3 prefix and S3 URLs are returned.
    
    - **s3_bucket**: S3 bucket name where results will be stored (required)
    - **s3_prefix**: Full S3 folder path where files will be uploaded (required)
    - **patient_name**: Optional patient identifier for logging
    - **debug**: If True, generates visualization images (semantic-segmentation.jpg and instance-detection.jpg)
    """
    # Save uploaded file to disk
    suffix = Path(file.filename).suffix or ".png"
    file_id = uuid.uuid4().hex
    input_path = settings.UPLOAD_DIR / f"{file_id}{suffix}"

    with input_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        # Run inference in a thread pool to avoid blocking the event loop
        # AI inference can take several minutes, so we run it asynchronously
        result = await asyncio.to_thread(run_dental_pano_ai, str(input_path), debug)
        
        # Normalize S3 prefix:
        # 1. Strip leading/trailing whitespace
        # 2. Remove spaces around slashes
        # 3. Normalize multiple slashes to single slash
        # 4. Ensure it ends with /
        s3_prefix_normalized = s3_prefix.strip()
        # Remove spaces around slashes and normalize slashes
        s3_prefix_normalized = re.sub(r'\s*/\s*', '/', s3_prefix_normalized)  # Remove spaces around /
        s3_prefix_normalized = re.sub(r'/+', '/', s3_prefix_normalized)  # Normalize multiple / to single /
        # Remove leading slash if present (we'll add it at the end)
        s3_prefix_normalized = s3_prefix_normalized.lstrip('/')
        # Ensure it ends with /
        if s3_prefix_normalized and not s3_prefix_normalized.endswith('/'):
            s3_prefix_normalized += '/'
        
        # Upload results to S3
        s3_urls = upload_results_to_s3(
            local_files=result["output_files"],
            bucket_name=s3_bucket,
            s3_prefix=s3_prefix_normalized,
            output_dir=result["output_dir"],
            region=os.getenv('AWS_REGION')
        )
        
        # Map relative file paths to S3 URLs for easier access
        # Preserves subdirectory structure (e.g., "image-name/semantic-segmentation.jpg")
        file_urls = {}
        output_dir_path = Path(result["output_dir"]).resolve()
        for local_file, s3_url in s3_urls.items():
            file_path = Path(local_file).resolve()
            try:
                relative_path = file_path.relative_to(output_dir_path)
                file_urls[relative_path.as_posix()] = s3_url
            except ValueError:
                # Fallback to filename if path calculation fails
                file_urls[file_path.name] = s3_url
        
        response = {
            "message": "analysis complete",
            "s3_bucket": s3_bucket,
            "s3_prefix": s3_prefix_normalized,
            "files": file_urls,  # Dict of filename -> S3 URL
            "debug": debug,
        }
        
        if patient_name:
            response["patient_name"] = patient_name
        
        return response
        
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )
