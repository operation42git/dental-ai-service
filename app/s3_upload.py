"""S3 upload utilities for storing analysis results."""
import boto3
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import os
import re

# Load .env file if it exists (from project root)
try:
    from dotenv import load_dotenv
    # Try multiple locations: project root (parent of app directory) and current working directory
    project_root = Path(__file__).parent.parent
    env_paths = [
        project_root / '.env',  # Project root
        Path.cwd() / '.env',    # Current working directory
        Path('.env'),           # Relative to CWD
    ]
    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(dotenv_path=env_path, override=True)
            break
    else:
        # If no .env found, try default behavior (searches upward from CWD)
        load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, that's okay


def _parse_bucket_and_endpoint(bucket_input: str, region: Optional[str] = None) -> Tuple[str, str, str]:
    """
    Parse bucket name and endpoint from input.
    Supports both AWS S3 and DigitalOcean Spaces.
    
    Args:
        bucket_input: Bucket name or full URL (e.g., "my-bucket" or "https://my-bucket.fra1.digitaloceanspaces.com")
        region: Optional region override
    
    Returns:
        Tuple of (bucket_name, endpoint_url, region)
    """
    # Check if it's a DigitalOcean Spaces URL
    do_spaces_match = re.match(r'https?://([^.]+)\.([^.]+)\.digitaloceanspaces\.com', bucket_input)
    if do_spaces_match:
        bucket_name = do_spaces_match.group(1)
        detected_region = do_spaces_match.group(2)
        endpoint_url = f"https://{detected_region}.digitaloceanspaces.com"
        return bucket_name, endpoint_url, detected_region
    
    # Check if it's an AWS S3 URL
    aws_s3_match = re.match(r'https?://([^.]+)\.s3(?:\.([^.]+))?\.amazonaws\.com', bucket_input)
    if aws_s3_match:
        bucket_name = aws_s3_match.group(1)
        detected_region = aws_s3_match.group(2) or region or os.getenv('AWS_REGION', 'us-east-1')
        # AWS S3 doesn't need explicit endpoint_url for standard regions
        return bucket_name, None, detected_region
    
    # Assume it's just a bucket name
    bucket_name = bucket_input
    # Check if DigitalOcean Spaces is being used (check env var or default to AWS)
    spaces_region = region or os.getenv('DO_SPACES_REGION')
    if spaces_region:
        endpoint_url = f"https://{spaces_region}.digitaloceanspaces.com"
        return bucket_name, endpoint_url, spaces_region
    else:
        # Default to AWS S3
        aws_region = region or os.getenv('AWS_REGION', 'us-east-1')
        return bucket_name, None, aws_region


def upload_results_to_s3(
    local_files: List[str],
    bucket_name: str,
    s3_prefix: str,  # Should include trailing /
    output_dir: str,
    region: str = None
) -> Dict[str, str]:
    """
    Upload result files to S3-compatible storage (AWS S3 or DigitalOcean Spaces) and return their URLs.
    Preserves subdirectory structure from output_dir.
    
    Args:
        local_files: List of local file paths to upload
        bucket_name: Bucket name or full URL (e.g., "my-bucket" or "https://my-bucket.fra1.digitaloceanspaces.com")
        s3_prefix: S3 prefix/folder path (e.g., "patients/john-doe/2024-01-15/")
        output_dir: Base output directory path (used to calculate relative paths)
        region: Optional region override
    
    Returns:
        Dict mapping local file paths to S3 URLs
    """
    # Parse bucket name and endpoint
    actual_bucket_name, endpoint_url, actual_region = _parse_bucket_and_endpoint(bucket_name, region)
    
    # Get credentials (check both AWS and DO Spaces variable names)
    access_key = os.getenv('AWS_ACCESS_KEY_ID') or os.getenv('DO_SPACES_ACCESS_KEY')
    secret_key = os.getenv('AWS_SECRET_ACCESS_KEY') or os.getenv('DO_SPACES_SECRET_KEY')
    
    # Create S3 client with appropriate endpoint
    if endpoint_url:
        # DigitalOcean Spaces or custom endpoint - credentials are required
        if not access_key or not secret_key:
            # Check what variables are actually set (for debugging)
            found_vars = []
            if os.getenv('AWS_ACCESS_KEY_ID'):
                found_vars.append('AWS_ACCESS_KEY_ID (set)')
            if os.getenv('DO_SPACES_ACCESS_KEY'):
                found_vars.append('DO_SPACES_ACCESS_KEY (set)')
            if os.getenv('AWS_SECRET_ACCESS_KEY'):
                found_vars.append('AWS_SECRET_ACCESS_KEY (set)')
            if os.getenv('DO_SPACES_SECRET_KEY'):
                found_vars.append('DO_SPACES_SECRET_KEY (set)')
            
            # Check if .env file exists in common locations
            project_root = Path(__file__).parent.parent
            env_locations = [
                project_root / '.env',
                Path.cwd() / '.env',
            ]
            existing_env = [str(p) for p in env_locations if p.exists()]
            
            error_msg = (
                "DigitalOcean Spaces credentials not found. "
                "Please set DO_SPACES_ACCESS_KEY and DO_SPACES_SECRET_KEY environment variables, "
                "or AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY.\n"
                f"Found environment variables: {', '.join(found_vars) if found_vars else 'none'}\n"
                f"Checked .env file locations: {', '.join(existing_env) if existing_env else 'none found'}\n"
                f"Project root: {project_root}\n"
                f"Current working directory: {Path.cwd()}\n"
                f"Make sure your .env file is in the project root ({project_root}) and contains the credentials."
            )
            raise RuntimeError(error_msg)
        s3_client = boto3.client(
            's3',
            endpoint_url=endpoint_url,
            region_name=actual_region,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key
        )
        # Generate URLs for DigitalOcean Spaces
        base_url = f"https://{actual_bucket_name}.{actual_region}.digitaloceanspaces.com"
    else:
        # AWS S3 - credentials can come from env vars, IAM role, or credentials file
        client_kwargs = {'region_name': actual_region}
        if access_key and secret_key:
            # Explicitly provide credentials if available
            client_kwargs['aws_access_key_id'] = access_key
            client_kwargs['aws_secret_access_key'] = secret_key
        s3_client = boto3.client('s3', **client_kwargs)
        base_url = f"https://{actual_bucket_name}.s3.{actual_region}.amazonaws.com"
    
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
            s3_client.upload_file(str(local_file), actual_bucket_name, s3_key)
            
            # Generate S3 URL
            s3_url = f"{base_url}/{s3_key}"
            s3_urls[local_file] = s3_url
        except Exception as e:
            # If upload fails for one file, raise error with context
            raise RuntimeError(
                f"Failed to upload {file_path.name} to bucket {actual_bucket_name} at {s3_key}: {str(e)}"
            ) from e
    
    return s3_urls

