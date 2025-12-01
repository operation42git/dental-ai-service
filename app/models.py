"""Model initialization and management for dental-pano-ai modules."""
import sys
from pathlib import Path
from typing import Optional

from .config import settings

# Add dental-pano-ai directory to Python path so we can import its modules
_dental_pano_ai_path = str(settings.DENTAL_PANO_AI_REPO_DIR)
if _dental_pano_ai_path not in sys.path:
    sys.path.insert(0, _dental_pano_ai_path)

# Import the modules from dental-pano-ai
try:
    from main import (
        SemanticSegmentationModule,
        InstanceDetectionModule,
        PostProcessingModule,
        FindingAssessment,
    )
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
            return
        
        deeplab_config = settings.MODELS_DIR / "deeplab" / "config.yaml"
        deeplab_weights = settings.MODELS_DIR / "deeplab" / "model.pth"
        yolo_config = settings.MODELS_DIR / "yolo" / "config.yaml"
        yolo_weights = settings.MODELS_DIR / "yolo" / "model.pt"
        
        # Validate model files exist
        if not deeplab_config.exists():
            raise FileNotFoundError(f"DeepLab config not found: {deeplab_config}")
        if not deeplab_weights.exists():
            raise FileNotFoundError(f"DeepLab weights not found: {deeplab_weights}")
        if not yolo_config.exists():
            raise FileNotFoundError(f"YOLO config not found: {yolo_config}")
        if not yolo_weights.exists():
            raise FileNotFoundError(f"YOLO weights not found: {yolo_weights}")
        
        # Initialize modules (this loads models into memory)
        self.semseg_module = SemanticSegmentationModule(
            config_path=str(deeplab_config),
            weights_path=str(deeplab_weights),
            debug=debug,
        )
        
        self.insdet_module = InstanceDetectionModule(
            config_path=str(yolo_config),
            weights_path=str(yolo_weights),
            debug=debug,
        )
        
        self.postproc_module = PostProcessingModule()
        
        self._loaded = True
    
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

