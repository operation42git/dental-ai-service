import subprocess
from pathlib import Path
import uuid

# Where the dental-pano-ai repo will be cloned inside the image
REPO_DIR = Path("/app/dental-pano-ai")
MODELS_DIR = REPO_DIR / "models"
RESULTS_ROOT = REPO_DIR / "results"


def run_dental_pano_ai(input_image_path: str) -> dict:
    """
    Run the original dental-pano-ai/main.py script on a single image.

    Returns:
        {
            "output_dir": "<path>",
            "output_files": ["<file1>", "<file2>", ...],
        }
    """
    input_path = Path(input_image_path)
    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    if not MODELS_DIR.exists():
        raise RuntimeError(
            f"Models directory not found at {MODELS_DIR}. "
            "Make sure models.tar.gz was downloaded and extracted during build."
        )

    # Unique output directory per request
    RESULTS_ROOT.mkdir(parents=True, exist_ok=True)
    out_id = uuid.uuid4().hex
    output_dir = RESULTS_ROOT / out_id
    output_dir.mkdir(parents=True, exist_ok=True)

    # Build the command.
    # main.py supports --input and --output; models default to ./models/* per README.
    # We rely on those defaults by setting cwd=REPO_DIR.
    cmd = [
        "python",
        "main.py",
        "--input",
        str(input_path),
        "--output",
        str(output_dir),
    ]

    # Run the script in the repo directory so relative paths (./models, ./data, etc.) work.
    completed = subprocess.run(
        cmd,
        cwd=str(REPO_DIR),
        check=True,
        capture_output=True,
        text=True,
    )

    # You can log completed.stdout / completed.stderr if needed
    # print("STDOUT:", completed.stdout)
    # print("STDERR:", completed.stderr)

    # Collect output files
    output_files = [str(p) for p in output_dir.glob("*") if p.is_file()]

    if not output_files:
        raise RuntimeError(
            f"No output files produced in {output_dir}. "
            "Check logs (stdout/stderr) from dental-pano-ai."
        )

    return {
        "output_dir": str(output_dir),
        "output_files": output_files,
    }
