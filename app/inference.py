import os
from pathlib import Path
import uuid
import numpy as np
from PIL import Image
import logging

from .config import settings

logger = logging.getLogger(__name__)

# Import model_manager with error handling
try:
    from .models import model_manager, FindingAssessment
    MODELS_AVAILABLE = True
except Exception as e:
    logger.error(f"Failed to import model_manager: {e}")
    model_manager = None
    FindingAssessment = None
    MODELS_AVAILABLE = False


def run_dental_pano_ai(input_image_path: str, debug: bool = False) -> dict:
    """
    Run dental-pano-ai inference on a single image using pre-loaded models.
    
    This function uses models that were loaded at application startup,
    avoiding the overhead of loading models on each request. This makes
    inference much faster (typically 10-100x faster) since models are
    already in memory.

    Args:
        input_image_path: Path to the input image file
        debug: If True, generates visualization images (semantic-segmentation.jpg
               and instance-detection.jpg) in the output directory

    Returns:
        {
            "output_dir": "<path>",
            "output_files": ["<file1>", "<file2>", ...],
        }
    """
    input_path = Path(input_image_path)
    input_path = input_path.resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input image not found: {input_path}")

    if not MODELS_AVAILABLE or not model_manager:
        raise RuntimeError(
            "Model manager not available. Cannot run inference."
        )
    
    if not model_manager.is_loaded():
        # Try to load models now (lazy loading fallback)
        logger.warning("Models not loaded, loading now (this will be slow)...")
        try:
            model_manager.load_models(debug=debug)
        except Exception as e:
            raise RuntimeError(
                f"Failed to load models: {e}. "
                "Make sure the application started successfully and models are available."
            ) from e

    # Unique output directory per request
    out_id = uuid.uuid4().hex
    output_dir = settings.RESULTS_DIR / out_id
    output_dir = output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    # Get the pre-loaded modules
    # Models are loaded with debug=True at startup, so visualization will work
    semseg_module, insdet_module, postproc_module = model_manager.get_modules(debug=debug)

    # Load and process the image
    image_pil = Image.open(input_path).convert("RGB")
    image = np.asarray(image_pil)

    # Create subdirectory for this image (matching original behavior)
    image_output_dir = output_dir / input_path.stem
    image_output_dir.mkdir(parents=True, exist_ok=True)

    # Run inference
    semseg_pred = semseg_module(image, output_dir=image_output_dir)
    insdet_pred = insdet_module(image, output_dir=image_output_dir)
    finding_entries = postproc_module(semseg_pred, insdet_pred)

    # Generate CSV output
    csv_path = output_dir / f"{input_path.stem}.csv"
    assessment = FindingAssessment(
        name=input_path.stem,
        entries=finding_entries
    )
    assessment.to_csv(csv_path)

    # Collect output files (including files in subdirectories for debug images)
    output_files = []
    for p in output_dir.rglob("*"):
        if p.is_file():
            output_files.append(str(p))

    if not output_files:
        raise RuntimeError(
            f"No output files produced in {output_dir}. "
            f"Expected at least a CSV file at {csv_path}."
        )

    return {
        "output_dir": str(output_dir),
        "output_files": output_files,
    }
