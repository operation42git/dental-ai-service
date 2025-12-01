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
import time

from .inference import run_dental_pano_ai
from .config import settings
from .s3_upload import upload_results_to_s3

# Set up logging with immediate flushing
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True  # Override any existing config
)
logger = logging.getLogger(__name__)
# Ensure logs are flushed immediately
import sys
sys.stdout.flush()
sys.stderr.flush()

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


# Add middleware to log all requests
@app.middleware("http")
async def log_requests(request, call_next):
    import time
    start_time = time.time()
    print(f"[REQUEST] {request.method} {request.url.path} - Started", flush=True)
    logger.info(f"Request: {request.method} {request.url.path}")
    try:
        response = await call_next(request)
        process_time = time.time() - start_time
        print(f"[REQUEST] {request.method} {request.url.path} - Completed in {process_time:.2f}s - Status: {response.status_code}", flush=True)
        logger.info(f"Request completed: {request.method} {request.url.path} - {process_time:.2f}s - {response.status_code}")
        return response
    except Exception as e:
        process_time = time.time() - start_time
        print(f"[REQUEST] {request.method} {request.url.path} - ERROR after {process_time:.2f}s: {e}", flush=True)
        logger.error(f"Request error: {request.method} {request.url.path} - {process_time:.2f}s - {e}")
        raise


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


@app.get("/test")
def test_endpoint():
    """Simple test endpoint to verify the app is responding."""
    return {
        "message": "App is running",
        "timestamp": time.time(),
        "models_loaded": MODELS_AVAILABLE and (model_manager.is_loaded() if model_manager else False)
    }


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
    request_start_time = time.time()
    print(f"[ANALYZE] === NEW REQUEST STARTED ===", flush=True)
    print(f"[ANALYZE] File: {file.filename}, Size: {file.size if hasattr(file, 'size') else 'unknown'}", flush=True)
    print(f"[ANALYZE] Debug: {debug}, Patient: {patient_name}", flush=True)
    print(f"[ANALYZE] S3 bucket: {s3_bucket}, Prefix: {s3_prefix}", flush=True)
    logger.info(f"=== NEW REQUEST STARTED ===")
    logger.info(f"File: {file.filename}, Size: {file.size if hasattr(file, 'size') else 'unknown'}")
    logger.info(f"Debug mode: {debug}, Patient: {patient_name}")
    logger.info(f"S3 bucket: {s3_bucket}, Prefix: {s3_prefix}")
    
    try:
        # Save uploaded file to disk
        print(f"[ANALYZE] Saving uploaded file to disk...", flush=True)
        logger.info("Saving uploaded file to disk...")
        suffix = Path(file.filename).suffix or ".png"
        file_id = uuid.uuid4().hex
        input_path = settings.UPLOAD_DIR / f"{file_id}{suffix}"
        print(f"[ANALYZE] Input file path: {input_path}", flush=True)
        logger.info(f"Input file path: {input_path}")

        with input_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        
        file_size = input_path.stat().st_size
        print(f"[ANALYZE] File saved successfully, size: {file_size} bytes", flush=True)
        logger.info(f"File saved successfully, size: {file_size} bytes")

        print(f"[ANALYZE] Starting inference for file: {file.filename}, debug={debug}", flush=True)
        models_loaded_status = MODELS_AVAILABLE and (model_manager.is_loaded() if model_manager else False)
        print(f"[ANALYZE] Models loaded: {models_loaded_status}", flush=True)
        logger.info(f"Starting inference for file: {file.filename}, debug={debug}")
        logger.info(f"Models loaded: {models_loaded_status}")
        
        if not models_loaded_status:
            print(f"[ANALYZE] WARNING: Models not loaded yet, this will trigger lazy loading (slower)", flush=True)
            logger.warning("Models not loaded yet, this will trigger lazy loading (slower)")
        
        # Run inference in a thread pool to avoid blocking the event loop
        # AI inference can take several minutes, so we run it asynchronously
        print(f"[ANALYZE] Starting inference in background thread...", flush=True)
        logger.info("Starting inference in background thread...")
        inference_start_time = time.time()
        try:
            result = await asyncio.to_thread(run_dental_pano_ai, str(input_path), debug)
            inference_elapsed = time.time() - inference_start_time
            print(f"[ANALYZE] Inference completed successfully in {inference_elapsed:.2f} seconds", flush=True)
            logger.info(f"Inference completed successfully in {inference_elapsed:.2f} seconds")
        except Exception as inference_error:
            inference_elapsed = time.time() - inference_start_time
            print(f"[ANALYZE] ERROR: Inference failed after {inference_elapsed:.2f} seconds: {inference_error}", flush=True)
            logger.error(f"Inference failed after {inference_elapsed:.2f} seconds: {inference_error}")
            logger.error(traceback.format_exc())
            raise
        
        logger.info("Normalizing S3 prefix...")
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
        
        logger.info(f"Uploading {len(result['output_files'])} files to S3...")
        logger.info(f"S3 prefix: {s3_prefix_normalized}")
        upload_start_time = time.time()
        try:
            s3_urls = upload_results_to_s3(
                local_files=result["output_files"],
                bucket_name=s3_bucket,
                s3_prefix=s3_prefix_normalized,
                output_dir=result["output_dir"],
                region=os.getenv('AWS_REGION')
            )
            upload_elapsed = time.time() - upload_start_time
            logger.info(f"S3 upload completed in {upload_elapsed:.2f} seconds, uploaded {len(s3_urls)} files")
        except Exception as upload_error:
            upload_elapsed = time.time() - upload_start_time
            logger.error(f"S3 upload failed after {upload_elapsed:.2f} seconds: {upload_error}")
            logger.error(traceback.format_exc())
            raise
        
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
        
        total_elapsed = time.time() - request_start_time
        logger.info(f"=== REQUEST COMPLETED SUCCESSFULLY in {total_elapsed:.2f} seconds ===")
        return response
        
    except Exception as e:
        total_elapsed = time.time() - request_start_time
        logger.error(f"=== REQUEST FAILED after {total_elapsed:.2f} seconds ===")
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )
