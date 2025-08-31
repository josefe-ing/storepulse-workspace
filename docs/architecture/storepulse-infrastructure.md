# StorePulse - Infraestructura MVP Hybrid Serverless

## 1. Visión General de Infraestructura MVP

Infraestructura híbrida serverless optimizada para **30 tiendas máximo**, **~19.5K eventos/hora** y **$265/mes de presupuesto**. Combina Cloud Run always-warm para baja latencia con Cloud Functions para procesamiento asíncrono.

```
┌─────────────────────────────────────────────────────────┐
│                 Google Cloud Platform MVP                  │
│                   (us-central1)                           │
│                                                           │
│  ┌─────────────────────────────────────────────────┐    │
│  │             Networking (Simplificado)            │    │
│  │         [Cloud Load Balancer] → [HTTPS]          │    │
│  └─────────────────────────────────────────────────┘    │
│                          ↓                              │
│  ┌─────────────────────────────────────────────────┐    │
│  │          Compute (Hybrid Serverless)             │    │
│  │    [Cloud Run Always-Warm] [Cloud Functions]     │    │
│  └─────────────────────────────────────────────────┘    │
│                          ↓                              │
│  ┌─────────────────────────────────────────────────┐    │
│  │           Data (PostgreSQL Standard)             │    │
│  │     [Cloud SQL] [Pub/Sub] [Cloud Storage]        │    │
│  └─────────────────────────────────────────────────┘    │
│                          ↓                              │
│  ┌─────────────────────────────────────────────────┐    │
│  │        Monitoring (Cloud Native)                 │    │
│  │      [Cloud Logging] [Cloud Monitoring]          │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## 2. Componentes Cloud Simplificados

### 2.1 Networking MVP

#### Load Balancer Básico
```yaml
Type: Cloud Load Balancer (Regional)
Region: us-central1
Features:
  - SSL termination automático
  - Managed certificate (auto-renovación)
  - No CDN (para MVP - Vercel maneja cliente)
  - No Cloud Armor (traffic bajo)

Configuration:
  Frontend:
    - HTTPS: api.storepulse.io
    - Certificate: Google-managed
  
  Backend:
    - cloud-run-api: storepulse-api service
    - health-check: /health endpoint
```

#### Red Simplificada (No VPC Custom)
```yaml
# Usa Default VPC para simplicidad MVP
Network: default
Region: us-central1
Zones: us-central1-a, us-central1-b

# Solo reglas esenciales
Firewall:
  - allow-https: internet → :443
  - allow-ssh: authorized IPs → :22 (admin only)
  - default-deny: resto bloqueado
```

### 2.2 Compute Híbrido Serverless

#### Cloud Run API (Always-Warm)
```yaml
# API Principal - Siempre activo para <200ms latency
storepulse-api:
  image: gcr.io/storepulse-prod/api:latest
  memory: 1Gi              # Optimizado costo
  cpu: 1                   # Suficiente para 30 tiendas
  min_instances: 1         # ALWAYS-WARM - No cold starts
  max_instances: 5         # Escala conservadora
  concurrency: 100         # 30 tiendas * 2 req/min = ~60 concurrent
  timeout: 60s
  port: 8080
  
  # Variables críticas
  environment:
    - DATABASE_URL: Cloud SQL connection
    - PUBSUB_TOPIC: metrics-queue
    - WHATSAPP_TOKEN: secret from Secret Manager
    
# Dashboard Admin (Opcional - puede estar en API)
storepulse-admin:
  image: gcr.io/storepulse-prod/admin:latest
  memory: 512Mi
  cpu: 1
  min_instances: 0         # Scale to zero OK (uso esporádico)
  max_instances: 2
  ingress: internal-and-cloud-load-balancing
```

#### Cloud Functions (Processing)
```yaml
# Procesador Principal
process-metrics:
  runtime: python311
  memory: 512MB           # Procesa batches de ~50 eventos
  timeout: 60s
  trigger: pubsub
  topic: metrics-queue
  max_instances: 10       # Más que suficiente para 19K events/hora
  retry_policy: true
  
  tasks:
    - Parse and validate metrics batch
    - Insert into PostgreSQL
    - Evaluate simple alert rules
    - Send WhatsApp if alert triggered
  
