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
    logger.info("Running semantic segmentation...")
    print("[INFERENCE] Running semantic segmentation...", flush=True)
    
    # Log memory usage before inference
    try:
        import psutil
        import os
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        mem_mb = mem_info.rss / 1024 / 1024
        mem_percent = process.memory_percent()
        logger.info(f"Memory usage before semantic segmentation: {mem_mb:.2f} MB ({mem_percent:.1f}%)")
        print(f"[INFERENCE] Memory before semantic seg: {mem_mb:.2f} MB ({mem_percent:.1f}%)", flush=True)
        
        # Also log system memory
        sys_mem = psutil.virtual_memory()
        logger.info(f"System memory: {sys_mem.used / 1024 / 1024:.2f} MB used / {sys_mem.total / 1024 / 1024:.2f} MB total ({sys_mem.percent:.1f}%)")
        print(f"[INFERENCE] System memory: {sys_mem.used / 1024 / 1024:.2f} MB used / {sys_mem.total / 1024 / 1024:.2f} MB total ({sys_mem.percent:.1f}%)", flush=True)
    except ImportError:
        logger.warning("psutil not available, cannot monitor memory")
        print("[INFERENCE] WARNING: psutil not available, cannot monitor memory", flush=True)
    except Exception as e:
        logger.warning(f"Could not get memory info: {e}")
        print(f"[INFERENCE] WARNING: Could not get memory info: {e}", flush=True)
    
    import time
    start_time = time.time()
    try:
        semseg_pred = semseg_module(image, output_dir=image_output_dir)
        elapsed = time.time() - start_time
        logger.info(f"Semantic segmentation completed in {elapsed:.2f} seconds")
        print(f"[INFERENCE] Semantic segmentation completed in {elapsed:.2f} seconds", flush=True)
        
        # Log memory after semantic segmentation
        try:
            import psutil
            import os
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            mem_mb = mem_info.rss / 1024 / 1024
            mem_percent = process.memory_percent()
            logger.info(f"Memory usage after semantic segmentation: {mem_mb:.2f} MB ({mem_percent:.1f}%)")
            print(f"[INFERENCE] Memory after semantic seg: {mem_mb:.2f} MB ({mem_percent:.1f}%)", flush=True)
            
            sys_mem = psutil.virtual_memory()
            logger.info(f"System memory: {sys_mem.used / 1024 / 1024:.2f} MB used / {sys_mem.total / 1024 / 1024:.2f} MB total ({sys_mem.percent:.1f}%)")
            print(f"[INFERENCE] System memory: {sys_mem.used / 1024 / 1024:.2f} MB used / {sys_mem.total / 1024 / 1024:.2f} MB total ({sys_mem.percent:.1f}%)", flush=True)
        except Exception:
            pass
        
        # Free memory by clearing the semantic segmentation module from GPU/memory cache
        # This reduces peak memory usage before running instance detection
        logger.info("Clearing memory after semantic segmentation...")
        print("[INFERENCE] Clearing memory after semantic segmentation...", flush=True)
        try:
            import torch
            import gc
            # Clear PyTorch cache
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            # Force garbage collection
            gc.collect()
            logger.info("Memory cleared")
            print("[INFERENCE] Memory cleared", flush=True)
        except Exception as e:
            logger.warning(f"Could not clear memory: {e}")
            print(f"[INFERENCE] WARNING: Could not clear memory: {e}", flush=True)
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Semantic segmentation failed after {elapsed:.2f} seconds: {e}")
        print(f"[INFERENCE] ERROR: Semantic segmentation failed after {elapsed:.2f} seconds: {e}", flush=True)
        raise
    
    logger.info("Running instance detection...")
    print("[INFERENCE] Running instance detection...", flush=True)
    
    # Log memory usage before instance detection
    try:
        import psutil
        import os
        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        mem_mb = mem_info.rss / 1024 / 1024
        mem_percent = process.memory_percent()
        logger.info(f"Memory usage before instance detection: {mem_mb:.2f} MB ({mem_percent:.1f}%)")
        print(f"[INFERENCE] Memory before instance detection: {mem_mb:.2f} MB ({mem_percent:.1f}%)", flush=True)
        
        sys_mem = psutil.virtual_memory()
        logger.info(f"System memory: {sys_mem.used / 1024 / 1024:.2f} MB used / {sys_mem.total / 1024 / 1024:.2f} MB total ({sys_mem.percent:.1f}%)")
        print(f"[INFERENCE] System memory: {sys_mem.used / 1024 / 1024:.2f} MB used / {sys_mem.total / 1024 / 1024:.2f} MB total ({sys_mem.percent:.1f}%)", flush=True)
    except Exception as e:
        logger.warning(f"Could not get memory info: {e}")
        print(f"[INFERENCE] WARNING: Could not get memory info: {e}", flush=True)
    
    start_time = time.time()
    try:
        insdet_pred = insdet_module(image, output_dir=image_output_dir)
        elapsed = time.time() - start_time
        logger.info(f"Instance detection completed in {elapsed:.2f} seconds")
        print(f"[INFERENCE] Instance detection completed in {elapsed:.2f} seconds", flush=True)
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Instance detection failed after {elapsed:.2f} seconds: {e}")
        print(f"[INFERENCE] ERROR: Instance detection failed after {elapsed:.2f} seconds: {e}", flush=True)
        raise
    
    logger.info("Running post-processing...")
    finding_entries = postproc_module(semseg_pred, insdet_pred)
    logger.info(f"Post-processing completed, found {len(finding_entries)} entries")

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
