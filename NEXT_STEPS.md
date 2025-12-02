# Next Steps - Deployment Guide

## ✅ Completed

1. Cleaned up repository - removed DigitalOcean API code
2. Simplified RunPod handler - no S3 logic, returns data directly
3. Fixed NumPy compatibility issues
4. Fixed JSON serialization issues
5. Created documentation

## 📋 What You Have Now

```
dental-ai-service/
├── Dockerfile.runpod          # RunPod deployment
├── runpod_handler_simple.py   # Simplified handler
├── README.md                   # Overview
├── RUNPOD_SETUP.md            # Setup guide
├── RUNPOD_TEST.md             # Testing guide
├── ARCHITECTURE.md            # Architecture docs
└── .gitignore                 # Updated
```

## 🚀 Deployment Steps

### 1. Push to GitHub

```powershell
git add .
git commit -m "Simplify to RunPod-only architecture"
git push
```

### 2. RunPod Will Auto-Rebuild

- Wait 10-15 minutes for build
- Check Builds tab for progress
- Verify build succeeds

### 3. Test the Endpoint

Use a public image URL (one of your existing S3 images):

**In RunPod Test Interface:**
```json
{
  "input": {
    "image_url": "https://fra1.digitaloceanspaces.com/kisdentalchart/Staging/photos/Tomić Ivan, 1985-11-11/AI test 1/input/cc63add834ce47c78c0d016a7c29fc13.jpeg",
    "debug": true
  }
}
```

**Expected Result:**
- Status: COMPLETED
- Findings: Array of 200-300 findings
- CSV data: Full CSV string
- Debug images: 2 base64 encoded images
- Time: ~20 seconds

### 4. Integrate with Web App

Add to your web app backend (see examples below).

## 💻 Web App Integration Examples

### Next.js Example

```javascript
// pages/api/analyze.js
export default async function handler(req, res) {
  const { imageUrl, patientId, debug } = req.body;
  
  // Submit to RunPod
  const response = await fetch(
    `https://api.runpod.ai/v2/${process.env.RUNPOD_ENDPOINT_ID}/run`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.RUNPOD_API_KEY}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        input: { image_url: imageUrl, debug }
      })
    }
  );
  
  const { id: jobId } = await response.json();
  res.json({ jobId });
}

// pages/api/job-status/[jobId].js
export default async function handler(req, res) {
  const { jobId } = req.query;
  
  const response = await fetch(
    `https://api.runpod.ai/v2/${process.env.RUNPOD_ENDPOINT_ID}/status/${jobId}`,
    {
      headers: {
        'Authorization': `Bearer ${process.env.RUNPOD_API_KEY}`
      }
    }
  );
  
  const result = await response.json();
  res.json(result);
}
```

### Laravel Example

```php
// app/Http/Controllers/AnalysisController.php
public function analyze(Request $request) {
    $imageUrl = $request->input('image_url');
    $debug = $request->input('debug', false);
    
    $response = Http::withHeaders([
        'Authorization' => 'Bearer ' . env('RUNPOD_API_KEY'),
        'Content-Type' => 'application/json'
    ])->post("https://api.runpod.ai/v2/" . env('RUNPOD_ENDPOINT_ID') . "/run", [
        'input' => [
            'image_url' => $imageUrl,
            'debug' => $debug
        ]
    ]);
    
    return response()->json($response->json());
}

public function jobStatus($jobId) {
    $response = Http::withHeaders([
        'Authorization' => 'Bearer ' . env('RUNPOD_API_KEY')
    ])->get("https://api.runpod.ai/v2/" . env('RUNPOD_ENDPOINT_ID') . "/status/{$jobId}");
    
    return response()->json($response->json());
}
```

### Python/Django Example

```python
# views.py
import requests
import os

def analyze(request):
    image_url = request.POST.get('image_url')
    debug = request.POST.get('debug', False)
    
    response = requests.post(
        f"https://api.runpod.ai/v2/{os.getenv('RUNPOD_ENDPOINT_ID')}/run",
        headers={
            'Authorization': f"Bearer {os.getenv('RUNPOD_API_KEY')}",
            'Content-Type': 'application/json'
        },
        json={
            'input': {
                'image_url': image_url,
                'debug': debug
            }
        }
    )
    
    return JsonResponse(response.json())

def job_status(request, job_id):
    response = requests.get(
        f"https://api.runpod.ai/v2/{os.getenv('RUNPOD_ENDPOINT_ID')}/status/{job_id}",
        headers={
            'Authorization': f"Bearer {os.getenv('RUNPOD_API_KEY')}"
        }
    )
    
    return JsonResponse(response.json())
```

## 🔧 Configuration

### RunPod Endpoint Settings

1. **GPU**: RTX 4090 or A4000 (recommended)
2. **Workers**:
   - Active: 0 (use FlashBoot)
   - Max: 3-5
3. **FlashBoot**: Enabled
4. **Container Disk**: 10 GB
5. **Execution Timeout**: 120 seconds

### Web App Environment Variables

```env
# RunPod
RUNPOD_API_KEY=your-api-key
RUNPOD_ENDPOINT_ID=your-endpoint-id

# S3/Spaces
AWS_ACCESS_KEY_ID=your-access-key
AWS_SECRET_ACCESS_KEY=your-secret-key
AWS_REGION=fra1
S3_BUCKET=kisdentalchart
S3_ENDPOINT=https://fra1.digitaloceanspaces.com
```

## 📊 Expected Performance

| Metric | Value |
|--------|-------|
| Job submission | ~100ms |
| Cold start (FlashBoot) | <200ms |
| Inference (GPU) | 15-25 seconds |
| Total (first request) | ~16-26 seconds |
| Total (subsequent) | ~15-25 seconds |

## 💰 Cost Estimate

### Low Volume (100 images/month)
- RunPod: $1
- S3: $5
- **Total: $6/month**

### Medium Volume (1,000 images/month)
- RunPod: $10
- S3: $5
- **Total: $15/month**

### High Volume (10,000 images/month)
- RunPod: $100
- S3: $10
- **Total: $110/month**

## 🎯 Success Criteria

After deployment, you should see:

✅ Job submission in <1 second  
✅ Inference completion in 15-25 seconds  
✅ 200-300 findings per image  
✅ CSV data returned  
✅ Debug images (if requested)  
✅ No timeouts  
✅ No OOM errors  

## 📞 Support

- **RunPod Issues**: https://discord.gg/runpod
- **Model Issues**: https://github.com/stmharry/dental-pano-ai
- **This Service**: Create issue in this repo

## 🔄 Next Actions

1. ✅ Push code to GitHub
2. ⏳ Wait for RunPod rebuild
3. ✅ Test endpoint
4. 🔨 Integrate with web app
5. 🎉 Deploy to production

