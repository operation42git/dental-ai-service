from fastapi import FastAPI, UploadFile, File, Query
from fastapi.responses import JSONResponse
from pathlib import Path
import shutil
import uuid
import os

from .inference import run_dental_pano_ai
from .config import settings
from .s3_upload import upload_results_to_s3

app = FastAPI(title="Dental AI Inference Service")


@app.on_event("startup")
async def startup_event():
    """Validate configuration on startup."""
    settings.validate()


@app.get("/health")
def health():
    return {"status": "ok"}


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
        # Run inference
        result = run_dental_pano_ai(str(input_path), debug=debug)
        
        # Normalize S3 prefix (ensure it ends with /)
        s3_prefix_normalized = s3_prefix.rstrip('/') + '/'
        
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
