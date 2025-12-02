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
        input_data = event["input"]
        image_url = input_data["image_url"]
        s3_bucket = input_data.get("s3_bucket")
        s3_prefix = input_data.get("s3_prefix", "")
        debug = input_data.get("debug", False)
        
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
        csv_path = output_dir / "findings.csv"
        assessment = FindingAssessment(
            name=Path(tmp_path).stem,
            entries=finding_entries
        )
        assessment.to_csv(csv_path)
        
        # Read CSV content
        with open(csv_path, 'r') as f:
            csv_data = f.read()
        
        # Prepare output
        output = {
            "findings": [
                {
                    "fdi": entry.fdi,
                    "finding": entry.finding.value,
                    "score": entry.score
                }
                for entry in finding_entries
            ],
            "csv_data": csv_data,
            "num_findings": len(finding_entries)
        }
        
        # Include debug images if requested
        if debug:
            debug_images = {}
            for img_file in image_output_dir.glob("*.jpg"):
                # In production, you'd upload these to S3 and return URLs
                # For now, just note they exist
                debug_images[img_file.name] = f"s3://{s3_bucket}/{s3_prefix}debug/{img_file.name}"
            output["debug_images"] = debug_images
            logger.info(f"Debug images: {list(debug_images.keys())}")
        
        # Clean up temp files
        try:
            os.unlink(tmp_path)
        except:
            pass
        
        logger.info("Inference completed successfully!")
        return output
        
    except Exception as e:
        logger.error(f"Error during inference: {e}")
        import traceback
        traceback.print_exc()
        return {"error": str(e), "traceback": traceback.format_exc()}


# Start the RunPod serverless handler
runpod.serverless.start({"handler": handler})

