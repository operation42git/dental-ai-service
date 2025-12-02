"""
RunPod serverless handler for dental AI inference - Simplified version.

This handler:
1. Receives image URL
2. Runs AI inference
3. Uploads results to temp S3 folder (auto-expires after 24 hours)
4. Returns findings + CSV data + S3 URLs for debug images

Input:
{
    "image_url": "https://...",
    "debug": false
}

Output:
{
    "findings": [...],
    "csv_data": "...",
    "debug_image_urls": {
        "semantic-segmentation.jpg": "https://s3.../temp/job-123/semantic.jpg",
        "instance-detection.jpg": "https://s3.../temp/job-123/instance.jpg"
    }
}
"""
import runpod
import requests
import tempfile
import os
import base64
from pathlib import Path
import sys
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add dental-pano-ai to path
DENTAL_PANO_AI_DIR = os.getenv("DENTAL_PANO_AI_DIR", "/app/dental-pano-ai")
sys.path.insert(0, DENTAL_PANO_AI_DIR)

try:
    from main import (
        SemanticSegmentationModule,
        InstanceDetectionModule,
        PostProcessingModule,
        FindingAssessment
    )
    import numpy as np
    from PIL import Image
    
    logger.info("Successfully imported dental-pano-ai modules")
except ImportError as e:
    logger.error(f"Failed to import dental-pano-ai modules: {e}")
    raise

# Load models once at container startup
logger.info("Loading AI models...")
MODELS_DIR = Path(DENTAL_PANO_AI_DIR) / "models"

try:
    semseg_module = SemanticSegmentationModule(
        config_path=str(MODELS_DIR / "deeplab" / "config.yaml"),
        weights_path=str(MODELS_DIR / "deeplab" / "model.pth"),
        debug=True  # Always load with debug capability
    )
    logger.info("DeepLab model loaded")
    
    insdet_module = InstanceDetectionModule(
        config_path=str(MODELS_DIR / "yolo" / "config.yaml"),
        weights_path=str(MODELS_DIR / "yolo" / "model.pt"),
        debug=True  # Always load with debug capability
    )
    logger.info("YOLO model loaded")
    
    postproc_module = PostProcessingModule()
    logger.info("Post-processing module loaded")
    
    logger.info("All models loaded successfully!")
except Exception as e:
    logger.error(f"Failed to load models: {e}")
    raise


