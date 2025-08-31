# StorePulse - Plan de Desarrollo y Roadmap

## 1. Resumen Ejecutivo del Plan

### Timeline General
- **Duración Total:** 12 semanas
- **Equipo:** 3-4 desarrolladores
- **Metodología:** Agile/Scrum con sprints de 2 semanas
- **Primera Release:** Semana 8 (MVP)
- **Release Completa:** Semana 12

### Fases Principales
1. **Fase 1 (Semanas 1-4):** Infraestructura Core y Agentes
2. **Fase 2 (Semanas 5-8):** Cloud Platform y Dashboards
3. **Fase 3 (Semanas 9-12):** Alertas, Optimización y Rollout

## 2. Equipo y Roles

### Estructura del Equipo
```yaml
Tech Lead:
  Responsabilidades:
    - Arquitectura y decisiones técnicas
    - Code reviews
    - Mentoring
    - Integración con stakeholders
  Allocation: 100%

Backend Developer:
  Responsabilidades:
    - Gateway local development
    - Cloud API development
    - Database design
    - Integrations (WhatsApp, sensors)
  Allocation: 100%

Frontend Developer:
  Responsabilidades:
    - Customer dashboard
    - Admin dashboard
    - UI/UX implementation
    - Mobile responsiveness
  Allocation: 100%

DevOps Engineer:
  Responsabilidades:
    - Infrastructure setup
    - CI/CD pipelines
    - Monitoring setup
    - Security implementation
  Allocation: 50%

QA Engineer:
  Responsabilidades:
    - Test planning
    - Automated testing
    - Performance testing
    - User acceptance testing
  Allocation: 50% (from week 5)
```

## 3. Sprint Planning Detallado

### Sprint 0: Preparación (Semana 0)
**Objetivo:** Setup inicial y preparación del ambiente

**Tareas:**
```markdown
- [ ] Setup repositorios Git
- [ ] Configurar proyecto en GCP
- [ ] Crear documentación inicial
- [ ] Setup herramientas de desarrollo
- [ ] Definir estándares de código
- [ ] Crear templates de proyecto
```

**Entregables:**
- Repositorios creados
- Ambientes de desarrollo listos
- Guía de contribución

---

### Sprint 1: Agente POS y Gateway Base (Semanas 1-2)
**Objetivo:** Desarrollar el agente de monitoreo POS y gateway básico

**User Stories:**
```markdown
STOR-001: Como administrador, quiero que el agente detecte el estado del POS
  - Desarrollar health checks
  - Verificar conectividad
  - Detectar estado de impresora
  - Implementar heartbeat
  Puntos: 8

STOR-002: Como sistema, necesito un gateway local que reciba métricas
  - Setup FastAPI
  - Endpoint de ingesta
  - Almacenamiento en SQLite
  - Health endpoint
  Puntos: 5

STOR-003: Como desarrollador, necesito tests unitarios para el agente
  - Tests de health checks
  - Tests de conectividad
  - Mock de servicios externos
  Puntos: 3
```

**Tareas Técnicas:**
```go
// agent/main.go
package main

import (
    "time"
    "github.com/storepulse/agent/monitor"
    "github.com/storepulse/agent/client"
)

func main() {
    config := LoadConfig()
    gateway := client.NewGatewayClient(config.GatewayURL)
    
    ticker := time.NewTicker(30 * time.Second)
    for range ticker.C {
        metrics := monitor.CollectMetrics()
        gateway.Send(metrics)
    }
}
```

**Definition of Done:**
- [ ] Agente compilado y funcionando en Windows
- [ ] Gateway recibiendo y almacenando métricas
- [ ] Tests con 80% cobertura
- [ ] Documentación de instalación

---

### Sprint 2: Sincronización y Buffer (Semanas 3-4)
**Objetivo:** Implementar sincronización cloud y manejo de offline

