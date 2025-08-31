# Documento de Definición de MVP: StorePulse v2.0

## 1. Resumen Ejecutivo

**StorePulse** es una plataforma de monitoreo en tiempo real diseñada para supervisar la salud operativa de puntos de venta (POS) y condiciones ambientales en cadenas de supermercados. La solución proporciona visibilidad centralizada del estado de infraestructura crítica, permitiendo respuesta proactiva ante incidentes y minimizando pérdidas operativas.

### Datos Clave
- **Escala inicial:** 16 tiendas (expandiendo a 30 en 3 meses)
- **Dispositivos monitoreados:** ~150 POS y ~240 sensores ambientales
- **Arquitectura:** Edge computing con sincronización cloud
- **Stack tecnológico:** Go, Python, JavaScript, Google Cloud Platform
- **Presupuesto cloud:** $300/mes por cliente

## 2. Objetivos del MVP

### Objetivos Principales
1. **Minimizar pérdidas por caídas de POS** - Detección y notificación en menos de 1 minuto
2. **Prevenir pérdidas de productos refrigerados** - Monitoreo continuo de temperatura
3. **Centralizar la gestión operativa** - Dashboard unificado para todas las tiendas
4. **Automatizar la respuesta a incidentes** - Sistema de alertas con escalación automática

### Métricas de Éxito
- Reducción del 70% en tiempo de detección de fallas
- Reducción del 50% en pérdidas por productos refrigerados
- 99.9% de uptime del sistema de monitoreo
- Tiempo de respuesta a incidentes < 5 minutos

## 3. Alcance Funcional del MVP

### Módulo 1: Monitoreo de Puntos de Venta (POS)
**Frecuencia de monitoreo:** Cada 30 segundos (heartbeat cada 90s)

#### Métricas Recolectadas:
```json
{
  "device_type": "pos",
  "pos_id": "POS01",
  "store_id": "T01",
  "status": "online|offline",
  "ip_address": "192.168.1.50",
  "internet_status": "connected|disconnected",
  "printer_status": "connected|disconnected",
  "pos_software_status": "active|inactive",
  "timestamp": "2025-01-15T10:30:00Z"
}
```

#### Alertas Configuradas:
- **CRÍTICA:** POS offline (notificación inmediata)
- **ALTA:** Impresora desconectada (notificación en 5 min)
- **MEDIA:** Sin internet (notificación en 10 min)

### Módulo 2: Monitoreo Ambiental
**Frecuencia de monitoreo:** Cada 5 minutos

#### Métricas Recolectadas:
```json
{
  "device_type": "sensor",
  "sensor_id": "SENS_FRIDGE_01",
  "store_id": "T01",
  "location": "refrigerador_lacteos",
  "temperature_celsius": 4.5,
  "humidity_percentage": 65,
  "battery_level": 85,
  "timestamp": "2025-01-15T10:30:00Z"
}
```

#### Umbrales de Alerta:
- **Refrigeradores:** > 8°C por más de 5 minutos
- **Congeladores:** > -15°C por más de 5 minutos
- **Ambiente tienda:** > 26°C o < 18°C
- **Humedad:** > 70% o < 30%

### Módulo 3: Sistema de Alertas Inteligente

#### Canales de Notificación:
1. **WhatsApp Business API** - Canal principal (costo: $0.005/mensaje)
2. **Dashboard en tiempo real** - Actualización cada 30 segundos
3. **Sistema de incidentes** - Gestión y seguimiento interno

#### Matriz de Escalación:

| Evento | Severidad | T+0 min | T+5 min | T+15 min |
|--------|-----------|---------|---------|----------|
| POS Caído | CRÍTICA | Gerente Tienda | Superintendente + IT | Llamada automática |
| Temp. Alta Refrigerador | ALTA | Gerente Tienda | Servicios Generales | Superintendente |
| Impresora Offline | MEDIA | Gerente Tienda | IT Support | - |
| Sensor Sin Señal | BAJA | - | Admin Sistema | - |

### Módulo 4: Dashboards

#### Dashboard Cliente (Operacional)
- Vista general de todas las tiendas (mapa de calor)
- Estado detallado por tienda
- Histórico de incidentes últimas 24h
- Métricas de temperatura en tiempo real
- Panel de alertas activas

