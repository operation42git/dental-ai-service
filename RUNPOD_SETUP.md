# RunPod Serverless Setup Guide

This guide explains how to deploy the dental AI inference to RunPod serverless for fast, GPU-powered processing.

## Architecture

- **DigitalOcean App**: Receives requests, uploads images to S3, submits jobs to RunPod
- **RunPod Serverless**: Runs GPU-accelerated inference (~15 seconds)
- **S3/Spaces**: Stores input images and results

## Benefits

- ⚡ **Fast**: ~15 seconds inference (vs 2+ minutes on CPU)
- 💰 **Cost-effective**: Pay only for inference time
- 🔄 **Auto-scaling**: Handles traffic spikes automatically
- 🚀 **No timeouts**: No memory or timeout issues

## Setup Steps

### 1. Sign Up for RunPod

1. Go to [https://www.runpod.io/](https://www.runpod.io/)
2. Create an account
3. Add payment method (you get $5-$500 credit bonus)

### 2. Create API Key

1. Go to Settings → API Keys
2. Create a new API key
3. Save it securely (you'll need it later)

### 3. Build and Push Docker Image

```bash
# Build the RunPod handler image
docker build -f Dockerfile.runpod -t your-dockerhub-username/dental-ai-runpod:latest .

# Push to Docker Hub (or any container registry)
docker push your-dockerhub-username/dental-ai-runpod:latest
```

### 4. Create RunPod Serverless Endpoint

1. Go to RunPod Dashboard → Serverless
2. Click "New Endpoint"
3. Configure:
   - **Name**: `dental-ai-inference`
   - **Docker Image**: `your-dockerhub-username/dental-ai-runpod:latest`
   - **GPU Type**: Select GPU (e.g., RTX 4090, A4000, or higher)
   - **Workers**:
     - **Active Workers**: 0 (use FlashBoot for fast cold starts)
     - **Max Workers**: 3-5 (for auto-scaling)
   - **Container Disk**: 10 GB
   - **Volume**: Not required (models are in the image)
   - **Environment Variables** (for S3 uploads):
     - `AWS_ACCESS_KEY_ID`: Your S3/Spaces access key
     - `AWS_SECRET_ACCESS_KEY`: Your S3/Spaces secret key
     - `AWS_REGION`: Your region (e.g., `fra1` for DigitalOcean Spaces)
   - **FlashBoot**: Enable for <200ms cold starts
4. Click "Deploy"
5. Copy the **Endpoint ID** (you'll need it)

### 5. Configure DigitalOcean App

Add these environment variables to your DigitalOcean app:

```bash
RUNPOD_API_KEY=your-runpod-api-key
RUNPOD_ENDPOINT_ID=your-endpoint-id
```

### 6. Deploy Updated Code

```bash
git add .
git commit -m "Add RunPod serverless integration"
git push
```

DigitalOcean will automatically redeploy.

## Usage

### Fast Mode (Recommended)

Returns job ID immediately (~100ms response):

```bash
curl -X POST "https://your-app.ondigitalocean.app/analyze-ortopan?wait_for_result=false" \
  -F "file=@image.jpg" \
  -F "s3_bucket=your-bucket" \
  -F "s3_prefix=patient/folder/"
```

Response:
```json
{
  "message": "job submitted",
  "job_id": "abc123",
  "status_url": "/job-status/abc123",
  "elapsed_time": 0.12
}
```

Then poll for results:

```bash
curl "https://your-app.ondigitalocean.app/job-status/abc123"
```

### Sync Mode

Waits for completion (~15-30s response):

```bash
curl -X POST "https://your-app.ondigitalocean.app/analyze-ortopan?wait_for_result=true" \
  -F "file=@image.jpg" \
  -F "s3_bucket=your-bucket" \
  -F "s3_prefix=patient/folder/"
```

Response:
```json
{
  "message": "analysis complete",
  "job_id": "abc123",
  "findings": [
    {"fdi": "11", "finding": "CARIES", "score": 0.95}
  ],
  "csv_data": "...",
  "elapsed_time": 18.5
}
```

## Cost Estimation

### RunPod Pricing (as of Dec 2024)

| GPU | Price per second | Price per minute | Typical inference time | Cost per image |
|-----|------------------|------------------|------------------------|----------------|
| RTX 4090 | $0.00077 | $0.046 | ~15 seconds | ~$0.012 |
| A4000 | $0.00048 | $0.029 | ~20 seconds | ~$0.010 |
| L40 | $0.00133 | $0.080 | ~12 seconds | ~$0.016 |

**Example**: 1000 images/month on RTX 4090 = ~$12/month

Compare to DigitalOcean:
- 4GB RAM instance: $24/month (always running)
- 8GB RAM instance: $48/month (always running)

RunPod is more cost-effective for:
- Low to moderate volume (<2000 images/month)
- Bursty traffic patterns
- Need for fast inference

## Monitoring

### Check Endpoint Status

```bash
curl -H "Authorization: Bearer YOUR_API_KEY" \
  https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/health
```

### View Logs

1. Go to RunPod Dashboard → Serverless → Your Endpoint
2. Click "Logs" tab
3. View real-time logs for debugging

## Troubleshooting

### Job Stuck in Queue

- **Cause**: No workers available
- **Solution**: Increase "Active Workers" to 1 for faster cold starts

### Job Fails Immediately

- **Cause**: Docker image issue or missing models
- **Solution**: Check RunPod logs, verify Docker image is correct

### Slow Cold Starts

- **Cause**: Models loading on first request
- **Solution**: Set "Active Workers" to 1 to keep one worker warm

### Out of Memory

- **Cause**: GPU memory insufficient
- **Solution**: Use a GPU with more VRAM (e.g., A6000 48GB instead of 4090 24GB)

## Advanced Configuration

### Custom GPU Selection

Edit your RunPod endpoint to prefer specific GPUs:

```json
{
  "gpu_ids": "NVIDIA RTX 4090,NVIDIA A4000",
  "min_vcpu": 4,
  "min_memory_gb": 16
}
```

### Webhook Notifications

Instead of polling, use webhooks:

1. Add webhook URL to job submission:
```python
job_result = submit_inference_job(
    image_url=image_url,
    webhook="https://your-app.com/webhook"
)
```

2. RunPod will POST results to your webhook when complete

### Batch Processing

For multiple images, submit multiple jobs:

```python
job_ids = []
for image_url in image_urls:
    result = submit_inference_job(image_url)
    job_ids.append(result["id"])

# Wait for all to complete
results = await asyncio.gather(*[
    wait_for_completion(job_id) for job_id in job_ids
])
```

## Migration from Local Inference

The API is backward compatible. Existing clients work without changes:

- Default behavior: Returns job ID immediately
- Add `wait_for_result=true` for synchronous operation
- Response format includes all previous fields plus `job_id`

## Support

- RunPod Docs: https://docs.runpod.io/
- RunPod Discord: https://discord.gg/runpod
- RunPod Support: support@runpod.io

