# Dental AI Service - RunPod Serverless

GPU-powered dental panoramic X-ray analysis service deployed on RunPod Serverless.

- **Original AI Model**: [dental-pano-ai](https://github.com/stmharry/dental-pano-ai)
- **Platform**: RunPod Serverless (GPU)
- **Response Time**: ~15-25 seconds
- **Cost**: ~$0.01 per image (pay-per-use)

## What This Service Does

Analyzes dental panoramic X-rays and detects:
- Missing teeth
- Implants
- Fillings
- Caries (cavities)
- Root canal fillings
- Crowns/bridges
- Periapical radiolucencies
- Residual roots

## Architecture

```
Web App → RunPod Serverless → Returns Results
```

**RunPod handles:**
- AI inference (GPU-accelerated)
- Returns findings + CSV + debug images

**Web app handles:**
- Image upload
- Calling RunPod API
- Displaying results
- S3 storage (after user approval)
- Business logic

## Quick Start

### 1. Deploy to RunPod

See [RUNPOD_SETUP.md](RUNPOD_SETUP.md) for detailed setup instructions.

**Quick steps:**
1. Sign up at [RunPod.io](https://www.runpod.io/)
2. Create Serverless Endpoint
3. Connect to this GitHub repo
4. Set Dockerfile path: `Dockerfile.runpod`
5. Select GPU (RTX 4090 recommended)
6. Deploy

### 2. Test the Endpoint

See [RUNPOD_TEST.md](RUNPOD_TEST.md) for testing instructions.

**Quick test:**
```bash
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "image_url": "https://example.com/dental-xray.jpg",
      "debug": true
    }
  }'
```

### 3. Integrate with Your Web App

Add to your web app backend:

```javascript
// Call RunPod
const response = await fetch(`https://api.runpod.ai/v2/${RUNPOD_ENDPOINT_ID}/run`, {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${RUNPOD_API_KEY}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    input: {
      image_url: imageUrl,
      debug: true
    }
  })
});

const { id: jobId } = await response.json();

// Poll for results
const result = await pollForResults(jobId);

// result.output contains:
// - findings: Array of detected findings
// - csv_data: CSV string
// - debug_images: Base64 encoded images (if debug=true)
```

## API Reference

### Input Format

```json
{
  "input": {
    "image_url": "https://example.com/image.jpg",
    "debug": false
  }
}
```

**Parameters:**
- `image_url` (required): Publicly accessible URL to dental X-ray image
- `debug` (optional): If `true`, returns visualization images (default: `false`)

### Output Format

```json
{
  "findings": [
    {
      "fdi": "11",
      "finding": "CARIES",
      "score": 0.95
    },
    ...
  ],
  "csv_data": "file_name,fdi,finding,score\n...",
  "num_findings": 256,
  "debug_image_urls": {
    "semantic-segmentation.jpg": "https://s3.../temp/job-123/semantic-segmentation.jpg",
    "instance-detection.jpg": "https://s3.../temp/job-123/instance-detection.jpg"
  }
}
```

**Fields:**
- `findings`: Array of detected findings with FDI notation, finding type, and confidence score
- `csv_data`: CSV format of findings
- `num_findings`: Total number of findings
- `debug_image_urls`: S3 URLs to debug visualization images in temp folder (expire after 24 hours)

## Performance

| Metric | Value |
|--------|-------|
| Cold start (with FlashBoot) | <200ms |
| Inference time (GPU) | 15-25 seconds |
| Total response time | 15-30 seconds |

## Cost

| Volume | Monthly Cost |
|--------|--------------|
| 100 images | ~$1 |
| 1,000 images | ~$10 |
| 10,000 images | ~$100 |

Based on RTX 4090 pricing (~$0.01 per image).

## Files in This Repo

- `Dockerfile.runpod` - Docker image for RunPod deployment
- `runpod_handler_simple.py` - Inference handler (no S3 logic)
- `RUNPOD_SETUP.md` - Detailed setup guide
- `RUNPOD_TEST.md` - Testing guide with examples
- `README.md` - This file

## Local Development

This service is designed to run on RunPod's GPU infrastructure. For local development:

1. Clone the repo
2. Install dependencies (see `Dockerfile.runpod` for package list)
3. Download models from [dental-pano-ai S3](https://dental-pano-ai.s3.ap-southeast-1.amazonaws.com/models.tar.gz)
4. Run the handler locally (requires GPU for reasonable performance)

## Support

- RunPod Documentation: https://docs.runpod.io/
- Original Model: https://github.com/stmharry/dental-pano-ai
- Issues: Create an issue in this repository

## License

This wrapper service follows the same license as the original dental-pano-ai project.