#### Dashboard Administrador (Técnico)
- Estado de infraestructura (gateways, agentes, sensores)
- Logs de sincronización
- Gestión de configuraciones
- Comandos remotos (reinicio de sensores)
- Métricas de performance del sistema

## 4. Arquitectura Técnica (Resumen)

### Componentes Edge (Tienda)
- **Agente POS:** Ejecutable Go (.exe) en cada terminal
- **Gateway Local:** Python/FastAPI en servidor existente
- **Buffer Local:** SQLite (4+ horas de retención)
- **Sensores WiFi:** Dispositivos con batería (1-2 años)

### Componentes Cloud (GCP)
- **Ingesta:** Cloud Run + Pub/Sub
- **Procesamiento:** Cloud Functions
- **Almacenamiento:** Cloud SQL PostgreSQL
- **API:** Cloud Run (FastAPI)
- **Dashboards:** React (Vercel CDN)

### Seguridad
- Autenticación por API Keys únicas por tienda
- Encriptación TLS 1.3 en tránsito
- Row Level Security en base de datos
- Backup automático diario

## 5. Fases de Implementación

### Fase 1: MVP Core (4 semanas)
- ✅ Monitoreo básico de POS
- ✅ Gateway local con buffer
- ✅ Sincronización cloud
- ✅ Dashboard básico
- ✅ Alertas WhatsApp

### Fase 2: Expansión (4 semanas)
- ⏳ Integración sensores ambientales
- ⏳ Dashboard mejorado
- ⏳ Sistema de incidentes
- ⏳ Reportes automáticos

### Fase 3: Optimización (4 semanas)
- ⏳ Comandos remotos
- ⏳ Analytics predictivo
- ⏳ App móvil (opcional)
- ⏳ Integración ERP

## 6. Riesgos y Mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigación |
|--------|--------------|---------|------------|
| Pérdida de conectividad | Alta | Medio | Buffer local 4+ horas |
| Falla de sensores | Media | Bajo | Monitoreo de heartbeat |
| Sobrecarga de alertas | Media | Medio | Sistema de cooldown y agrupación |
| Escalabilidad | Baja | Alto | Arquitectura serverless |

## 7. Presupuesto Estimado

### Costos de Desarrollo (One-time)
- Desarrollo: 3 desarrolladores x 3 meses
- Sensores: $50 x 240 unidades = $12,000
- Licencias y setup: $2,000

### Costos Operativos (Mensual)
- Infraestructura GCP: $275/mes
- WhatsApp Business: $25/mes (5,000 mensajes)
- Total: **$300/mes por cliente**

### ROI Esperado
- Reducción pérdidas por POS caído: $2,000/mes
- Reducción pérdidas productos refrigerados: $1,500/mes
- **Retorno de inversión: 3-4 meses**

## 8. Criterios de Aceptación

### Funcionales
- [ ] Detección de falla POS en < 1 minuto
- [ ] Alertas WhatsApp funcionando 24/7
- [ ] Dashboard actualizado cada 30 segundos
- [ ] Buffer local resistente a cortes de 4 horas
- [ ] Histórico de datos de 1 año

### No Funcionales
- [ ] Disponibilidad del sistema > 99.9%
- [ ] Latencia de API < 200ms
- [ ] Tiempo de carga dashboard < 2 segundos
- [ ] Soporte para 100 tiendas sin degradación

## 9. Próximos Pasos

1. **Semana 1-2:** Desarrollo y testing del agente POS
2. **Semana 2-3:** Implementación gateway local
3. **Semana 3-4:** Setup infraestructura cloud
4. **Semana 4-5:** Desarrollo dashboards
5. **Semana 5-6:** Integración sistema de alertas
6. **Semana 6-8:** Testing end-to-end y piloto
7. **Semana 8-12:** Rollout gradual y optimizaciones

## 10. Equipo y Responsabilidades

- **Product Owner:** Define requerimientos y prioridades
- **Tech Lead:** Arquitectura y decisiones técnicas
- **Backend Dev:** Gateway, API, procesamiento
- **Frontend Dev:** Dashboards y UX
- **DevOps:** Infraestructura y monitoreo
- **QA:** Testing y validación

---
*Documento actualizado: Enero 2025*
*Versión: 2.0*
*Estado: Aprobado para desarrollo*