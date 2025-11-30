from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from pathlib import Path
import shutil
import uuid

from .inference import run_dental_pano_ai

app = FastAPI(title="Dental AI Inference Service")

UPLOAD_DIR = Path("/app/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/analyze-ortopan")
async def analyze_ortopan(file: UploadFile = File(...)):
    """
    Accept a DPR/ortopan image upload and run the dental-pano-ai inference.
    """
    # Save uploaded file to disk
    suffix = Path(file.filename).suffix or ".png"
    file_id = uuid.uuid4().hex
    input_path = UPLOAD_DIR / f"{file_id}{suffix}"

    with input_path.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    try:
        result = run_dental_pano_ai(str(input_path))
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"error": str(e)},
        )

    # TODO:
    # - upload result["output_dir"] contents to S3/Spaces
    # - return signed URLs instead of local paths

    return {
        "message": "analysis complete",
        "input_path": str(input_path),
        "output_dir": result["output_dir"],
        "output_files": result["output_files"],
    }
