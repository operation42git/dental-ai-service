# RunPod Testing Guide

## Quick Test with curl

### 1. Get Your Credentials

- **API Key**: RunPod Dashboard → Settings → API Keys
- **Endpoint ID**: RunPod Dashboard → Serverless → Your Endpoint (e.g., `cqpnz9dyo9lu2x`)

### 2. Test with Public Image URL

```bash
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
  -H "Authorization: Bearer YOUR_RUNPOD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "image_url": "https://fra1.digitaloceanspaces.com/kisdentalchart/Staging/photos/Tomić Ivan, 1985-11-11/AI test 1/input/cc63add834ce47c78c0d016a7c29fc13.jpeg",
      "debug": true
    }
  }'
```

**Response:**
```json
{
  "id": "abc123-xyz",
  "status": "IN_QUEUE"
}
```

### 3. Check Job Status

```bash
curl https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/status/abc123-xyz \
  -H "Authorization: Bearer YOUR_RUNPOD_API_KEY"
```

**While processing:**
```json
{
  "id": "abc123-xyz",
  "status": "IN_PROGRESS"
}
```

**When complete:**
```json
{
  "id": "abc123-xyz",
  "status": "COMPLETED",
  "output": {
    "findings": [
      {"fdi": "11", "finding": "CARIES", "score": 0.95},
      {"fdi": "12", "finding": "FILLING", "score": 0.88},
      ...
    ],
    "csv_data": "file_name,fdi,finding,score\ntmpxyz,11,CARIES,0.95\n...",
    "num_findings": 256,
    "debug_image_urls": {
      "semantic-segmentation.jpg": "https://fra1.digitaloceanspaces.com/kisdentalchart/temp/job-abc123/semantic-segmentation.jpg",
      "instance-detection.jpg": "https://fra1.digitaloceanspaces.com/kisdentalchart/temp/job-abc123/instance-detection.jpg"
    }
  }
}
```

## Test in RunPod Interface

1. Go to RunPod Dashboard → Your Endpoint
2. Click **"Requests"** tab
3. In the input box, paste:

```json
{
  "input": {
    "image_url": "https://fra1.digitaloceanspaces.com/kisdentalchart/Staging/photos/Tomić Ivan, 1985-11-11/AI test 1/input/cc63add834ce47c78c0d016a7c29fc13.jpeg",
    "debug": true
  }
}
```

4. Click **"Run"**
5. Wait ~20 seconds
6. See results in the output panel

## Expected Timing

- **Queue time**: 0-30 seconds (cold start with FlashBoot)
- **Execution time**: 15-25 seconds
  - Download: 1-2s
  - Semantic segmentation: 5-10s
  - Instance detection: 3-5s
  - Post-processing: 1-2s
  - Encoding: 2-5s
- **Total**: 15-55 seconds (first request), 15-25s (subsequent)

## Output Format

### Findings Array:
```json
"findings": [
  {
    "fdi": "11",           // Tooth number (FDI notation)
    "finding": "CARIES",   // Finding type
    "score": 0.95          // Confidence score (0-1)
  },
  ...
]
```

### CSV Data:
```
file_name,fdi,finding,score
tmpxyz,11,CARIES,0.95
tmpxyz,12,FILLING,0.88
...
```

### Debug Image URLs (if debug=true):
```json
"debug_image_urls": {
  "semantic-segmentation.jpg": "https://fra1.digitaloceanspaces.com/kisdentalchart/temp/job-abc123/semantic-segmentation.jpg",
  "instance-detection.jpg": "https://fra1.digitaloceanspaces.com/kisdentalchart/temp/job-abc123/instance-detection.jpg"
}
```

**Note:** These are temporary URLs that expire after 24 hours (S3 lifecycle rule).

## Displaying Images

### In JavaScript:
```javascript
const debugImageUrls = result.output.debug_image_urls;
for (const [filename, url] of Object.entries(debugImageUrls)) {
  const img = document.createElement('img');
  img.src = url;  // Direct S3 URL - no decoding needed!
  document.body.appendChild(img);
}
```

### In HTML:
```html
<img src="https://fra1.digitaloceanspaces.com/kisdentalchart/temp/job-abc123/semantic-segmentation.jpg" />
```

### Saving Permanently:
```javascript
// If user approves, copy from temp to permanent storage
await copyS3Object({
  from: 'temp/job-abc123/semantic-segmentation.jpg',
  to: `patients/${patientId}/analysis-${timestamp}/semantic-segmentation.jpg`
});
```

## Troubleshooting

### Job Stuck in Queue
- Check worker count (should be >0)
- Check GPU availability
- Terminate old workers if needed

### Job Fails with "image_url" Error
- Ensure image URL is publicly accessible
- Check URL format is correct
- Verify image is a valid JPEG/PNG

### Job Times Out
- Check logs for actual error
- Verify NumPy version is 1.x (not 2.x)
- Check if running on GPU (not CPU)

### JSON Serialization Error
- This is fixed in the latest version
- Rebuild if you see this error

## Integration with Web App

See your web app backend code for how to:
1. Upload image to temp S3 location
2. Call RunPod with image URL
3. Poll for results
4. Save to permanent S3 after user approval