# Limpieza Diaria
cleanup-old-data:
  runtime: python311
  memory: 256MB
  timeout: 300s
  trigger: scheduler
  schedule: "0 6 * * *"    # Daily at 6 AM
  max_instances: 1
  
  tasks:
    - Delete metrics older than 1 year
    - Archive old alerts
    - Generate daily reports
```

### 2.3 Data Storage MVP

#### Cloud SQL PostgreSQL (Costo-Optimizado)
```yaml
Instance: storepulse-db-mvp
Version: PostgreSQL 15
Tier: db-custom-1-3840      # 1 vCPU, 3.75GB RAM - $68/mes

Configuration:
  vCPUs: 1                  # Suficiente para 30 tiendas
  Memory: 3.75GB           # ~14M registros/mes caben cómodo
  Storage: 20GB SSD        # Auto-resize habilitado
  Max Storage: 100GB       # Límite para control de costos
  
Availability:
  Type: Zonal             # Regional = 2x costo (no MVP)
  Zone: us-central1-a
  
Backup:
  Schedule: Daily at 03:00 UTC
  Retention: 7 days       # Reducido para MVP
  Point-in-time: Enabled  # Últimas 7 días
  
Connections:
  Max: 50                 # Conservador para controlar uso
  Pool: PgBouncer en API  # Connection pooling
  
Maintenance:
  Window: Sunday 04:00-05:00 UTC
  Updates: Notify only (manual approval)
```

#### Cloud Storage (Mínimo)
```yaml
# Terraform State
storepulse-terraform-state:
  Location: us-central1
  Storage Class: Regional
  Versioning: Enabled
  
# Backups de DB (adicional)
storepulse-db-backups:
  Location: us-central1
  Storage Class: Standard
  Lifecycle: Delete after 30 days
  
# Logs exportados (opcional)
storepulse-logs:
  Location: us-central1
  Storage Class: Standard 
  Lifecycle: Delete after 90 days
```

### 2.4 Message Queue Simplificado

#### Pub/Sub MVP
```yaml
# Un solo topic para MVP - Simplicidad
Topics:
  metrics-queue:
    Message Retention: 1 day     # Reducido - procesamiento rápido
    Region: us-central1
    
    Subscriptions:
      - process-metrics-sub:
          Ack Deadline: 30s        # Procesamiento rápido esperado
          Retry Policy: 
            min_backoff: 10s
            max_backoff: 60s
            max_retry_delay: 600s
          Dead Letter: metrics-dlq  # Para debugging
          
# Topic para dead letter (debugging)
metrics-dlq:
  Message Retention: 7 days      # Retener para debug
  
# Estimación de uso
Estimated Usage:
  - Messages/hour: ~650 per store = 19,500 total
  - Messages/month: ~14M
  - Cost: ~$15/mes (bien dentro de presupuesto)
```

## 3. Infraestructura Edge (Tiendas)

### 3.1 Gateway por Tienda (Simplificado)

#### Hardware Mínimo (Costo-Eficiente)
```yaml
# Opción 1: Mini PC existente
Hardware:
  CPU: Intel i3-8100 o AMD Ryzen 3 (4 cores)
  RAM: 4GB (suficiente para gateway + buffer)
  Storage: 64GB SSD (SQLite + logs)
  Network: Ethernet 100Mbps
  
# Opción 2: Raspberry Pi (ultra low-cost)
Hardware Alt:
  Model: Raspberry Pi 4 (4GB RAM)
  Storage: 32GB microSD + USB SSD 64GB
  Network: Ethernet + WiFi
  Cost: <$100 por tienda
  
Operating System:
  Primary: Ubuntu Server 22.04 LTS
  Alternative: Raspberry Pi OS
  Remote Access: SSH + VPN
