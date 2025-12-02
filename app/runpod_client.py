"""RunPod serverless client for dental AI inference."""
import os
import requests
import time
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
RUNPOD_ENDPOINT_ID = os.getenv("RUNPOD_ENDPOINT_ID")


def get_api_url() -> str:
    """Get the RunPod API URL."""
    if not RUNPOD_ENDPOINT_ID:
        raise ValueError("RUNPOD_ENDPOINT_ID environment variable not set")
    return f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}"


def submit_inference_job(image_url: str, s3_bucket: str, s3_prefix: str, debug: bool = False) -> Dict:
    """
    Submit an inference job to RunPod serverless endpoint.
    
    Args:
        image_url: URL to the image file (must be accessible by RunPod)
        s3_bucket: S3 bucket for storing results
        s3_prefix: S3 prefix for storing results
        debug: Enable debug mode for visualization images
    
    Returns:
        {
            "id": "job-id",
            "status": "IN_QUEUE" | "IN_PROGRESS" | "COMPLETED" | "FAILED"
        }
    """
    if not RUNPOD_API_KEY:
        raise ValueError("RUNPOD_API_KEY environment variable not set")
    
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "input": {
            "image_url": image_url,
            "s3_bucket": s3_bucket,
            "s3_prefix": s3_prefix,
            "debug": debug
        }
    }
    
    api_url = get_api_url()
    logger.info(f"Submitting job to RunPod: {api_url}/run")
    
    response = requests.post(
        f"{api_url}/run",
        headers=headers,
        json=payload,
        timeout=30
    )
    response.raise_for_status()
    result = response.json()
    
    logger.info(f"Job submitted successfully: {result.get('id')}")
    return result


def get_job_status(job_id: str) -> Dict:
    """
    Get the status of a RunPod job.
    
    Returns:
        {
            "id": "job-id",
            "status": "IN_QUEUE" | "IN_PROGRESS" | "COMPLETED" | "FAILED",
            "output": {...}  # Only present when COMPLETED
        }
    """
    if not RUNPOD_API_KEY:
        raise ValueError("RUNPOD_API_KEY environment variable not set")
    
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
    }
    
    api_url = get_api_url()
    response = requests.get(
        f"{api_url}/status/{job_id}",
        headers=headers,
        timeout=30
    )
    response.raise_for_status()
    return response.json()


def wait_for_completion(job_id: str, timeout: int = 120, poll_interval: int = 2) -> Dict:
    """
    Poll for job completion.
    
    Args:
        job_id: The job ID to poll
        timeout: Maximum time to wait in seconds (default: 120s)
        poll_interval: Time between polls in seconds (default: 2s)
    
    Returns:
        Job result when completed
    
    Raises:
        TimeoutError: If job doesn't complete within timeout
        RuntimeError: If job fails
    """
    start_time = time.time()
    logger.info(f"Waiting for job {job_id} to complete (timeout: {timeout}s)...")
    
    while time.time() - start_time < timeout:
        result = get_job_status(job_id)
        status = result.get("status")
        
        logger.debug(f"Job {job_id} status: {status}")
        
        if status == "COMPLETED":
            elapsed = time.time() - start_time
            logger.info(f"Job {job_id} completed in {elapsed:.2f}s")
            return result
        elif status == "FAILED":
            error = result.get("error", "Unknown error")
            logger.error(f"Job {job_id} failed: {error}")
            raise RuntimeError(f"Job failed: {error}")
        
        time.sleep(poll_interval)
    
    elapsed = time.time() - start_time
    logger.error(f"Job {job_id} timed out after {elapsed:.2f}s")
    raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")


def cancel_job(job_id: str) -> Dict:
    """
    Cancel a running job.
    
    Args:
        job_id: The job ID to cancel
    
    Returns:
        Cancellation result
    """
    if not RUNPOD_API_KEY:
        raise ValueError("RUNPOD_API_KEY environment variable not set")
    
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
    }
    
    api_url = get_api_url()
    response = requests.post(
        f"{api_url}/cancel/{job_id}",
        headers=headers,
        timeout=30
    )
    response.raise_for_status()
    
    logger.info(f"Job {job_id} cancelled")
    return response.json()

