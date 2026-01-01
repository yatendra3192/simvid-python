# Deployment Options for Aiezzy Simvid

## Current: Railway
- Good for development and small scale
- Limitations: Shared CPU, 8GB RAM max, expensive at scale
- Cost: ~$20-50/month for basic usage

---

## Recommended: Hetzner + Coolify (Best Value)

### Why Hetzner?
- **Dedicated CPU cores** (not shared like Railway/Render)
- 3-5x cheaper than AWS/GCP for same specs
- European data centers (low latency)
- Excellent for CPU-intensive workloads

### Setup Steps

1. **Create Hetzner Account**: https://hetzner.cloud

2. **Create Server** (recommended: CPX31 or CCX23):
```
Location: Choose nearest to your users
OS: Ubuntu 22.04
Type: CPX31 (4 vCPU, 8GB) - $15/mo
      or CCX23 (4 dedicated, 16GB) - $35/mo
```

3. **Install Coolify** (one command):
```bash
ssh root@your-server-ip
curl -fsSL https://cdn.coollabs.io/coolify/install.sh | bash
```

4. **Access Coolify Dashboard**: http://your-server-ip:8000

5. **Deploy Your App**:
   - Add GitHub repository
   - Set environment variables:
     ```
     REDIS_URL=redis://localhost:6379
     USE_CELERY=true
     WEB_WORKERS=4
     VIDEO_WORKERS=3
     ```
   - Deploy!

### Architecture on Hetzner

```
Single Server (CPX31 - $15/mo):
├── Coolify (management)
├── Redis (queue)
├── Web App (4 workers)
├── Celery Workers (3 video workers)
└── Nginx (reverse proxy + SSL)
```

For 300+ users, add a second server for workers.

---

## Alternative: Fly.io (Good for Global)

### Pros
- Edge deployment (fast globally)
- Easy scaling
- Good free tier

### Setup
```bash
# Install flyctl
curl -L https://fly.io/install.sh | sh

# Deploy
fly launch
fly secrets set REDIS_URL=redis://...
fly scale count 2  # 2 web instances
```

### fly.toml
```toml
app = "aiezzy-video"
primary_region = "iad"

[build]
  dockerfile = "Dockerfile"

[http_service]
  internal_port = 5000
  force_https = true
  auto_start_machines = true
  min_machines_running = 1

[[services]]
  internal_port = 5000
  protocol = "tcp"

  [[services.ports]]
    port = 443
    handlers = ["tls", "http"]

[processes]
  web = "gunicorn app:app --workers 4 --bind 0.0.0.0:5000"
  worker = "celery -A celery_app worker --concurrency=2"
```

Cost: ~$10-30/mo for small scale

---

## Alternative: DigitalOcean App Platform

### Pros
- Simple deployment
- Managed databases
- Predictable pricing

### Setup
1. Connect GitHub repo
2. Add Redis database ($15/mo)
3. Configure:
   - Web service: 2 instances
   - Worker service: 2 instances

Cost: ~$40-80/mo

---

## Alternative: AWS (Maximum Scale)

For 1000+ users, use AWS with spot instances:

### Architecture
```
ALB (Load Balancer)
  ├── ECS Fargate (Web) - 4 tasks
  ├── ECS Fargate (Workers) - 8 tasks (spot instances)
  ├── ElastiCache (Redis)
  └── S3 (file storage)
```

### Cost Optimization
- Use Spot instances for workers (70% cheaper)
- Use S3 for file storage (cheaper than EBS)
- Use CloudFront for video delivery

Cost: ~$100-300/mo for 1000 users

---

## Quick Comparison

| Scale | Best Option | Monthly Cost |
|-------|-------------|--------------|
| <50 users | Railway (current) | $20-50 |
| 50-200 users | Hetzner CPX31 + Coolify | $15-25 |
| 200-500 users | Hetzner CCX33 + Coolify | $50-70 |
| 500-1000 users | AWS ECS with Spot | $150-300 |
| 1000+ users | AWS/GCP with auto-scaling | $300+ |

---

## Migration from Railway

1. Export environment variables from Railway
2. Set up new hosting (Hetzner/Fly.io)
3. Update DNS: point video.aiezzy.com to new server
4. Test thoroughly before switching

### DNS Update (Cloudflare recommended)
```
Type: A
Name: video
Content: <new-server-ip>
Proxy: Yes (for DDoS protection)
```

---

## Recommended Action Plan

### Immediate (Stay on Railway)
- Enable Redis addon if not already
- Set USE_CELERY=true
- Monitor performance

### Short-term (1-2 weeks)
- Set up Hetzner CPX31 ($15/mo)
- Install Coolify
- Test deployment
- Migrate when ready

### Long-term (if growth continues)
- Add dedicated worker servers
- Implement S3 for file storage
- Add CDN for video delivery