```

#### Software Stack Simplificado
```yaml
# Stack mínimo para 30 tiendas
Software:
  - Docker 24.0+ (containerization)
  - Python 3.11 (gateway FastAPI)
  - SQLite 3 (buffer local)
  - No Nginx (direct port binding OK para MVP)
  - No Redis (in-memory caching)
  
# Storage allocation
Disk Usage:
  - Gateway container: ~200MB
  - SQLite buffer: ~50MB/día (retention 7 días)
  - Logs: ~10MB/día (retention 30 días)
  - OS + overhead: ~2GB
  - Total: <4GB (plenty margin)
```

#### Deployment Ultra-Simple
```dockerfile
# Gateway Dockerfile Optimizado
FROM python:3.11-slim

WORKDIR /app

# Install deps
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Health check built-in
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
```

```yaml
# docker-compose.yml - Sin nginx para MVP
version: '3.8'

services:
  gateway:
    image: storepulse/gateway:${VERSION:-latest}
    container_name: sp-gateway
    ports:
      - "8080:8080"    # Direct access, no reverse proxy
    volumes:
      - ./data:/data    # SQLite buffer + logs
    environment:
      - STORE_ID=${STORE_ID}
      - TENANT_ID=${TENANT_ID}
      - API_KEY=${API_KEY}
      - CLOUD_API_URL=${CLOUD_API_URL}
      - SYNC_INTERVAL_SECONDS=30
      - BATCH_SIZE=50
      - LOG_LEVEL=INFO
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

### 3.2 Agentes POS (Go - Single Binary)

#### Windows Service (Go Executable)
```yaml
# Agente Go - Single binary deployment
Executable: storepulse-agent.exe
Size: ~10MB (static binary)
Location: C:\StorePulse\

Capabilities:
  - Monitor POS process health
  - Check network connectivity  
  - Test printer/scanner status
  - Send metrics to Gateway (HTTP POST)
  - Automatic recovery/restart
  - Minimal resource usage (<5MB RAM)

Configuration:
  Config File: C:\StorePulse\config.yaml
  Log File: C:\StorePulse\logs\agent.log
  Metrics Endpoint: http://gateway-ip:8080/metrics
  
Windows Service:
  Service Name: StorePulse Agent
  Start Type: Automatic
  Recovery: Restart on failure
```

#### Service Installation Script
```powershell
# install-agent.ps1 - Deployment script
# Download latest binary
$url = "https://releases.storepulse.io/agent/latest/windows/storepulse-agent.exe"
$dest = "C:\StorePulse\storepulse-agent.exe"

# Create directory
New-Item -Path "C:\StorePulse" -ItemType Directory -Force
New-Item -Path "C:\StorePulse\logs" -ItemType Directory -Force

# Download binary
Invoke-WebRequest -Uri $url -OutFile $dest

# Install as service
sc.exe create "StorePulseAgent" binpath= "C:\StorePulse\storepulse-agent.exe" start= auto
sc.exe description "StorePulseAgent" "StorePulse POS monitoring agent"
sc.exe start "StorePulseAgent"

Write-Host "StorePulse Agent installed successfully"
```

#### Config Template
```yaml
# C:\StorePulse\config.yaml
agent:
  store_id: "${STORE_ID}"
  pos_id: "${POS_ID}"  # POS01, POS02, etc.
  gateway_url: "http://192.168.1.100:8080"
  
monitoring:
  interval_seconds: 30
  pos_process_name: "pos_software.exe"
  printer_ip: "192.168.1.201"
  
logging:
  level: "info"
  max_size_mb: 10
  max_files: 5
```

## 4. CI/CD Simplificado MVP

### 4.1 GitHub Actions (Minimal)

