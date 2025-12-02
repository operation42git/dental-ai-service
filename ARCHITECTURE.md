# Architecture Overview

## Simplified Architecture

```
┌─────────────┐
│   Web App   │
│  (Backend)  │
└──────┬──────┘
       │
       │ 1. Upload image to temp S3
       │ 2. Call RunPod API
       │ 3. Poll for results
       │ 4. Display to user
       │ 5. Save to permanent S3 (if approved)
       │
       ▼
┌──────────────────┐
│  RunPod Serverless│
│   (GPU Inference) │
└──────┬───────────┘
       │
       │ • Download image
       │ • Run AI inference
       │ • Return findings + CSV + images
       │
       ▼
   [Results]
```

## Components

### 1. Web App (Your Application)
**Responsibilities:**
- User interface
- Image upload to temp S3
- Call RunPod API
- Poll for results
- Display results to user
- Save to permanent S3 after approval
- Database storage
- Business logic

**Technologies:**
- Your choice (Next.js, Laravel, Django, etc.)
- S3 SDK (boto3, AWS SDK, etc.)
- HTTP client (fetch, axios, requests, etc.)

**Environment Variables:**
```env
RUNPOD_API_KEY=your-runpod-api-key
RUNPOD_ENDPOINT_ID=your-endpoint-id
AWS_ACCESS_KEY_ID=your-s3-key
AWS_SECRET_ACCESS_KEY=your-s3-secret
AWS_REGION=fra1
```

### 2. RunPod Serverless (This Repo)
**Responsibilities:**
- AI inference only
- Download image from URL
- Run dental-pano-ai models
- Return findings + CSV + debug images

**Technologies:**
- Python 3.10
- PyTorch 2.1 (GPU)
- Detectron2 (semantic segmentation)
- Ultralytics YOLO (instance detection)
- RunPod SDK

**Input:**
```json
{
  "image_url": "https://...",
  "debug": false
}
```

**Output:**
```json
{
  "findings": [...],
  "csv_data": "...",
  "num_findings": 256,
  "debug_images": {...}
}
```

### 3. S3/Spaces (Storage)
**Responsibilities:**
- Store input images (temp)
- Store results (permanent, after approval)
- Serve images via CDN

**Structure:**
```
bucket/
├── temp/                    # Temporary uploads
│   └── image-123.jpg
├── patients/
│   └── patient-id/
│       └── analysis-timestamp/
│           ├── input.jpg
│           ├── findings.csv
│           └── debug/
│               ├── semantic-segmentation.jpg
│               └── instance-detection.jpg
```

## Data Flow

### 1. User Uploads Image
```
User → Web App → Temp S3
```
- User selects image
- Web app uploads to `temp/` folder in S3
- Gets public URL

### 2. Submit to RunPod
```
Web App → RunPod API
```
- POST to `https://api.runpod.ai/v2/{endpoint}/run`
- Payload: `{"input": {"image_url": "...", "debug": true}}`
- Response: `{"id": "job-123"}`
- **Time**: ~100ms

### 3. RunPod Processing
```
RunPod → Download → Inference → Return
```
- Download image from S3
- Run AI models (GPU)
- Return findings + CSV + images
- **Time**: ~15-25 seconds

### 4. Poll for Results
```
Web App → RunPod Status API
```
- GET `https://api.runpod.ai/v2/{endpoint}/status/{job_id}`
- Poll every 2 seconds
- When status = "COMPLETED", get output

### 5. Display Results
```
Web App → User
```
- Show findings table
- Display debug images (decode base64)
- Show CSV preview
- Offer download/save options

### 6. Save to Permanent Storage (If Approved)
```
Web App → Permanent S3 → Database
```
- User reviews results
- If approved:
  - Move image from `temp/` to `patients/{id}/`
  - Save CSV to S3
  - Save debug images to S3
  - Store metadata in database

## Benefits of This Architecture

### ✅ Simplicity
- Only 2 services (web app + RunPod)
- No middleware/orchestrator needed
- Clear separation of concerns

### ✅ Performance
- Fast response (~1s for job submission)
- GPU inference (~20s)
- No unnecessary hops

### ✅ Cost-Effective
- Pay-per-use for AI ($0.01/image)
- No always-on API server needed
- Efficient resource usage

### ✅ Flexibility
- User can review before saving
- Easy to rerun analysis
- Can reject/discard results

### ✅ Scalability
- RunPod auto-scales
- No capacity planning needed
- Handles traffic spikes

## Security

### API Key Protection
- RunPod API key stored in web app backend (server-side)
- Never exposed to frontend/browser
- Same security as S3 credentials

### S3 Access
- Temp folder for uploads (short-lived)
- Permanent folder requires approval
- Public read for results (or use signed URLs)

## Monitoring

### RunPod Dashboard
- View request logs
- Monitor worker health
- Track costs
- View execution times

### Web App
- Track job submissions
- Monitor completion rates
- Log errors
- User analytics

## Disaster Recovery

### If RunPod is Down
- Queue requests in web app
- Process when RunPod is back
- Or switch to backup endpoint

### If S3 is Down
- Can't upload images
- Show error to user
- Retry later

### If Web App is Down
- No impact on RunPod
- RunPod continues processing queued jobs
- Results available when web app recovers

## Future Enhancements

### Webhooks
- RunPod calls webhook when complete
- No polling needed
- Faster notification

### Batch Processing
- Submit multiple images at once
- Process in parallel
- Bulk results

### Caching
- Cache results for duplicate images
- Reduce redundant processing
- Lower costs

### Multi-Model Support
- Deploy different models to different endpoints
- A/B testing
- Model versioning

