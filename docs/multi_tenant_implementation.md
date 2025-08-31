# StorePulse Multi-Tenant Implementation Guide

## Overview

StorePulse está diseñado como multi-tenant desde el inicio, permitiendo servir múltiples clientes desde una sola infraestructura compartida. Esta guía detalla la implementación completa del sistema multi-tenant.

## 🏗️ Arquitectura Multi-Tenant

### Modelo de Tenancy
- **Shared Database, Shared Schema**: Todos los tenants comparten la misma base de datos y esquema
- **Row Level Security (RLS)**: Isolación automática de datos por `tenant_id`
- **Single Deployment**: Una sola API sirve múltiples clientes
- **Tenant Context**: Middleware automático para contexto de tenant

### Beneficios
- **Costo-eficiente**: Infraestructura compartida reduce costos por cliente
- **Fácil mantenimiento**: Un solo deployment, un solo update
- **Escalabilidad**: Agregar clientes no requiere nueva infraestructura
- **Seguridad**: RLS garantiza isolación de datos automática

## 📊 Schema de Base de Datos

### Tabla Principal: Tenants
```sql
CREATE TABLE tenants (
    tenant_id VARCHAR(50) PRIMARY KEY,
    company_name VARCHAR(100) NOT NULL,
    plan_type VARCHAR(20) DEFAULT 'basic',  -- 'basic', 'premium'
    max_stores INTEGER DEFAULT 30,
    max_monthly_cost DECIMAL(10,2) DEFAULT 265.00,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    is_active BOOLEAN DEFAULT TRUE,
    
    -- Configuración por cliente
    config JSONB DEFAULT '{}',
    
    -- Para facturación y contacto
    billing_email VARCHAR(100),
    admin_contact VARCHAR(100),
    whatsapp_numbers JSONB DEFAULT '[]',
    
    CONSTRAINT valid_plan CHECK (plan_type IN ('basic', 'premium'))
);
```

### API Keys por Tienda
```sql
CREATE TABLE store_api_keys (
    key_id VARCHAR(64) PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    store_id VARCHAR(50) NOT NULL,
    key_hash VARCHAR(128) NOT NULL,  -- SHA-256 hash
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_used_at TIMESTAMPTZ,
    is_active BOOLEAN DEFAULT TRUE,
    
    FOREIGN KEY (tenant_id, store_id) REFERENCES stores(tenant_id, store_id)
);
```

### Usuarios Dashboard
```sql
CREATE TABLE dashboard_users (
    user_id VARCHAR(100) PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    user_type VARCHAR(20) DEFAULT 'client',
    permissions JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    password_change_required BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    UNIQUE(email, tenant_id)
);
```

### Row Level Security (RLS)
```sql
-- Habilitar RLS en todas las tablas multi-tenant
ALTER TABLE metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE alerts ENABLE ROW LEVEL SECURITY;
ALTER TABLE stores ENABLE ROW LEVEL SECURITY;

-- Política de isolación por tenant
CREATE POLICY tenant_isolation ON metrics
    FOR ALL TO storepulse_app
    USING (tenant_id = current_setting('app.tenant_id'));

CREATE POLICY tenant_isolation ON alerts
    FOR ALL TO storepulse_app
    USING (tenant_id = current_setting('app.tenant_id'));
```

## 🔐 Autenticación Multi-Tenant

### 1. API Key Authentication (Gateways)
```python
# Formato de API Key
api_key = f"store_{tenant_id}_{store_id}_{random_token}"
# Ejemplo: store_cliente1_T01_abc123def456...

# Middleware extrae tenant_id automáticamente
@app.middleware("http")
async def tenant_context_middleware(request: Request, call_next):
    api_key = request.headers.get("Authorization", "").replace("Bearer ", "")
    tenant_id, store_id = await extract_tenant_from_key(api_key)
    
    # Set database context for RLS
    await db.execute(text(f"SET app.tenant_id = '{tenant_id}'"))
    
    request.state.tenant_id = tenant_id
    request.state.store_id = store_id
    
    response = await call_next(request)
    return response
```