```yaml
# .github/workflows/deploy-mvp.yml
name: Deploy StorePulse MVP

on:
  push:
    branches: [main]
    paths: 
      - 'api/**'
      - 'functions/**'
      - '.github/workflows/**'

env:
  PROJECT_ID: storepulse-prod
  REGION: us-central1

jobs:
  # Tests básicos - No coverage ni linting para MVP
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'
          
      - name: Install dependencies
        run: |
          pip install -r api/requirements.txt
          pip install pytest
          
      - name: Run basic tests
        run: |
          cd api && python -m pytest tests/ -v

  # Deploy Cloud Run API
  deploy-api:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
          
      - name: Set up Cloud SDK
        uses: google-github-actions/setup-gcloud@v1
        with:
          project_id: ${{ env.PROJECT_ID }}
          
      - name: Build and deploy API
        run: |
          cd api
          gcloud builds submit --tag gcr.io/$PROJECT_ID/api:$GITHUB_SHA
          
          gcloud run deploy storepulse-api \
            --image gcr.io/$PROJECT_ID/api:$GITHUB_SHA \
            --region $REGION \
            --platform managed \
            --allow-unauthenticated \
            --set-env-vars PROJECT_ID=$PROJECT_ID \
            --min-instances 1 \
            --max-instances 5 \
            --memory 1Gi \
            --cpu 1
            
      - name: Health check
        run: |
          sleep 30  # Wait for deployment
          API_URL=$(gcloud run services describe storepulse-api --region $REGION --format 'value(status.url)')
          curl -f $API_URL/health
          echo "API deployed successfully at $API_URL"
  
  # Deploy Cloud Function
  deploy-function:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    steps:
      - uses: actions/checkout@v4
      
      - name: Authenticate to Google Cloud
        uses: google-github-actions/auth@v1
        with:
          credentials_json: ${{ secrets.GCP_SA_KEY }}
          
      - name: Deploy function
        run: |
          cd functions
          gcloud functions deploy process-metrics \
            --gen2 \
            --runtime python311 \
            --trigger-topic metrics-queue \
            --region $REGION \
            --memory 512MB \
            --timeout 60s \
            --max-instances 10 \
            --set-env-vars PROJECT_ID=$PROJECT_ID
```

### 4.2 Deployment Strategy MVP

```yaml
# Estrategia simple para MVP
Strategy: Rolling Update (Cloud Run nativo)

Steps:
  1. Build new container image
  2. Deploy to Cloud Run (automatic rolling)
  3. Health check nuevo revision
  4. Switch traffic 100% si health OK
  5. Monitor logs for 10 minutes

Rollback Plan:
  - Manual: gcloud run services update-traffic --to-revisions=previous=100
  - Automatic: Cloud Run health check failure
  - Database: No breaking schema changes
  - Time to rollback: <2 minutes
  
# Edge deployment (separado)
Edge Strategy: Manual deployment
  1. Build gateway Docker image
  2. Push to registry
  3. Update docker-compose.yml per store
  4. Rolling update per tienda (1-2 por día)
```

## 5. Monitoring MVP (Cloud Native)

### 5.1 Cloud Monitoring (Automático)

```yaml
# Health Checks básicos
api-uptime-check:
  Type: HTTPS
  URL: https://api.storepulse.io/health
  Frequency: 60 seconds
  Locations: [us-central1]  # Single region para MVP
  Timeout: 10s
  
# Alertas críticas solamente
Critical Alerts:
  api_down:
    Condition: Uptime check fails > 2 minutes
    Notification: email + SMS
    
  high_error_rate:
    Condition: HTTP 5xx errors > 5% in 5 minutes
    Notification: email
    
  database_down:
    Condition: Cloud SQL instance down
    Notification: email + SMS
    
  cost_spike:
    Condition: Daily spend > $15 (proyección $450/mes)
    Notification: email

# Métricas automáticas (sin configuración)
Built-in Metrics:
  - Cloud Run: Request latency, error rate, instance count
  - Cloud SQL: CPU, memory, connections, storage
  - Cloud Functions: Execution time, error rate, invocations
  - Pub/Sub: Message age, undelivered messages
```

### 5.2 Logging Simplificado

