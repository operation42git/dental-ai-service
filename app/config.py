"""Configuration management for the Dental AI Service."""
import os
from pathlib import Path

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


class Settings:
    """Application settings loaded from environment variables."""
    
    def __init__(self):
        """Initialize settings from environment variables."""
        # Base directory - defaults to /app for Docker, but can be overridden locally
        base_dir_str = os.getenv("BASE_DIR", "/app")
        self.BASE_DIR: Path = Path(base_dir_str)
        
        # Dental Pano AI repository directory
        repo_dir_str = os.getenv("DENTAL_PANO_AI_REPO_DIR")
        if repo_dir_str:
            self.DENTAL_PANO_AI_REPO_DIR: Path = Path(repo_dir_str)
        else:
            self.DENTAL_PANO_AI_REPO_DIR: Path = self.BASE_DIR / "dental-pano-ai"
        
        # Models directory (inside the repo)
        self.MODELS_DIR: Path = self.DENTAL_PANO_AI_REPO_DIR / "models"
        
        # Upload directory for temporary files
        upload_dir_str = os.getenv("UPLOAD_DIR")
        if upload_dir_str:
            self.UPLOAD_DIR: Path = Path(upload_dir_str)
        else:
            self.UPLOAD_DIR: Path = self.BASE_DIR / "uploads"
        
        # Results directory (inside the repo)
        self.RESULTS_DIR: Path = self.DENTAL_PANO_AI_REPO_DIR / "results"
        
        # Python executable path (for running dental-pano-ai)
        self.PYTHON_EXECUTABLE: str = os.getenv("PYTHON_EXECUTABLE", "python")
        
        # Poetry executable path (for running dental-pano-ai with dependencies)
        self.POETRY_EXECUTABLE: str = os.getenv("POETRY_EXECUTABLE", "poetry")
        
        # Create directories if they don't exist
        self.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        self.RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    
    def validate(self) -> None:
        """Validate that required directories exist."""
        if not self.DENTAL_PANO_AI_REPO_DIR.exists():
            raise RuntimeError(
                f"Dental Pano AI repository not found at {self.DENTAL_PANO_AI_REPO_DIR}. "
                "Please set DENTAL_PANO_AI_REPO_DIR environment variable or clone the repo."
            )
        
        if not self.MODELS_DIR.exists():
            raise RuntimeError(
                f"Models directory not found at {self.MODELS_DIR}. "
                "Please download and extract models.tar.gz into the repository."
            )


# Global settings instance
settings = Settings()