### 2. JWT Authentication (Dashboards)
```python
# JWT Payload incluye tenant_id
payload = {
    "sub": user_data["user_id"],
    "tenant_id": user_data["tenant_id"],
    "user_type": user_data.get("user_type", "client"),
    "permissions": user_data.get("permissions", []),
    "exp": expire_time
}

# Dashboard users solo ven datos de su tenant
@router.get("/stores")
async def get_stores(current_user: dict = Depends(get_current_user)):
    tenant_id = current_user["tenant_id"]  # Auto-extraído del JWT
    # RLS automáticamente filtra por tenant_id
    return await get_tenant_stores(tenant_id)
```

## 🚀 Onboarding Process

### Script Automatizado
```bash
# Crear nuevo tenant con 5 tiendas
python scripts/onboard_tenant.py \
    --tenant-id cliente3 \
    --company "Retail Corp" \
    --stores 5 \
    --email admin@retailcorp.com \
    --admin "Juan Pérez" \
    --whatsapp 1234567890
```

### Proceso Step-by-Step
1. **Crear Tenant**: Insertar en tabla `tenants`
2. **Crear Tiendas**: Insertar tiendas en tabla `stores`
3. **Generar API Keys**: Una por tienda para gateways
4. **Crear Usuario Dashboard**: Para acceso web
5. **Generar Deployment Package**: Configs para deployment
6. **Validar Setup**: Verificar que todo funciona

### Deployment Package
```
deployment_package_cliente3/
├── README.md                     # Instrucciones
├── onboarding_results.json       # Resumen completo
├── T01/
│   ├── docker-compose.yml
│   ├── deploy.sh
│   └── pos-agent-config.yaml
├── T02/
│   ├── docker-compose.yml
│   ├── deploy.sh
│   └── pos-agent-config.yaml
└── ...
```

## 🔒 Tenant Isolation

### 1. Database Level
- **Row Level Security**: Automática por `tenant_id`
- **Connection Pooling**: Shared connections con context setting
- **Query Performance**: Índices incluyen `tenant_id`

### 2. Application Level
- **Middleware**: Extrae tenant context automáticamente
- **API Endpoints**: Scope automático por tenant
- **Error Handling**: No leak de información entre tenants

### 3. Resource Level
- **Rate Limiting**: Por tenant_id
- **Cost Monitoring**: Tracking por tenant
- **Feature Flags**: Configuración por tenant

## 📊 Limits and Quotas

### Tenant Limits
```python
class TenantLimitsService:
    async def validate_store_limit(self, tenant_id: str):
        tenant = await get_tenant(tenant_id)
        current_stores = await count_stores(tenant_id)
        
        if current_stores >= tenant.max_stores:
            raise HTTPException(429, "Store limit exceeded")
    
    async def check_cost_limit(self, tenant_id: str) -> float:
        estimated_cost = await calculate_monthly_cost(tenant_id)
        tenant = await get_tenant(tenant_id)
        
        if estimated_cost > tenant.max_monthly_cost * 0.8:  # 80% threshold
            await send_cost_alert(tenant_id, estimated_cost)
        
        return estimated_cost
```

### Cost Monitoring
- **Per-tenant cost tracking**: GCP billing API integration
- **Budget alerts**: 50%, 80%, 100% thresholds
- **Usage analytics**: Events per tenant, cost per event
- **Automatic scaling**: Based on usage patterns

## 🌐 Multi-Tenant APIs

### Ingest API (Gateways → Cloud)
```python
@router.post("/v1/metrics/batch")
async def ingest_metrics(
    batch: MetricsBatch,
    tenant_id: str = Depends(get_tenant_id),  # Auto-extraído del API key
    store_id: str = Depends(get_store_id)
):
    # RLS automáticamente scope por tenant_id
    await process_metrics_batch(batch, tenant_id, store_id)
    return {"status": "success", "processed": len(batch.metrics)}
```