```yaml
# Default Cloud Logging (sin routing complejo)
Logging Strategy:
  - Cloud Run: stdout/stderr automático
  - Cloud Functions: print() statements
  - Edge Gateway: JSON logs a stdout
  
# Retention básico
Retention:
  Cloud Logging: 30 days (gratis tier)
  No export to Storage (costo extra innecesario)
  
# Structured logging format
Log Format:
  timestamp: ISO 8601
  level: DEBUG|INFO|WARNING|ERROR|CRITICAL
  service: api|function|gateway
  tenant_id: cliente1
  store_id: T01
  message: human readable
  metadata: {key: value}
  
# Solo errores críticos van a alertas
Error Alerting:
  - Cloud Function errors -> email
  - Cloud Run 5xx errors -> email
  - Gateway sync failures -> (monitoreado por falta de métricas)
```

### 5.3 Dashboard Operacional

```yaml
# Cloud Monitoring Dashboard (Gratis)
Operational Panels:
  - API Request Rate (req/min)
  - API Latency P95
  - HTTP Error Rate %
  - Cloud Run Instance Count
  - Cloud SQL CPU %
  - Cloud SQL Connections
  - Pub/Sub Message Age
  - Daily Cost ($)

# Custom Business Metrics (via API)
Business Panels:
  - Stores Online Count
  - POS Offline Count
  - Temperature Alerts Today
  - Last Data Received (freshness)
  - WhatsApp Messages Sent
  - Total Devices (POS + Sensors)
  
# Access:
  - Operations: Cloud Console (Google accounts)
  - Business: StorePulse Admin Dashboard
```

## 6. Security MVP (Essentials Only)

### 6.1 IAM Simplificado

```yaml
# Service Accounts mínimos
storepulse-api-sa:
  Description: "Cloud Run API service account"
  Roles:
    - cloudsql.client           # Database access
    - pubsub.publisher          # Send messages
    - secretmanager.secretAccessor  # Read secrets
    
storepulse-function-sa:
  Description: "Cloud Function processor"
  Roles:
    - cloudsql.editor           # Insert metrics
    - pubsub.subscriber         # Process messages
    - secretmanager.secretAccessor

# Human Access (mínimo para MVP)
Developer Access:
  - Project Editor role (temporal para MVP)
  - Can deploy Cloud Run/Functions
  - Can read logs and metrics
  - NO production database admin
```

### 6.2 Secrets (Secret Manager)

```yaml
# Solo secretos esenciales
Secrets:
  db-connection-string:     # PostgreSQL connection
    value: "postgresql://user:pass@host/db"
    access: api-sa, function-sa
    
  whatsapp-api-token:       # WhatsApp Business API
    value: "EAAxx..."
    access: function-sa
    
  api-keys:                 # Store API keys (JSON)
    value: '{"T01": "key1", "T02": "key2"}'
    access: api-sa

Policy:
  - Manual rotation (no auto para MVP)
  - Access logged automatically
  - No versioning (latest only)
```

### 6.3 Network Security Básico

```yaml
# Sin Cloud Armor para MVP (costo extra)
Security:
  - HTTPS enforced (managed certificate)
  - Default VPC firewall (allow HTTPS only)
  - Cloud Run: Allow unauthenticated (API pública)
  - Cloud Functions: Private (Pub/Sub trigger only)
  
# Rate limiting nativo
Cloud Run Limits:
  - Max 100 concurrent requests per instance
  - Max 5 instances = 500 concurrent max
  - Request timeout: 60s
  
# SSL/TLS automático
TLS:
  - Google-managed certificate
  - Auto-renewal
  - TLS 1.2+ only
  - Modern cipher suites
```

## 7. Disaster Recovery MVP

### 7.1 Backup Strategy Simple

```yaml
# Database backup (automático)
Cloud SQL Backup:
  Type: Automated daily backup
  Time: 03:00 UTC
  Retention: 7 days
  Cross-region: NO (costo extra innecesario)
  Point-in-time recovery: YES (7 days)
  
# Terraform state
Infrastructure:
  State: Cloud Storage bucket (versioned)
  Config: Git repository
  
# Container images
Application:
  Registry: Google Container Registry
  Retention: Last 10 images
  
# No backup de logs (recreables)
```

### 7.2 Incident Response Simple

