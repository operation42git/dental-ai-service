"""S3 upload utilities for storing analysis results."""
import boto3
from pathlib import Path
from typing import List, Dict
import os


def upload_results_to_s3(
    local_files: List[str],
    bucket_name: str,
    s3_prefix: str,  # Should include trailing /
    output_dir: str,
    region: str = None
) -> Dict[str, str]:
    """
    Upload result files to S3 and return their URLs.
    Preserves subdirectory structure from output_dir.
    
    Args:
        local_files: List of local file paths to upload
        bucket_name: S3 bucket name
        s3_prefix: S3 prefix/folder path (e.g., "patients/john-doe/2024-01-15/")
        output_dir: Base output directory path (used to calculate relative paths)
        region: AWS region (defaults to env var or us-east-1)
    
    Returns:
        Dict mapping local file paths to S3 URLs
    """
    s3_client = boto3.client('s3', region_name=region or os.getenv('AWS_REGION', 'us-east-1'))
    output_dir_path = Path(output_dir).resolve()
    
    s3_urls = {}
    for local_file in local_files:
        file_path = Path(local_file).resolve()
        
        # Calculate relative path from output_dir to preserve subdirectory structure
        try:
            relative_path = file_path.relative_to(output_dir_path)
        except ValueError:
            # If file is not under output_dir, just use filename
            relative_path = Path(file_path.name)
        
        # Convert to forward slashes for S3 (works on all platforms)
        s3_key = f"{s3_prefix}{relative_path.as_posix()}"
        
        try:
            s3_client.upload_file(str(local_file), bucket_name, s3_key)
            
            # Generate S3 URL
            s3_url = f"https://{bucket_name}.s3.{s3_client.meta.region_name}.amazonaws.com/{s3_key}"
            s3_urls[local_file] = s3_url
        except Exception as e:
            # If upload fails for one file, raise error with context
            raise RuntimeError(
                f"Failed to upload {file_path.name} to S3 bucket {bucket_name} at {s3_key}: {str(e)}"
            ) from e
    
    return s3_urls

