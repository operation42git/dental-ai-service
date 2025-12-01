"""Model initialization and management for dental-pano-ai modules."""
import sys
import logging
from pathlib import Path
from typing import Optional

from .config import settings

logger = logging.getLogger(__name__)

# Validate dental-pano-ai directory exists before trying to import
_dental_pano_ai_path = Path(settings.DENTAL_PANO_AI_REPO_DIR)
if not _dental_pano_ai_path.exists():
    raise FileNotFoundError(
        f"Dental-pano-ai repository directory not found: {_dental_pano_ai_path}. "
        "Make sure the repository is cloned and DENTAL_PANO_AI_REPO_DIR is set correctly."
    )

_dental_pano_ai_path_str = str(_dental_pano_ai_path)
if _dental_pano_ai_path_str not in sys.path:
    sys.path.insert(0, _dental_pano_ai_path_str)

# Import the modules from dental-pano-ai
try:
    logger.info(f"Importing dental-pano-ai modules from {_dental_pano_ai_path_str}")
    from main import (
        SemanticSegmentationModule,
        InstanceDetectionModule,
        PostProcessingModule,
        FindingAssessment,
    )
    logger.info("Successfully imported dental-pano-ai modules")
    # Re-export for convenience
    __all__ = [
        "SemanticSegmentationModule",
        "InstanceDetectionModule",
        "PostProcessingModule",
        "FindingAssessment",
        "ModelManager",
        "model_manager",
    ]
except ImportError as e:
    logger.error(f"Failed to import dental-pano-ai modules from {_dental_pano_ai_path}: {e}")
    raise ImportError(
        f"Failed to import dental-pano-ai modules. "
        f"Make sure the repository is at {settings.DENTAL_PANO_AI_REPO_DIR}. "
        f"Error: {e}"
    )


class ModelManager:
    """Manages loaded AI models for reuse across requests."""
    
    def __init__(self):
        self.semseg_module: Optional[SemanticSegmentationModule] = None
        self.insdet_module: Optional[InstanceDetectionModule] = None
        self.postproc_module: Optional[PostProcessingModule] = None
        self._loaded = False
    
    def load_models(self, debug: bool = False) -> None:
        """
        Load all AI models into memory.
        
        Args:
            debug: If True, enables debug mode for visualization images
        """
        if self._loaded:
            logger.info("Models already loaded, skipping")
            return
        
        logger.info(f"Starting model loading (debug={debug})...")
        logger.info(f"Models directory: {settings.MODELS_DIR}")
        
        deeplab_config = settings.MODELS_DIR / "deeplab" / "config.yaml"
        deeplab_weights = settings.MODELS_DIR / "deeplab" / "model.pth"
        yolo_config = settings.MODELS_DIR / "yolo" / "config.yaml"
        yolo_weights = settings.MODELS_DIR / "yolo" / "model.pt"
        
        # Validate model files exist
        logger.info("Validating model files...")
        if not deeplab_config.exists():
            raise FileNotFoundError(f"DeepLab config not found: {deeplab_config}")
        if not deeplab_weights.exists():
            raise FileNotFoundError(f"DeepLab weights not found: {deeplab_weights}")
        if not yolo_config.exists():
            raise FileNotFoundError(f"YOLO config not found: {yolo_config}")
        if not yolo_weights.exists():
            raise FileNotFoundError(f"YOLO weights not found: {yolo_weights}")
        logger.info("All model files found")
        
        # Initialize modules (this loads models into memory)
        logger.info("Loading DeepLab (semantic segmentation) model...")
        try:
            self.semseg_module = SemanticSegmentationModule(
                config_path=str(deeplab_config),
                weights_path=str(deeplab_weights),
                debug=debug,
            )
            logger.info("DeepLab model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load DeepLab model: {e}")
            raise
        
        logger.info("Loading YOLO (instance detection) model...")
        try:
            self.insdet_module = InstanceDetectionModule(
                config_path=str(yolo_config),
                weights_path=str(yolo_weights),
                debug=debug,
            )
            logger.info("YOLO model loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load YOLO model: {e}")
            raise
        
        logger.info("Initializing post-processing module...")
        self.postproc_module = PostProcessingModule()
        
        self._loaded = True
        logger.info("All models loaded successfully!")
    
    def is_loaded(self) -> bool:
        """Check if models are loaded."""
        return self._loaded
    
    def get_modules(self, debug: bool = False):
        """
        Get the loaded modules. Loads them if not already loaded.
        
        Args:
            debug: If True, enables debug mode (only used if models need to be loaded)
        
        Returns:
            Tuple of (semseg_module, insdet_module, postproc_module)
        """
        if not self._loaded:
            self.load_models(debug=debug)
        
        # If debug mode changed, we need to reload (models are initialized with debug flag)
        # For now, we'll use the debug flag from initial load
        # In the future, we could support reloading if needed
        
        return self.semseg_module, self.insdet_module, self.postproc_module


# Global model manager instance
model_manager = ModelManager()

