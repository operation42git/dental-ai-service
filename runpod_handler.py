"""
RunPod serverless handler for dental AI inference.

This file should be deployed to RunPod as a separate container.
It receives image URLs, runs inference, and returns results.
"""
import runpod
import requests
import tempfile
import os
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
    RunPod handler function.
    
    Input:
        {
            "image_url": "https://...",
            "s3_bucket": "bucket-name",
            "s3_prefix": "path/to/folder/",
            "debug": false
        }
    
    Output:
        {
            "findings": [
                {"fdi": "11", "finding": "CARIES", "score": 0.95},
                ...
            ],
            "csv_data": "file_name,fdi,finding,score\n...",
            "debug_images": {...}  # if debug=True
        }
    """
    try:
        input_data = event.get("input", {})
        
        # Validate required fields
        if "image_url" not in input_data:
            return {
                "error": "Missing required field: image_url",
                "expected_input": {
                    "image_url": "https://...",
                    "s3_bucket": "bucket-name (optional)",
                    "s3_prefix": "path/to/folder/ (optional)",
                    "debug": False
                }
            }
        
        image_url = input_data["image_url"]
        s3_bucket = input_data.get("s3_bucket")
        s3_prefix = input_data.get("s3_prefix", "")
        debug = input_data.get("debug", False)
        
        logger.info(f"Processing image: {image_url}")
        logger.info(f"S3 bucket: {s3_bucket}, prefix: {s3_prefix}")
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
        logger.info(f"CSV generated: {csv_path}")
        
        # Upload results to S3 if bucket is provided
        if s3_bucket and s3_prefix:
            logger.info(f"Uploading results to S3: {s3_bucket}/{s3_prefix}")
            import boto3
            import re
            
            # Parse bucket and endpoint from URL if needed
            bucket_name = s3_bucket
            endpoint_url = None
            
            # Check if it's a DigitalOcean Spaces URL
            do_spaces_match = re.match(r'https?://([^.]+)\.([^.]+)\.digitaloceanspaces\.com', s3_bucket)
            if do_spaces_match:
                bucket_name = do_spaces_match.group(1)
                region = do_spaces_match.group(2)
                endpoint_url = f"https://{region}.digitaloceanspaces.com"
            else:
                region = os.getenv('AWS_REGION', 'us-east-1')
            
            # Get credentials from environment
            aws_access_key = os.getenv('AWS_ACCESS_KEY_ID') or os.getenv('DO_SPACES_ACCESS_KEY')
            aws_secret_key = os.getenv('AWS_SECRET_ACCESS_KEY') or os.getenv('DO_SPACES_SECRET_KEY')
            
            if not aws_access_key or not aws_secret_key:
                logger.warning("S3 credentials not found, skipping upload")
                # Return findings without S3 URLs
                return {
                    "findings": [
                        {
                            "fdi": entry.fdi,
                            "finding": entry.finding.value,
                            "score": entry.score
                        }
                        for entry in finding_entries
                    ],
                    "num_findings": len(finding_entries),
                    "warning": "S3 credentials not provided, results not uploaded"
                }
            
            # Create S3 client
            s3_client = boto3.client(
                's3',
                region_name=region,
                endpoint_url=endpoint_url if endpoint_url else None,
                aws_access_key_id=aws_access_key,
                aws_secret_access_key=aws_secret_key
            )
            
            # Upload CSV
            csv_s3_key = f"{s3_prefix}{csv_path.name}"
            logger.info(f"Uploading CSV to {csv_s3_key}")
            s3_client.upload_file(
                str(csv_path),
                bucket_name,
                csv_s3_key,
                ExtraArgs={'ACL': 'public-read'}
            )
            
            # Generate CSV URL
            if endpoint_url:
                csv_url = f"{endpoint_url}/{bucket_name}/{csv_s3_key}"
            else:
                csv_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{csv_s3_key}"
            
            logger.info(f"CSV uploaded: {csv_url}")
            
            # Upload debug images if requested
            debug_image_urls = {}
            if debug:
                logger.info("Uploading debug images...")
                for img_file in image_output_dir.glob("*.jpg"):
                    img_s3_key = f"{s3_prefix}{img_file.stem}/{img_file.name}"
                    logger.info(f"Uploading {img_file.name} to {img_s3_key}")
                    s3_client.upload_file(
                        str(img_file),
                        bucket_name,
                        img_s3_key,
                        ExtraArgs={'ACL': 'public-read'}
                    )
                    
                    if endpoint_url:
                        img_url = f"{endpoint_url}/{bucket_name}/{img_s3_key}"
                    else:
                        img_url = f"https://{bucket_name}.s3.{region}.amazonaws.com/{img_s3_key}"
                    
                    debug_image_urls[img_file.name] = img_url
                
                logger.info(f"Uploaded {len(debug_image_urls)} debug images")
            
            # Prepare output with S3 URLs
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
                "num_findings": int(len(finding_entries)),
                "csv_url": csv_url,
                "s3_bucket": bucket_name,
                "s3_prefix": s3_prefix
            }
            
            if debug_image_urls:
                output["debug_images"] = debug_image_urls
            
            logger.info("Results uploaded to S3 successfully!")
        else:
            # No S3 bucket provided, return data directly
            logger.info("No S3 bucket provided, returning data directly")
            with open(csv_path, 'r') as f:
                csv_data = f.read()
            
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

