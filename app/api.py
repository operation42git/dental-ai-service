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
    debug: bool = Query(default=False, description="Enable debug mode to generate visualization images"),
    wait_for_result: bool = Query(default=False, description="Wait for result or return job ID immediately")
):
    """
    Submit dental image for AI analysis via RunPod serverless.
    
    - **s3_bucket**: S3 bucket name where results will be stored (required)
    - **s3_prefix**: Full S3 folder path where files will be uploaded (required)
    - **patient_name**: Optional patient identifier for logging
    - **debug**: If True, generates visualization images (semantic-segmentation.jpg and instance-detection.jpg)
    - **wait_for_result**: If False (default), returns job ID immediately (~100ms). If True, waits for completion (~15-30s)
    
    ## Response Modes:
    
    ### Fast mode (wait_for_result=false):
    Returns job ID immediately. Client polls `/job-status/{job_id}` for results.
    Response time: ~100-200ms
    
    ### Sync mode (wait_for_result=true):
    Waits for inference to complete and returns results.
    Response time: ~15-30s (much faster than local inference)
    """
    request_start_time = time.time()
    logger.info(f"=== NEW REQUEST STARTED ===")
    logger.info(f"File: {file.filename}, Patient: {patient_name}, Debug: {debug}, Wait: {wait_for_result}")
    
    try:
        # Save uploaded file
        suffix = Path(file.filename).suffix or ".png"
        file_id = uuid.uuid4().hex
        input_path = settings.UPLOAD_DIR / f"{file_id}{suffix}"
        
        with input_path.open("wb") as f:
            shutil.copyfileobj(file.file, f)
        
        logger.info(f"File saved: {input_path}")
        
        # Normalize S3 prefix
        s3_prefix_normalized = s3_prefix.strip()
        s3_prefix_normalized = re.sub(r'\s*/\s*', '/', s3_prefix_normalized)
        s3_prefix_normalized = re.sub(r'/+', '/', s3_prefix_normalized)
        s3_prefix_normalized = s3_prefix_normalized.lstrip('/')
        if s3_prefix_normalized and not s3_prefix_normalized.endswith('/'):
            s3_prefix_normalized += '/'
        
        # Upload image to S3 so RunPod can access it
        logger.info("Uploading image to S3...")
        from .s3_upload import upload_file_to_s3
        
        image_s3_key = f"{s3_prefix_normalized}input/{file_id}{suffix}"
        image_url = upload_file_to_s3(
            local_file=str(input_path),
            bucket_name=s3_bucket,
            s3_key=image_s3_key,
            region=os.getenv('AWS_REGION')
        )
        
        logger.info(f"Image uploaded to S3: {image_url}")
        
        # Submit job to RunPod
        logger.info("Submitting job to RunPod...")
        from .runpod_client import submit_inference_job, wait_for_completion
        
        job_result = submit_inference_job(
            image_url=image_url,
            s3_bucket=s3_bucket,
            s3_prefix=s3_prefix_normalized,
            debug=debug
        )
        job_id = job_result.get("id")
        
        logger.info(f"Job submitted to RunPod: {job_id}")
        
        # If client wants to wait, poll for results
        if wait_for_result:
            logger.info("Waiting for RunPod job completion...")
            result = await asyncio.to_thread(wait_for_completion, job_id, timeout=120)
            
            output = result.get("output", {})
            
            total_elapsed = time.time() - request_start_time
            logger.info(f"=== REQUEST COMPLETED in {total_elapsed:.2f}s ===")
            
            # RunPod now uploads directly to S3 and returns URLs
            response = {
                "message": "analysis complete",
                "job_id": job_id,
                "s3_bucket": output.get("s3_bucket", s3_bucket),
                "s3_prefix": output.get("s3_prefix", s3_prefix_normalized),
                "findings": output.get("findings", []),
                "num_findings": output.get("num_findings", 0),
                "csv_url": output.get("csv_url"),  # S3 URL to CSV file
                "debug_images": output.get("debug_images", {}),  # Dict of filename -> S3 URL
                "elapsed_time": total_elapsed
            }
            
            if patient_name:
                response["patient_name"] = patient_name
            
            return response
        else:
            # Return job ID immediately
            total_elapsed = time.time() - request_start_time
            logger.info(f"=== JOB SUBMITTED in {total_elapsed:.2f}s ===")
            
            response = {
                "message": "job submitted",
                "job_id": job_id,
                "status_url": f"/job-status/{job_id}",
                "elapsed_time": total_elapsed
            }
            
            if patient_name:
                response["patient_name"] = patient_name
            
            return response
        
    except Exception as e:
        total_elapsed = time.time() - request_start_time
        logger.error(f"=== REQUEST FAILED after {total_elapsed:.2f}s ===")
        logger.error(f"Error: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )


@app.get("/job-status/{job_id}")
async def get_job_status_endpoint(job_id: str):
    """
    Get the status of a submitted RunPod job.
    
    Returns:
        {
            "id": "job-id",
            "status": "IN_QUEUE" | "IN_PROGRESS" | "COMPLETED" | "FAILED",
            "output": {...}  # Only present when COMPLETED
        }
    """
    try:
        from .runpod_client import get_job_status
        result = get_job_status(job_id)
        return result
    except Exception as e:
        logger.error(f"Failed to get job status for {job_id}: {e}")
        logger.error(traceback.format_exc())
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )
