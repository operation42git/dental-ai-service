# Setup Checklist

Complete setup guide for deploying the dental AI service.

## ☐ 1. S3/Spaces Setup

### Create Lifecycle Rule for Temp Files

1. Go to DigitalOcean Spaces → Your Bucket (`kisdentalchart`)
2. Settings → Lifecycle Rules
3. Add new rule:
   - **Name**: "Delete temp files"
   - **Prefix**: `temp/`
   - **Delete after**: 1 day
4. Save

This automatically deletes temp files after 24 hours.

### Verify Folder Structure

Your bucket should have:
```
kisdentalchart/
├── temp/              # Auto-deleted after 24 hours
│   └── job-{id}/
│       ├── semantic-segmentation.jpg
│       └── instance-detection.jpg
├── patients/          # Permanent storage
│   └── {patient-id}/
│       └── analysis-{timestamp}/
│           ├── input.jpg
│           ├── findings.csv
│           └── debug/
```

## ☐ 2. RunPod Setup

### Sign Up

1. Go to [RunPod.io](https://www.runpod.io/)
2. Create account
3. Add payment method (get $5-$500 credit bonus)

### Create API Key

1. Dashboard → Settings → API Keys
2. Create new key
3. Copy and save securely

### Create Serverless Endpoint

1. Dashboard → Serverless → New Endpoint
2. Configure:
   - **Name**: `dental-ai-inference`
   - **Source**: GitHub
   - **Repository**: `operation42git/dental-ai-service`
   - **Branch**: `main`
   - **Dockerfile Path**: `Dockerfile.runpod`
   - **GPU Type**: RTX 4090 (recommended) or A4000
   - **Workers**:
     - Active Workers: `0`
     - Max Workers: `3`
   - **FlashBoot**: ✅ Enabled
   - **Container Disk**: 10 GB
   - **Execution Timeout**: 120 seconds

### Add Environment Variables

In endpoint settings, add:

```
AWS_ACCESS_KEY_ID=DO0098XXNE6ZFUV7EA3G
AWS_SECRET_ACCESS_KEY=IB8y11j/XFL+RcMYjB754fZVe45XACQRe1q7FWyLsG4
AWS_REGION=fra1
S3_BUCKET=https://kisdentalchart.fra1.digitaloceanspaces.com
S3_TEMP_PREFIX=temp/
```

### Deploy

1. Click "Deploy"
2. Wait for build (~10-15 minutes)
3. Copy Endpoint ID (e.g., `cqpnz9dyo9lu2x`)

## ☐ 3. Test RunPod Endpoint

### Test in RunPod Interface

1. Go to your endpoint → Requests tab
2. Input:
```json
{
  "input": {
    "image_url": "https://fra1.digitaloceanspaces.com/kisdentalchart/Staging/photos/Tomić Ivan, 1985-11-11/AI test 1/input/cc63add834ce47c78c0d016a7c29fc13.jpeg",
    "debug": true
  }
}
```
3. Click "Run"
4. Wait ~20 seconds
5. Verify output has:
   - ✅ `findings` array
   - ✅ `csv_data` string
   - ✅ `debug_image_urls` with S3 URLs
   - ✅ Images uploaded to `temp/job-{id}/` in S3

### Test with curl

```bash
curl -X POST https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "input": {
      "image_url": "https://fra1.digitaloceanspaces.com/kisdentalchart/test-image.jpg",
      "debug": true
    }
  }'
```

## ☐ 4. Web App Integration

### Add Environment Variables to Web App

```env
RUNPOD_API_KEY=your-runpod-api-key
RUNPOD_ENDPOINT_ID=your-endpoint-id
AWS_ACCESS_KEY_ID=DO0098XXNE6ZFUV7EA3G
AWS_SECRET_ACCESS_KEY=IB8y11j/XFL+RcMYjB754fZVe45XACQRe1q7FWyLsG4
AWS_REGION=fra1
S3_BUCKET=kisdentalchart
S3_ENDPOINT=https://fra1.digitaloceanspaces.com
```

### Implement API Endpoints

See `NEXT_STEPS.md` for code examples in:
- Next.js
- Laravel
- Django

### Test Full Flow

1. Upload image in web app
2. Submit to RunPod
3. Poll for results
4. Display findings and images
5. Save to permanent S3 if approved

## ☐ 5. Production Checklist

### Security
- ✅ API keys stored server-side only
- ✅ Never expose RunPod API key in frontend
- ✅ S3 bucket has proper CORS settings
- ✅ Temp folder has lifecycle rule

### Performance
- ✅ FlashBoot enabled (<200ms cold start)
- ✅ GPU selected (not CPU)
- ✅ Execution timeout set to 120s
- ✅ Max workers set for traffic

### Monitoring
- ✅ Set up RunPod alerts
- ✅ Monitor costs in RunPod dashboard
- ✅ Track success/failure rates
- ✅ Log errors in web app

### Backup Plan
- ✅ Document RunPod endpoint ID
- ✅ Keep API key secure
- ✅ Have rollback plan if needed

## ☐ 6. User Workflow

### Typical Flow

1. **User uploads image** → Web app uploads to temp S3
2. **Submit to RunPod** → Returns job ID (~1s)
3. **Show loading** → Poll every 2 seconds
4. **Display results** → Show findings + images from temp S3
5. **User reviews** → Can rerun if needed
6. **User approves** → Copy to permanent S3 + save to database
7. **Temp files expire** → Auto-deleted after 24 hours

### Edge Cases

- **User closes browser**: Job continues, results in temp S3
- **User rejects**: Temp files expire, no permanent storage
- **User reruns**: New job, new temp folder
- **Network error**: Retry or show error

## 📊 Success Metrics

After deployment, verify:

- ✅ Response time <1s for job submission
- ✅ Inference time 15-25s
- ✅ Success rate >95%
- ✅ Temp files auto-delete
- ✅ Cost per image ~$0.01
- ✅ No timeouts
- ✅ No OOM errors

## 🎉 You're Done!

Once all checkboxes are complete, your dental AI service is production-ready!