### Query API (Dashboards → Cloud)  
```python
@router.get("/v1/stores/{store_id}/status")
async def get_store_status(
    store_id: str,
    current_user: dict = Depends(get_current_user_jwt)
):
    tenant_id = current_user["tenant_id"]  # Auto-extraído del JWT
    # RLS automáticamente filtra por tenant_id
    return await get_store_status(tenant_id, store_id)
```

## 💰 Economics Multi-Tenant

### Cost Structure
```yaml
Single Tenant Cost: $265/mes
Multi-Tenant Cost (10 clientes):
  Infrastructure: $400/mes total
  Cost per client: $40/mes
  Profit margin: 85%

Break-even: 3 clientes
Sweet spot: 10-50 clientes
```

### Revenue Model
- **Basic Plan**: $299/mes (30 tiendas max)
- **Premium Plan**: $599/mes (100 tiendas max) 
- **Enterprise**: Custom pricing
- **Setup Fee**: $500 one-time

## 🔄 Migration Strategy

### From Single-Tenant
1. **Add tenant_id**: A todas las tablas existentes
2. **Enable RLS**: Con políticas por tenant  
3. **Update middleware**: Para tenant context
4. **Migrate API keys**: Nuevo formato con tenant_id
5. **Test isolation**: Verificar no hay data leakage

### Data Migration
```sql
-- Migrar datos existentes al primer tenant
UPDATE metrics SET tenant_id = 'cliente1' WHERE tenant_id IS NULL;
UPDATE alerts SET tenant_id = 'cliente1' WHERE tenant_id IS NULL;
UPDATE stores SET tenant_id = 'cliente1' WHERE tenant_id IS NULL;

-- Habilitar constraints
ALTER TABLE metrics ALTER COLUMN tenant_id SET NOT NULL;
ALTER TABLE alerts ALTER COLUMN tenant_id SET NOT NULL;
```

## 🧪 Testing Multi-Tenancy

### Unit Tests
```python
def test_tenant_isolation():
    # Create data for tenant1
    create_metrics(tenant_id="tenant1", count=100)
    
    # Set context to tenant2
    set_tenant_context("tenant2")
    
    # Should return 0 metrics
    metrics = get_metrics()
    assert len(metrics) == 0

def test_api_key_validation():
    key = "store_tenant1_T01_abc123"
    tenant_id, store_id = extract_tenant_from_key(key)
    
    assert tenant_id == "tenant1"
    assert store_id == "T01"
```

### Integration Tests
- **Cross-tenant queries**: Verificar isolación
- **API key rotation**: No debe afectar otros tenants
- **Dashboard access**: Solo datos del tenant correcto
- **Cost calculation**: Por tenant individual

## 📋 Operations Runbook

### Adding New Tenant
1. Run onboarding script
2. Verify database entries
3. Test API key authentication
4. Validate RLS isolation
5. Deploy gateway configs
6. Monitor first 24h of data

### Tenant Deactivation
1. Set `is_active = FALSE` in tenants table
2. Revoke all API keys
3. Disable dashboard users
4. Archive tenant data (optional)
5. Remove deployment configs

### Troubleshooting
- **Data leakage**: Check RLS policies
- **Auth failures**: Verify API key format
- **Performance**: Add tenant_id to slow queries
- **Cost overruns**: Check usage patterns

## 🚀 Future Enhancements

### Phase 2
- **Tenant-specific features**: Feature flags por tenant
- **Custom domains**: cliente1.storepulse.io
- **Advanced billing**: Usage-based pricing
- **Multi-region**: Tenant data locality

### Phase 3  
- **Tenant databases**: Separate DB per large tenant
- **Kubernetes multi-tenancy**: Namespace isolation
- **Advanced analytics**: Cross-tenant insights
- **Self-service onboarding**: Automated tenant creation

---

Esta implementación multi-tenant permite escalar de 1 a 100+ clientes sin cambios arquitecturales mayores, manteniendo costos bajos y operaciones simples.