def handler(event):
    """
    RunPod handler function - simplified version.
    
    Input:
        {
            "image_url": "https://...",
            "debug": false (optional)
        }
    
    Output:
        {
            "findings": [{"fdi": "11", "finding": "CARIES", "score": 0.95}, ...],
            "csv_data": "file_name,fdi,finding,score\n...",
            "num_findings": 15,
            "debug_image_urls": {
                "semantic-segmentation.jpg": "https://s3.../temp/job-123/semantic.jpg",
                "instance-detection.jpg": "https://s3.../temp/job-123/instance.jpg"
            } (if debug=true)
        }
    """
    try:
        input_data = event.get("input", {})
        
        # Get job ID from event for temp folder naming
        job_id = event.get("id", "unknown")
        
        # Validate required fields
        if "image_url" not in input_data:
            return {
                "error": "Missing required field: image_url",
                "expected_input": {
                    "image_url": "https://...",
                    "debug": False
                }
            }
        
        image_url = input_data["image_url"]
        debug = input_data.get("debug", False)
        
        logger.info(f"Job ID: {job_id}")
        logger.info(f"Processing image: {image_url}")
        logger.info(f"Debug mode: {debug}")
        
        # Download image
        logger.info("Downloading image...")
        response = requests.get(image_url, timeout=60)
        response.raise_for_status()
        
        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
        
        logger.info(f"Image downloaded to {tmp_path}")
        
        # Load image
        logger.info("Loading image...")
        image_pil = Image.open(tmp_path).convert("RGB")
        image = np.asarray(image_pil)
        
        logger.info(f"Image loaded: {image.shape}")
        
        # Create output directory
        output_dir = Path(tempfile.mkdtemp())
        image_output_dir = output_dir / "results"
        image_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Run inference
        logger.info("Running semantic segmentation...")
        semseg_pred = semseg_module(image, output_dir=image_output_dir)
        logger.info("Semantic segmentation completed")
        
        # Clear memory
        import gc
        import torch
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        gc.collect()
        
        logger.info("Running instance detection...")
        insdet_pred = insdet_module(image, output_dir=image_output_dir)
        logger.info("Instance detection completed")
        
        logger.info("Running post-processing...")
        finding_entries = postproc_module(semseg_pred, insdet_pred)
        logger.info(f"Post-processing completed: {len(finding_entries)} findings")
        
        # Generate CSV
        logger.info("Generating CSV...")
        csv_path = output_dir / "findings.csv"
        assessment = FindingAssessment(
            name=Path(tmp_path).stem,
            entries=finding_entries
        )
        assessment.to_csv(csv_path)
        
        # Read CSV content
        with open(csv_path, 'r') as f:
            csv_data = f.read()
        
        logger.info("Preparing output...")
        
        # Prepare output - return data directly
        # Convert NumPy types to Python types for JSON serialization
        output = {
            "findings": [
                {
                    "fdi": str(entry.fdi),
                    "finding": str(entry.finding.value),
                    "score": float(entry.score)  # Convert numpy.float32 to Python float
                }
                for entry in finding_entries
            ],
            "csv_data": csv_data,
            "num_findings": int(len(finding_entries))
        }
        
        # Upload debug images to temp S3 if requested
        if debug:
            logger.info("Uploading debug images to temp S3...")
            
            # Get S3 configuration from environment
            s3_bucket_url = os.getenv('S3_BUCKET')
            s3_temp_prefix = os.getenv('S3_TEMP_PREFIX', 'temp/')
            
            if not s3_bucket_url:
                logger.warning("S3_BUCKET not set, returning images as base64 fallback")
                # Fallback to base64
                debug_images = {}
                for img_file in image_output_dir.glob("*.jpg"):
                    with open(img_file, 'rb') as f:
                        img_data = f.read()
                        img_base64 = base64.b64encode(img_data).decode('utf-8')
                        debug_images[img_file.name] = f"data:image/jpeg;base64,{img_base64}"
                output["debug_image_urls"] = debug_images
            else:
                # Upload to S3
                import boto3
                import re
                
                # Parse bucket and endpoint
                bucket_name = s3_bucket_url
                endpoint_url = None
                
                do_spaces_match = re.match(r'https?://([^.]+)\.([^.]+)\.digitaloceanspaces\.com', s3_bucket_url)
                if do_spaces_match:
                    bucket_name = do_spaces_match.group(1)
                    region = do_spaces_match.group(2)
                    endpoint_url = f"https://{region}.digitaloceanspaces.com"
                else:
                    region = os.getenv('AWS_REGION', 'us-east-1')
                
                # Get credentials
                aws_access_key = os.getenv('AWS_ACCESS_KEY_ID')
                aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY')
                
                if not aws_access_key or not aws_secret_key:
                    logger.warning("S3 credentials not found, skipping upload")
                else:
                    # Create S3 client
                    s3_client = boto3.client(
                        's3',
                        region_name=region,
                        endpoint_url=endpoint_url if endpoint_url else None,
                        aws_access_key_id=aws_access_key,
                        aws_secret_access_key=aws_secret_key
                    )
                    
                    # Upload debug images to temp folder
                    debug_image_urls = {}
                    for img_file in image_output_dir.glob("*.jpg"):
                        # Upload to temp/job-{id}/filename.jpg
                        s3_key = f"{s3_temp_prefix}job-{job_id}/{img_file.name}"
                        logger.info(f"Uploading {img_file.name} to {s3_key}")
                        
                        s3_client.upload_file(
                            str(img_file),
                            bucket_name,
                            s3_key,
                            ExtraArgs={'ACL': 'public-read'}
                        )
                        
                        # Generate public URL
                        if endpoint_url:
                            img_url = f"{endpoint_url}/{bucket_name}/{s3_key}"
                        else:
                            img_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{s3_key}"
                        
                        debug_image_urls[img_file.name] = img_url
                    
                    output["debug_image_urls"] = debug_image_urls
                    logger.info(f"Uploaded {len(debug_image_urls)} debug images to temp S3")
        
        # Clean up temp files
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        logger.info("Handler completed successfully!")
        return output
        
    except Exception as e:
        logger.error(f"Error during inference: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "traceback": traceback.format_exc()}


# Start the RunPod serverless handler
runpod.serverless.start({"handler": handler})

