# StorePulse API Service

Cloud Run API service for StorePulse platform. Handles metric ingestion from edge gateways and serves data to dashboards with multi-tenant isolation.

## Overview

- **Technology**: Python 3.11 + FastAPI + PostgreSQL
- **Deployment**: Google Cloud Run (always-warm)
- **Authentication**: API Keys (gateways) + JWT (dashboards) 
- **Multi-tenancy**: Row Level Security + tenant context middleware

## API Endpoints

### Ingestion API (Gateways → Cloud)
```
POST /v1/metrics/batch    # Batch metric ingestion
GET  /health              # Health check
```

### Query API (Dashboards → Cloud)  
```
GET  /v1/stores                     # List stores
GET  /v1/stores/{id}/status         # Store status
GET  /v1/stores/{id}/metrics        # Historical metrics
GET  /v1/alerts                     # Alert management
POST /v1/alerts/{id}/acknowledge    # Acknowledge alerts
```

### Admin API (Tenant Management)
```
POST /v1/admin/tenants              # Create tenant
GET  /v1/admin/tenants/{id}/stats   # Tenant statistics
POST /v1/admin/tenants/{id}/stores  # Create store
POST /v1/admin/api-keys/generate    # Generate API key
```

## Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Gateways      │───▶│   Cloud Run     │───▶│   PostgreSQL    │
│   (API Keys)    │    │   (Always-On)   │    │   (RLS Enabled) │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                              │
                              ▼
                       ┌─────────────────┐
                       │    Pub/Sub      │
                       │    (Queue)      │
                       └─────────────────┘
```

## Development Setup

```bash
cd services/api

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your settings

# Run locally
uvicorn main:app --reload --port 8080

# Run tests
pytest

# Type checking
mypy .
```

## Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:pass@host/db

# Authentication  
JWT_SECRET_KEY=your-jwt-secret
API_KEY_CACHE_TTL=300

# External Services
PUBSUB_TOPIC=projects/your-project/topics/metrics-queue
WHATSAPP_API_TOKEN=your-whatsapp-token

# Monitoring
LOG_LEVEL=INFO
TENANT_LIMITS_CHECK_INTERVAL=3600
```

## Deployment

```bash
# Build Docker image
docker build -t gcr.io/your-project/storepulse-api .

# Deploy to Cloud Run
gcloud run deploy storepulse-api \
    --image gcr.io/your-project/storepulse-api \
    --region us-central1 \
    --min-instances 1 \
    --max-instances 5 \
    --memory 1Gi \
    --cpu 1
```

## Multi-Tenant Features

- **Automatic tenant isolation** via middleware
- **API key validation** with tenant context
- **Row Level Security** for data isolation
- **Tenant limits** enforcement (stores, cost)
- **Usage analytics** per tenant

## Testing

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# Load testing
locust -f tests/load/locustfile.py
```

## Monitoring

- **Health endpoint**: `/health`
- **Metrics**: Custom Cloud Monitoring metrics
- **Logging**: Structured JSON logs
- **Tracing**: Cloud Trace integration