```yaml
# Equipo mínimo
Incident Team:
  Primary: Lead Developer
  Escalation: CTO/Business Owner
  
# Canales de comunicación
Communication:
  Internal: Email/WhatsApp
  Client: WhatsApp business account
  
# Escenarios principales
Common Issues:
  1. API down -> Check Cloud Run logs -> Redeploy if needed
  2. Database slow -> Check Cloud SQL metrics -> Scale up if needed  
  3. High costs -> Check daily spend alerts
  4. Gateway offline -> SSH to store server -> Restart docker
  
Recovery Time:
  - Cloud services: <30 minutes (mostly automated)
  - Edge services: <2 hours (manual access required)
```

## 8. Cost Optimization MVP

### 8.1 Resource Optimization (Target $265/mes)

```yaml
# Cloud Run (Always-warm optimizado)
API Service:
  Min instances: 1          # Always warm pero mínimo
  Max instances: 5          # Límite conservador
  Memory: 1Gi               # Balance costo/performance
  CPU: 1                    # Sufficient for 30 stores
  
# Cloud SQL (Costo-optimizado)
Database:
  Tier: db-custom-1-3840    # $68/mes instead of $120+
  Storage: 20GB             # Auto-resize enabled
  Backups: 7 days           # Not 30 days
  
# Cloud Functions
Processor:
  Max instances: 10         # Avoid runaway scaling
  Memory: 512MB             # Right-sized
  Timeout: 60s              # Prevent long-running
```

### 8.2 Cost Monitoring (Crucial para MVP)

```yaml
# Budget alerts (configuración crítica)
Main Budget:
  Name: "storepulse-monthly-budget"
  Amount: $300              # Buffer sobre $265 target
  Alerts:
    - 50% ($150): email
    - 80% ($240): email + SMS
    - 100% ($300): email + SMS + Slack
    - 120% ($360): STOP services
    
Per-Service Budgets:
  - Cloud Run: $70/mes max
  - Cloud SQL: $80/mes max
  - Cloud Functions: $50/mes max
  - Pub/Sub: $20/mes max
  
# Daily cost tracking
Daily Monitoring:
  - Check daily spend in Cloud Console
  - Alert if daily spend > $12 (= $360/mes projection)
  - Weekly review of cost trends
```

## 9. Infrastructure as Code (Terraform MVP)

### 9.1 Terraform Simplificado

```hcl
# terraform/main.tf - Todo en un archivo para MVP
terraform {
  required_version = ">= 1.0"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
  
  backend "gcs" {
    bucket = "storepulse-terraform-state"
    prefix = "mvp"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Variables
variable "project_id" {
  description = "GCP project ID"
  type        = string
  default     = "storepulse-prod"
}

variable "region" {
  description = "GCP region"
  type        = string
  default     = "us-central1"
}

# Cloud SQL Instance
resource "google_sql_database_instance" "main" {
  name             = "storepulse-db"
  database_version = "POSTGRES_15"
  region           = var.region
  
  settings {
    tier = "db-custom-1-3840"  # 1 vCPU, 3.75GB RAM
    
    backup_configuration {
      enabled    = true
      start_time = "03:00"
      location   = var.region
    }
    
    database_flags {
      name  = "max_connections"
      value = "50"
    }
    
    disk_size = 20
    disk_type = "PD_SSD"
  }
}

# Cloud Run Service
resource "google_cloud_run_service" "api" {
  name     = "storepulse-api"
  location = var.region
  
  template {
    metadata {
      annotations = {
        "autoscaling.knative.dev/minScale" = "1"
        "autoscaling.knative.dev/maxScale" = "5"
      }
    }
    
    spec {
      containers {
        image = "gcr.io/${var.project_id}/api:latest"
        
        resources {
          limits = {
            cpu    = "1"
            memory = "1Gi"
          }
        }
        
        env {
          name  = "PROJECT_ID"
          value = var.project_id
        }
      }
    }
  }
}

# Pub/Sub Topic
resource "google_pubsub_topic" "metrics" {
  name = "metrics-queue"
}

resource "google_pubsub_subscription" "processor" {
  name  = "process-metrics-sub"
  topic = google_pubsub_topic.metrics.name
  
  ack_deadline_seconds = 30
  
  retry_policy {
    minimum_backoff = "10s"
    maximum_backoff = "60s"
  }
}
```