**User Stories:**
```markdown
STOR-004: Como gateway, debo sincronizar datos con la nube
  - Implementar sync service
  - Retry con backoff exponencial
  - Manejo de errores
  - Confirmación de recepción
  Puntos: 8

STOR-005: Como gateway, debo mantener datos si no hay internet
  - Buffer en SQLite
  - Limpieza de datos antiguos
  - Priorización de envío
  - Compresión de datos
  Puntos: 5

STOR-006: Como admin, quiero ver logs del gateway
  - Structured logging
  - Rotación de logs
  - Niveles de log configurables
  Puntos: 3
```

**Código de Referencia:**
```python
# gateway/sync_service.py
import asyncio
from typing import List
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

class SyncService:
    def __init__(self, cloud_api: str, api_key: str):
        self.cloud_api = cloud_api
        self.api_key = api_key
        self.client = httpx.AsyncClient()
    
    @retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=4, max=60)
    )
    async def sync_batch(self, metrics: List[dict]):
        response = await self.client.post(
            f"{self.cloud_api}/v1/metrics/batch",
            json={"metrics": metrics},
            headers={"X-API-Key": self.api_key}
        )
        response.raise_for_status()
        return response.json()
    
    async def run_sync_loop(self):
        while True:
            metrics = await self.get_pending_metrics()
            if metrics:
                try:
                    result = await self.sync_batch(metrics)
                    await self.mark_as_synced(result['processed_ids'])
                except Exception as e:
                    logger.error(f"Sync failed: {e}")
            await asyncio.sleep(30)
```

---

### Sprint 3: Infraestructura Cloud (Semanas 5-6)
**Objetivo:** Setup completo de infraestructura en GCP

**User Stories:**
```markdown
STOR-007: Como DevOps, necesito infraestructura cloud configurada
  - Setup Cloud Run
  - Configurar Cloud SQL
  - Setup Pub/Sub
  - Configurar Cloud Functions
  Puntos: 13

STOR-008: Como API, necesito endpoints de ingesta
  - Endpoint batch metrics
  - Validación de datos
  - Autenticación por API key
  - Rate limiting
  Puntos: 8

STOR-009: Como sistema, necesito procesar métricas asincrónicamente
  - Cloud Function processor
  - Guardar en PostgreSQL
  - Manejo de errores
  - Dead letter queue
  Puntos: 8
```

**Terraform Configuration:**
```hcl
# infrastructure/main.tf
module "api" {
  source = "./modules/cloudrun"
  
  service_name = "storepulse-api"
  image        = "gcr.io/storepulse/api:latest"
  region       = var.region
  
  environment_variables = {
    DATABASE_URL = module.database.connection_string
    PUBSUB_TOPIC = module.pubsub.topic_id
  }
}

module "database" {
  source = "./modules/cloudsql"
  
  instance_name = "storepulse-db"
  database_version = "POSTGRES_15"
  tier = "db-n1-standard-2"
  
  backup_configuration = {
    enabled = true
    start_time = "03:00"
  }
}

module "pubsub" {
  source = "./modules/pubsub"
  
  topic_name = "metrics-ingestion"
  
  subscriptions = [{
    name = "metrics-processor"
    ack_deadline = 60
  }]
}
```

---

### Sprint 4: Dashboard Cliente MVP (Semanas 7-8)
**Objetivo:** Dashboard funcional para clientes

**User Stories:**
```markdown
STOR-010: Como cliente, quiero ver el estado de mis tiendas
  - Vista general con cards
  - Indicadores de salud (verde/amarillo/rojo)
  - Filtros por tienda
  - Auto-refresh cada 30s
  Puntos: 8

STOR-011: Como cliente, quiero ver detalles de una tienda
  - Lista de POS con estado
  - Gráficos de temperatura
  - Historial últimas 24h
  - Alertas activas
  Puntos: 8

STOR-012: Como cliente, necesito autenticación segura
  - Login con email/password
  - JWT tokens
  - Refresh tokens
  - Logout
  Puntos: 5
```

