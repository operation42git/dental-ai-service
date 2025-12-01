import subprocess
import os
from pathlib import Path
import uuid

from .config import settings


def run_dental_pano_ai(input_image_path: str, debug: bool = False) -> dict:
    """
    Run the original dental-pano-ai/main.py script on a single image.

    Args:
        input_image_path: Path to the input image file
        debug: If True, enables debug mode to generate visualization images

    Returns:
        {
            "output_dir": "<path>",
            "output_files": ["<file1>", "<file2>", ...],
        }
    """
    input_path = Path(input_image_path)
    # Convert to absolute path to ensure the script can find it when running from dental-pano-ai directory
    input_path = input_path.resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    if not settings.MODELS_DIR.exists():
        raise RuntimeError(
            f"Models directory not found at {settings.MODELS_DIR}. "
            "Make sure models.tar.gz was downloaded and extracted."
        )

    # Unique output directory per request
    out_id = uuid.uuid4().hex
    output_dir = settings.RESULTS_DIR / out_id
    output_dir = output_dir.resolve()  # Convert to absolute path
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build the command.
    # Use 'poetry run' to ensure the script runs with Poetry's virtual environment
    # which has all the dependencies installed (absl-py, torch, etc.)
    # This works reliably in both local and Docker environments.
    # main.py supports --input and --output; models default to ./models/* per README.
    # We rely on those defaults by setting cwd=REPO_DIR.
    # Convert paths to relative paths from REPO_DIR to avoid Windows absolute path issues.
    # The script's path handling for absolute paths only works on Unix-like systems.
    repo_dir_resolved = settings.DENTAL_PANO_AI_REPO_DIR.resolve()
    
    # Calculate relative path from REPO_DIR to input file
    try:
        input_path_relative = os.path.relpath(str(input_path.resolve()), str(repo_dir_resolved))
    except ValueError:
        # If paths are on different drives (Windows), we can't make them relative
        # In this case, we'll need to copy the file or use a workaround
        # For now, try using the path as-is but this may fail
        input_path_relative = str(input_path.resolve())
    
    # Calculate relative path from REPO_DIR to output directory
    try:
        output_dir_relative = os.path.relpath(str(output_dir.resolve()), str(repo_dir_resolved))
    except ValueError:
        output_dir_relative = str(output_dir.resolve())
    
    # Build command using poetry run
    # Use python -m poetry for better compatibility in Docker environments
    # where Poetry might not be in PATH but is installed via pip
    cmd = [
        settings.PYTHON_EXECUTABLE,
        "-m",
        "poetry",
        "run",
        settings.PYTHON_EXECUTABLE,
        "main.py",
        "--input",
        input_path_relative,
        "--output",
        output_dir_relative,
    ]
    
    # Add --debug flag if requested
    if debug:
        cmd.append("--debug")

    # Run the script in the repo directory so relative paths (./models, ./data, etc.) work.
    try:
        completed = subprocess.run(
            cmd,
            cwd=str(settings.DENTAL_PANO_AI_REPO_DIR),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as e:
        error_msg = f"Command failed with exit code {e.returncode}\n"
        error_msg += f"Command: {' '.join(cmd)}\n"
        error_msg += f"Working directory: {settings.DENTAL_PANO_AI_REPO_DIR}\n"
        if e.stdout:
            error_msg += f"STDOUT:\n{e.stdout}\n"
        if e.stderr:
            error_msg += f"STDERR:\n{e.stderr}\n"
        raise RuntimeError(error_msg) from e

    # You can log completed.stdout / completed.stderr if needed
    # print("STDOUT:", completed.stdout)
    # print("STDERR:", completed.stderr)

    # Collect output files (including files in subdirectories for debug images)
    output_files = []
    for p in output_dir.rglob("*"):  # Use rglob to search recursively
        if p.is_file():
            output_files.append(str(p))

    if not output_files:
        error_msg = f"No output files produced in {output_dir}.\n"
        error_msg += f"Command: {' '.join(cmd)}\n"
        error_msg += f"Working directory: {settings.DENTAL_PANO_AI_REPO_DIR}\n"
        error_msg += f"Input file: {input_path}\n"
        error_msg += f"Output directory: {output_dir}\n"
        if completed.stdout:
            error_msg += f"STDOUT:\n{completed.stdout}\n"
        if completed.stderr:
            error_msg += f"STDERR:\n{completed.stderr}\n"
        raise RuntimeError(error_msg)

    return {
        "output_dir": str(output_dir),
        "output_files": output_files,
    }