### 9.2 Edge Deployment (Script Bash)

```bash
#!/bin/bash
# deploy-gateway.sh - Simple deployment script for edge servers

set -e

# Configuration
STORE_ID="$1"
TENANT_ID="$2"
API_KEY="$3"

if [ -z "$STORE_ID" ] || [ -z "$TENANT_ID" ] || [ -z "$API_KEY" ]; then
    echo "Usage: $0 <store_id> <tenant_id> <api_key>"
    exit 1
fi

echo "Deploying StorePulse Gateway for store: $STORE_ID"

# Install Docker if not present
if ! command -v docker &> /dev/null; then
    echo "Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    sudo systemctl enable docker
    sudo systemctl start docker
fi

# Create project directory
sudo mkdir -p /opt/storepulse
sudo mkdir -p /opt/storepulse/data
cd /opt/storepulse

# Create environment file
sudo tee .env > /dev/null <<EOF
STORE_ID=$STORE_ID
TENANT_ID=$TENANT_ID
API_KEY=$API_KEY
CLOUD_API_URL=https://api.storepulse.io
SYNC_INTERVAL_SECONDS=30
BATCH_SIZE=50
LOG_LEVEL=INFO
EOF

# Create docker-compose.yml
sudo tee docker-compose.yml > /dev/null <<'EOF'
version: '3.8'
services:
  gateway:
    image: storepulse/gateway:latest
    container_name: sp-gateway
    ports:
      - "8080:8080"
    volumes:
      - ./data:/data
    env_file:
      - .env
    restart: unless-stopped
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
EOF

# Start services
sudo docker-compose pull
sudo docker-compose up -d

# Verify deployment
sleep 10
if curl -f http://localhost:8080/health; then
    echo "✅ Gateway deployed successfully for store $STORE_ID"
else
    echo "❌ Gateway deployment failed"
    exit 1
fi
```

## 10. Performance MVP (Sin Optimizaciones Complejas)

### 10.1 Caching Simple

```yaml
# Sin Redis para MVP - Caching en memoria
Application Caching:
  - API responses: In-memory cache (5 minutos)
  - Store configs: In-memory cache (30 minutos)
  - Alert rules: In-memory cache (10 minutos)
  
# CDN nativo
Static Assets:
  - Dashboard cliente: Vercel CDN (automático)
  - API responses: Sin cache (datos en tiempo real)
```

### 10.2 Database Performance (Sin Partitioning)

```sql
-- Solo índices esenciales para MVP
-- Primary key: id (automatic)
CREATE INDEX idx_tenant_store_recent ON metrics(tenant_id, store_id, created_at DESC)
WHERE created_at > NOW() - INTERVAL '7 days';

-- Para queries de alertas
CREATE INDEX idx_recent_metrics ON metrics(created_at DESC)
WHERE created_at > NOW() - INTERVAL '1 hour';

-- Auto-vacuum defaults (sin tuning)
-- PostgreSQL defaults son suficientes para 14M registros/mes
```

### 10.3 Proyección de Performance

```yaml
# Con 30 tiendas, 19.5K eventos/hora
Database Size:
  - Daily: ~470K registros
  - Monthly: ~14M registros  
  - Yearly: ~170M registros
  - Storage: ~50GB/año (JSON comprimido)
  
Expected Latency:
  - API responses: <200ms (always-warm)
  - Database queries: <50ms (SSD + indexes)
  - Function processing: <5s per batch
  
Bottlenecks (futuros):
  - 50+ tiendas: Need db-n1-standard-1
  - 100+ tiendas: Consider partitioning
  - 200+ tiendas: Multi-region deployment
```

---
*StorePulse MVP Infrastructure v2.0*
*Hybrid Serverless: Cloud Run + Cloud Functions*  
*Target: 30 tiendas, $265/mes, <200ms latency*
*Last Updated: January 2025*