**React Components:**
```jsx
// dashboard/src/components/StoreCard.jsx
import React from 'react';
import { Card, Badge } from '@/components/ui';
import { Thermometer, Monitor, AlertTriangle } from 'lucide-react';

const StoreCard = ({ store }) => {
  const getStatusColor = (status) => {
    switch(status) {
      case 'healthy': return 'bg-green-500';
      case 'warning': return 'bg-yellow-500';
      case 'critical': return 'bg-red-500';
      default: return 'bg-gray-500';
    }
  };

  return (
    <Card className="p-6 hover:shadow-lg transition-shadow">
      <div className="flex justify-between items-start mb-4">
        <h3 className="text-xl font-semibold">{store.name}</h3>
        <Badge className={getStatusColor(store.status)}>
          {store.status.toUpperCase()}
        </Badge>
      </div>
      
      <div className="grid grid-cols-3 gap-4">
        <div className="flex items-center">
          <Monitor className="w-5 h-5 mr-2 text-gray-600" />
          <div>
            <p className="text-sm text-gray-500">POS</p>
            <p className="font-semibold">{store.pos.active}/{store.pos.total}</p>
          </div>
        </div>
        
        <div className="flex items-center">
          <Thermometer className="w-5 h-5 mr-2 text-gray-600" />
          <div>
            <p className="text-sm text-gray-500">Temp</p>
            <p className="font-semibold">{store.avgTemp}°C</p>
          </div>
        </div>
        
        <div className="flex items-center">
          <AlertTriangle className="w-5 h-5 mr-2 text-gray-600" />
          <div>
            <p className="text-sm text-gray-500">Alertas</p>
            <p className="font-semibold">{store.activeAlerts}</p>
          </div>
        </div>
      </div>
    </Card>
  );
};
```

---

### Sprint 5: Sistema de Alertas (Semanas 9-10)
**Objetivo:** Implementar sistema completo de alertas

**User Stories:**
```markdown
STOR-013: Como sistema, debo generar alertas automáticamente
  - Motor de reglas
  - Evaluación de umbrales
  - Cooldown para evitar spam
  - Escalación automática
  Puntos: 13

STOR-014: Como cliente, quiero recibir alertas por WhatsApp
  - Integración WhatsApp Business API
  - Templates de mensajes
  - Confirmación de recepción
  - Gestión de contactos
  Puntos: 8

STOR-015: Como admin, quiero gestionar configuración de alertas
  - CRUD de reglas
  - Configuración por cliente
  - Test de alertas
  - Histórico de alertas
  Puntos: 8
```

**Alert Engine Implementation:**
```python
# alerts/engine.py
from datetime import datetime, timedelta
from typing import Dict, List
import asyncio

class AlertEngine:
    def __init__(self, db, whatsapp_client, opsgenie_client):
        self.db = db
        self.whatsapp = whatsapp_client
        self.opsgenie = opsgenie_client
        self.cooldown_cache = {}
    
    async def evaluate_metrics(self, metrics: List[Dict]):
        """Evalúa métricas contra reglas definidas"""
        rules = await self.db.get_active_rules()
        
        for metric in metrics:
            for rule in rules:
                if self.should_trigger(metric, rule):
                    await self.trigger_alert(metric, rule)
    
    def should_trigger(self, metric: Dict, rule: Dict) -> bool:
        """Verifica si se debe disparar la alerta"""
        # Check cooldown
        cache_key = f"{rule['id']}:{metric['device_id']}"
        if cache_key in self.cooldown_cache:
            last_alert = self.cooldown_cache[cache_key]
            if datetime.now() - last_alert < timedelta(minutes=rule['cooldown']):
                return False
        
        # Evaluate condition
        return self.evaluate_condition(metric, rule['condition'])
    
    async def trigger_alert(self, metric: Dict, rule: Dict):
        """Dispara la alerta por todos los canales configurados"""
        alert = {
            'id': generate_uuid(),
            'rule_id': rule['id'],
            'metric': metric,
            'severity': rule['severity'],
            'message': self.format_message(rule['template'], metric),
            'created_at': datetime.now()
        }
        
        # Save to database
        await self.db.save_alert(alert)
        
        # Send notifications
        tasks = []
        if 'whatsapp' in rule['channels']:
            tasks.append(self.send_whatsapp(alert, rule['contacts']))
        if 'opsgenie' in rule['channels']:
            tasks.append(self.send_opsgenie(alert))
        
        await asyncio.gather(*tasks)
        
        # Update cooldown
        cache