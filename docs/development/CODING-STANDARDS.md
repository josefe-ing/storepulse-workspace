# STOREPULSE - ESTÁNDARES DE CÓDIGO

## FILOSOFÍA DE DESARROLLO

### Principios Fundamentales
1. **Defensive Programming**: Código robusto que maneja todos los casos edge
2. **Fail Fast**: Detectar errores lo más temprano posible
3. **Explicit over Implicit**: Código autodocumentado y claro
4. **DRY (Don't Repeat Yourself)**: Evitar duplicación de lógica
5. **SOLID Principles**: Diseño orientado a objetos sólido
6. **Test-Driven Development**: Tests antes que código

### Edge-Computing Architecture
- Todos los agentes locales deben operar offline
- Datos buffeados en SQLite con WAL mode
- Sincronización resiliente con retry exponencial
- Heartbeat monitoring para detección de sensores silenciosos

## PYTHON/FASTAPI STANDARDS

### Configuración Python (`pyproject.toml`)
```toml
[tool.poetry]
name = "storepulse-backend"
version = "1.0.0"
description = "Multi-Client Retail Monitoring System"
authors = ["StorePulse Team <dev@storepulse.com>"]

[tool.poetry.dependencies]
python = "^3.11"
fastapi = "^0.104.0"
uvicorn = "^0.24.0"
pydantic = "^2.4.0"
sqlalchemy = "^2.0.0"
alembic = "^1.12.0"
asyncpg = "^0.29.0"
redis = "^5.0.0"
google-cloud-pubsub = "^2.18.0"
google-cloud-sql = "^3.4.0"
psutil = "^5.9.0"
aiohttp = "^3.9.0"
pytest = "^7.4.0"

[tool.poetry.group.dev.dependencies]
pytest-cov = "^4.1.0"
black = "^23.9.0"
mypy = "^1.6.0"
ruff = "^0.1.0"
pre-commit = "^3.5.0"

[tool.black]
line-length = 88
target-version = ['py311']

[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
disallow_incomplete_defs = true
check_untyped_defs = true
disallow_untyped_decorators = true
no_implicit_optional = true
warn_redundant_casts = true
warn_unused_ignores = true
warn_no_return = true
warn_unreachable = true
strict_equality = true

[tool.ruff]
line-length = 88
select = ["E", "W", "F", "I", "N", "UP", "B", "A", "C4", "T20"]
ignore = ["E203", "W503"]
```

### Estructura Python (Agentes Edge)
```
agents/
   __init__.py
   base_agent.py           # BaseAgent class
   pos_collector.py        # POS data collector
   sensor_collector.py     # IoT sensor collector  
   sync_manager.py         # Offline sync handler
   buffer/
      __init__.py
      sqlite_buffer.py     # SQLite buffering
      compression.py       # Data compression
   config/
      __init__.py
      agent_config.py      # Configuration management
   utils/
      __init__.py
      heartbeat.py         # Health monitoring
      retry.py             # Exponential backoff
   main.py                 # Agent entry point
```

### Estructura Python (Backend API)
```
src/
   api/                    # FastAPI routes
      __init__.py
      routers/
         __init__.py
         health.py         # Health checks
         ingest.py         # Data ingestion
         agents.py         # Agent management
         sensors.py        # Sensor control
         alerts.py         # Alert management
      schemas/
         __init__.py
         agent.py          # Agent schemas
         sensor.py         # Sensor schemas
         alert.py          # Alert schemas
   core/                   # Core utilities
      __init__.py
      config.py            # Configuration
      dependencies.py      # FastAPI dependencies
      logging.py           # Structured logging
      multi_tenant.py      # Tenant isolation
   services/               # Business logic
      __init__.py
      agent_service.py     # Agent operations
      sensor_service.py    # Sensor operations
      alert_service.py     # Alert detection
   db/                     # Database layer
      __init__.py
      models.py            # SQLAlchemy models
      repository.py        # Data access layer
      migrations/          # Alembic migrations
   main.py                 # FastAPI application
```

### Type Hints Obligatorios
```python
from typing import Dict, List, Optional, Union, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

class AgentHeartbeat(BaseModel):
    agent_id: str = Field(..., description="Unique agent identifier")
    tenant_id: str = Field(..., description="Tenant identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    status: Literal["online", "offline", "syncing"] = Field(..., description="Agent status")
    system_metrics: Dict[str, float] = Field(default_factory=dict)
    buffer_size: int = Field(ge=0, description="Number of buffered events")

async def process_heartbeat(
    heartbeat: AgentHeartbeat,
    db_session: AsyncSession,
    redis_client: Redis,
) -> Dict[str, Any]:
    """Procesa heartbeat de agent y actualiza estado."""
    # Implementation with proper error handling
    pass
```

### Error Handling Python
```python
from enum import Enum
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any

class StorePulseErrorCode(str, Enum):
    AGENT_OFFLINE = "agent_offline"
    SENSOR_SILENT = "sensor_silent" 
    SYNC_FAILED = "sync_failed"
    VALIDATION_ERROR = "validation_error"
    NOT_FOUND = "not_found"
    TENANT_ISOLATION_ERROR = "tenant_isolation_error"

class StorePulseError(Exception):
    def __init__(
        self, 
        message: str, 
        code: StorePulseErrorCode, 
        status_code: int = 500,
        context: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.status_code = status_code
        self.context = context or {}
        super().__init__(message)

# Uso específico para sensores silenciosos
class SensorSilentError(StorePulseError):
    def __init__(self, sensor_id: str, last_seen: datetime):
        super().__init__(
            message=f"Sensor {sensor_id} has been silent for too long",
            code=StorePulseErrorCode.SENSOR_SILENT,
            status_code=503,
            context={
                "sensor_id": sensor_id, 
                "last_seen": last_seen.isoformat(),
                "silence_duration_minutes": (datetime.utcnow() - last_seen).total_seconds() / 60
            }
        )

# Error handler middleware
async def storepulse_error_handler(request, exc: StorePulseError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "context": exc.context,
                "timestamp": datetime.utcnow().isoformat()
            }
        }
    )
```

## REACT/FRONTEND STANDARDS

### Estructura de Componentes
```
src/
   components/                 # Componentes reutilizables
      common/
         Button/
            Button.tsx
            Button.test.tsx
            index.ts
         StatusIndicator/       # Indicadores de estado de sensores
         AlertCard/            # Cards de alertas
      dashboard/
         AgentGrid/            # Grid de agents
         SensorNetwork/        # Network de sensores
         AlertCenter/          # Centro de alertas
   pages/                      # Páginas principales
      Dashboard/
      Agents/
      Sensors/
      Alerts/
      Sync/
   services/                   # API calls
      api.ts
      agent.service.ts
      sensor.service.ts
      alert.service.ts
   hooks/                      # Custom hooks
      useAgent.ts
      useSensor.ts
      useRealTimeAlerts.ts
      useWebSocket.ts
   contexts/                   # React contexts
      TenantContext.tsx
      AlertContext.tsx
      WebSocketContext.tsx
   types/
       api.types.ts
       agent.types.ts
       sensor.types.ts
       alert.types.ts
       index.ts
```

### Component Standards para StorePulse
```typescript
import React, { useState, useCallback, useMemo } from 'react';

interface SensorStatusProps {
  sensor_id: string;
  sensor_type: 'temperature' | 'door' | 'motion' | 'power' | 'pos';
  status: 'active' | 'inactive' | 'error' | 'silent';
  last_reading?: Date;
  signal_strength: number;
  battery_level?: number;
  onRestart?: (sensor_id: string) => void;
  onTest?: (sensor_id: string) => void;
}

export const SensorStatus: React.FC<SensorStatusProps> = ({
  sensor_id,
  sensor_type,
  status,
  last_reading,
  signal_strength,
  battery_level,
  onRestart,
  onTest,
}) => {
  const statusColor = useMemo(() => {
    const colors = {
      active: 'bg-green-500',
      inactive: 'bg-yellow-500', 
      error: 'bg-red-500',
      silent: 'bg-red-600 animate-pulse'
    };
    return colors[status] || 'bg-gray-500';
  }, [status]);

  const handleRestart = useCallback(() => {
    if (onRestart && (status === 'error' || status === 'silent')) {
      onRestart(sensor_id);
    }
  }, [sensor_id, status, onRestart]);

  const silenceDuration = useMemo(() => {
    if (status === 'silent' && last_reading) {
      const minutes = Math.floor((Date.now() - last_reading.getTime()) / (1000 * 60));
      return `${minutes}m ago`;
    }
    return null;
  }, [status, last_reading]);

  return (
    <div className="bg-white rounded-lg shadow-md p-4 border-l-4" 
         style={{ borderLeftColor: statusColor.replace('bg-', '') }}>
      <div className="flex justify-between items-start mb-3">
        <div>
          <h3 className="font-semibold text-gray-900">{sensor_id}</h3>
          <p className="text-sm text-gray-600 capitalize">{sensor_type}</p>
        </div>
        <div className={`w-3 h-3 rounded-full ${statusColor}`} />
      </div>

      <div className="space-y-2 text-sm">
        <div className="flex justify-between">
          <span className="text-gray-600">Status:</span>
          <span className={status === 'silent' ? 'text-red-600 font-medium' : ''}>
            {status.toUpperCase()}
            {silenceDuration && ` (${silenceDuration})`}
          </span>
        </div>
        
        <div className="flex justify-between">
          <span className="text-gray-600">Signal:</span>
          <span>{signal_strength}%</span>
        </div>

        {battery_level !== undefined && (
          <div className="flex justify-between">
            <span className="text-gray-600">Battery:</span>
            <span className={battery_level < 20 ? 'text-red-600' : ''}>
              {battery_level}%
            </span>
          </div>
        )}
      </div>

      {(status === 'error' || status === 'silent') && (
        <div className="mt-4 flex gap-2">
          <button
            onClick={handleRestart}
            className="flex-1 bg-red-600 text-white px-3 py-2 rounded-md text-sm hover:bg-red-700 transition-colors"
          >
            Restart Sensor
          </button>
          {onTest && (
            <button
              onClick={() => onTest(sensor_id)}
              className="px-3 py-2 border border-gray-300 rounded-md text-sm hover:bg-gray-50 transition-colors"
            >
              Test
            </button>
          )}
        </div>
      )}
    </div>
  );
};
```

### Custom Hooks para StorePulse
```typescript
import { useState, useEffect, useCallback } from 'react';
import { sensorService } from '../services/sensor.service';
import { useWebSocket } from './useWebSocket';

export const useSensorMonitoring = (tenantId: string) => {
  const [sensors, setSensors] = useState<SensorStatus[]>([]);
  const [silentAlerts, setSilentAlerts] = useState<SilentSensorAlert[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { socket } = useWebSocket(`/sensors/${tenantId}`);

  const fetchSensors = useCallback(async () => {
    setLoading(true);
    setError(null);
    
    try {
      const data = await sensorService.getAllSensors(tenantId);
      setSensors(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  }, [tenantId]);

  // Listen for real-time sensor updates
  useEffect(() => {
    if (socket) {
      socket.on('sensor_status_update', (update: SensorStatusUpdate) => {
        setSensors(prev => 
          prev.map(sensor => 
            sensor.sensor_id === update.sensor_id 
              ? { ...sensor, ...update } 
              : sensor
          )
        );
      });

      socket.on('silent_sensor_alert', (alert: SilentSensorAlert) => {
        setSilentAlerts(prev => [alert, ...prev]);
      });

      socket.on('sensor_recovered', (sensor_id: string) => {
        setSilentAlerts(prev => 
          prev.filter(alert => alert.sensor_id !== sensor_id)
        );
      });

      return () => {
        socket.off('sensor_status_update');
        socket.off('silent_sensor_alert');
        socket.off('sensor_recovered');
      };
    }
  }, [socket]);

  useEffect(() => {
    void fetchSensors();
  }, [fetchSensors]);

  const restartSensor = useCallback(async (sensorId: string) => {
    try {
      await sensorService.restartSensor(tenantId, sensorId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Restart failed');
    }
  }, [tenantId]);

  const testSensor = useCallback(async (sensorId: string) => {
    try {
      await sensorService.testSensorConnection(tenantId, sensorId);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Test failed');
    }
  }, [tenantId]);

  return {
    sensors,
    silentAlerts,
    loading,
    error,
    refetch: fetchSensors,
    restartSensor,
    testSensor,
  };
};
```

## DATABASE STANDARDS

### Migraciones con Alembic (PostgreSQL + TimescaleDB)
```python
"""Create multi-tenant sensor monitoring tables

Revision ID: 001
Revises: 
Create Date: 2024-01-15 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision = '001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create TimescaleDB extension if not exists
    op.execute('CREATE EXTENSION IF NOT EXISTS timescaledb CASCADE')
    
    # Tenants table
    op.create_table('tenants',
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('is_active', sa.Boolean(), default=True),
    )

    # Agents table (multi-tenant)
    op.create_table('agents',
        sa.Column('agent_id', sa.String(100), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('store_location', sa.String(255), nullable=False),
        sa.Column('status', sa.Enum('online', 'offline', 'error', 'syncing', name='agent_status'), nullable=False),
        sa.Column('last_heartbeat', sa.TIMESTAMP(timezone=True)),
        sa.Column('version', sa.String(50)),
        sa.Column('system_metrics', sa.JSON()),
        sa.Column('buffer_size', sa.Integer(), default=0),
        sa.Column('pending_syncs', sa.Integer(), default=0),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id']),
        sa.Index('idx_agents_tenant_status', 'tenant_id', 'status'),
    )

    # Sensors table (multi-tenant)
    op.create_table('sensors',
        sa.Column('sensor_id', sa.String(100), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('agent_id', sa.String(100), nullable=False),
        sa.Column('sensor_type', sa.Enum('temperature', 'door', 'motion', 'power', 'pos', name='sensor_type'), nullable=False),
        sa.Column('location', sa.String(255), nullable=False),
        sa.Column('status', sa.Enum('active', 'inactive', 'error', 'silent', name='sensor_status'), nullable=False),
        sa.Column('last_reading', sa.TIMESTAMP(timezone=True)),
        sa.Column('battery_level', sa.Integer(), sa.CheckConstraint('battery_level >= 0 AND battery_level <= 100')),
        sa.Column('signal_strength', sa.Integer(), nullable=False),
        sa.Column('error_count', sa.Integer(), default=0),
        sa.Column('readings_today', sa.Integer(), default=0),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id']),
        sa.ForeignKeyConstraint(['agent_id'], ['agents.agent_id']),
        sa.Index('idx_sensors_tenant_agent', 'tenant_id', 'agent_id'),
        sa.Index('idx_sensors_type_status', 'sensor_type', 'status'),
    )

    # Sensor readings time-series table
    op.create_table('sensor_readings',
        sa.Column('reading_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('sensor_id', sa.String(100), nullable=False),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('timestamp', sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.Column('unit', sa.String(20)),
        sa.Column('metadata', sa.JSON()),
        
        sa.ForeignKeyConstraint(['sensor_id'], ['sensors.sensor_id']),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id']),
        sa.Index('idx_sensor_readings_tenant_time', 'tenant_id', 'timestamp'),
        sa.Index('idx_sensor_readings_sensor_time', 'sensor_id', 'timestamp'),
    )

    # Convert to TimescaleDB hypertable
    op.execute("""
        SELECT create_hypertable('sensor_readings', 'timestamp', 
            partitioning_column => 'tenant_id', 
            number_partitions => 4
        );
    """)

    # Alerts table
    op.create_table('alerts',
        sa.Column('alert_id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('alert_type', sa.Enum('sensor_silent', 'agent_down', 'sync_failed', 'threshold_exceeded', name='alert_type'), nullable=False),
        sa.Column('severity', sa.Enum('warning', 'critical', 'emergency', name='alert_severity'), nullable=False),
        sa.Column('entity_id', sa.String(100), nullable=False),  # sensor_id or agent_id
        sa.Column('entity_type', sa.Enum('sensor', 'agent', name='entity_type'), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('context', sa.JSON()),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now()),
        sa.Column('acknowledged_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('resolved_at', sa.TIMESTAMP(timezone=True)),
        sa.Column('acknowledged_by', sa.String(255)),
        
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.tenant_id']),
        sa.Index('idx_alerts_tenant_type', 'tenant_id', 'alert_type'),
        sa.Index('idx_alerts_severity_created', 'severity', 'created_at'),
    )

def downgrade():
    op.drop_table('alerts')
    op.drop_table('sensor_readings')
    op.drop_table('sensors')
    op.drop_table('agents')
    op.drop_table('tenants')
    
    op.execute('DROP TYPE IF EXISTS alert_severity')
    op.execute('DROP TYPE IF EXISTS alert_type')
    op.execute('DROP TYPE IF EXISTS entity_type')
    op.execute('DROP TYPE IF EXISTS sensor_status')
    op.execute('DROP TYPE IF EXISTS sensor_type')
    op.execute('DROP TYPE IF EXISTS agent_status')
```

### Query Patterns Multi-Tenant
```python
# Siempre incluir tenant_id en queries para aislamiento
class SensorRepository:
    async def find_sensors_by_tenant(self, tenant_id: str, status: Optional[str] = None) -> List[Sensor]:
        query = select(Sensor).where(
            Sensor.tenant_id == tenant_id,
            Sensor.deleted_at.is_(None)
        )
        
        if status:
            query = query.where(Sensor.status == status)
            
        return await self.db.execute(query).scalars().all()

    async def find_silent_sensors(self, tenant_id: str, silence_threshold: int = 300) -> List[Sensor]:
        """Find sensors that haven't reported in X seconds."""
        cutoff_time = datetime.utcnow() - timedelta(seconds=silence_threshold)
        
        return await self.db.execute(
            select(Sensor)
            .where(
                Sensor.tenant_id == tenant_id,
                Sensor.status.in_(['active', 'inactive']),  # Not already marked as silent
                or_(
                    Sensor.last_reading.is_(None),
                    Sensor.last_reading < cutoff_time
                )
            )
        ).scalars().all()

    async def update_sensor_status_with_audit(
        self,
        tenant_id: str,
        sensor_id: str,
        new_status: str,
        reason: str,
        updated_by: str
    ) -> None:
        """Update sensor status with full audit trail."""
        async with self.db.begin():
            # Update sensor
            await self.db.execute(
                update(Sensor)
                .where(
                    Sensor.sensor_id == sensor_id,
                    Sensor.tenant_id == tenant_id
                )
                .values(
                    status=new_status,
                    updated_at=datetime.utcnow()
                )
            )
            
            # Create audit record
            await self.db.execute(
                insert(SensorAuditLog).values(
                    sensor_id=sensor_id,
                    tenant_id=tenant_id,
                    action='status_change',
                    old_value=None,  # Could fetch from previous state
                    new_value=new_status,
                    reason=reason,
                    changed_by=updated_by,
                    timestamp=datetime.utcnow()
                )
            )
```

## TESTING STANDARDS

### Backend Testing (Pytest)
```python
import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime, timedelta
from src.services.alert_service import AlertService, SilentSensorDetector

@pytest.fixture
async def alert_service():
    mock_db = AsyncMock()
    mock_redis = AsyncMock()
    return AlertService(db=mock_db, redis=mock_redis)

@pytest.fixture
def sample_sensors():
    return [
        {
            "sensor_id": "TEMP-A1-01",
            "tenant_id": "client-a",
            "sensor_type": "temperature",
            "last_reading": datetime.utcnow() - timedelta(minutes=20),
            "status": "active"
        },
        {
            "sensor_id": "DOOR-A1-01", 
            "tenant_id": "client-a",
            "sensor_type": "door",
            "last_reading": datetime.utcnow() - timedelta(minutes=2),
            "status": "active"
        }
    ]

@pytest.mark.asyncio
async def test_detect_silent_sensors_identifies_temperature_sensor(
    alert_service, sample_sensors
):
    """Test that temperature sensor silent for 20min is detected."""
    # Arrange
    alert_service.sensor_repo.find_all_active.return_value = sample_sensors
    
    # Act
    silent_sensors = await alert_service.detect_silent_sensors("client-a")
    
    # Assert
    assert len(silent_sensors) == 1
    assert silent_sensors[0]["sensor_id"] == "TEMP-A1-01"
    assert silent_sensors[0]["silence_duration_minutes"] == 20

@pytest.mark.asyncio
async def test_silent_sensor_alert_creation_and_dispatch(alert_service):
    """Test alert creation and multi-channel dispatch."""
    # Arrange
    sensor_data = {
        "sensor_id": "TEMP-A1-01",
        "tenant_id": "client-a", 
        "sensor_type": "temperature",
        "silence_duration_minutes": 25
    }
    
    # Act
    with patch.object(alert_service, 'dispatch_alert_notifications') as mock_dispatch:
        await alert_service.create_silent_sensor_alert(sensor_data)
    
    # Assert
    mock_dispatch.assert_called_once()
    alert_arg = mock_dispatch.call_args[0][0]
    assert alert_arg.sensor_id == "TEMP-A1-01"
    assert alert_arg.severity == "critical"  # Based on 25min silence

@pytest.mark.asyncio
async def test_sensor_recovery_removes_from_alerts(alert_service):
    """Test that sensor recovery removes active alerts."""
    # Arrange
    active_alert = {
        "alert_id": "alert-123",
        "sensor_id": "TEMP-A1-01",
        "tenant_id": "client-a",
        "status": "active"
    }
    alert_service.alert_repo.find_active_alerts.return_value = [active_alert]
    
    # Act
    await alert_service.handle_sensor_recovery("client-a", "TEMP-A1-01")
    
    # Assert
    alert_service.alert_repo.resolve_alert.assert_called_once_with("alert-123")

class TestSensorThresholds:
    """Test sensor-specific silence thresholds."""
    
    @pytest.mark.parametrize("sensor_type,silence_minutes,expected_severity", [
        ("temperature", 5, "warning"),
        ("temperature", 15, "critical"), 
        ("pos", 2, "critical"),
        ("pos", 30, "emergency"),
        ("door", 3, "warning"),
        ("motion", 10, "warning"),
    ])
    def test_sensor_type_specific_alert_levels(
        self, sensor_type, silence_minutes, expected_severity
    ):
        """Test that different sensor types have appropriate alert levels."""
        detector = SilentSensorDetector()
        severity = detector.calculate_alert_level(
            silence_duration_minutes=silence_minutes,
            sensor_type=sensor_type
        )
        assert severity == expected_severity
```

### Frontend Testing (React + Vitest)
```typescript
// SensorStatus.test.tsx
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi } from 'vitest';
import { SensorStatus } from './SensorStatus';

describe('SensorStatus Component', () => {
  const defaultProps = {
    sensor_id: 'TEMP-A1-01',
    sensor_type: 'temperature' as const,
    status: 'active' as const,
    signal_strength: 85,
  };

  it('renders sensor information correctly', () => {
    render(<SensorStatus {...defaultProps} />);
    
    expect(screen.getByText('TEMP-A1-01')).toBeInTheDocument();
    expect(screen.getByText('temperature')).toBeInTheDocument();
    expect(screen.getByText('ACTIVE')).toBeInTheDocument();
    expect(screen.getByText('85%')).toBeInTheDocument();
  });

  it('shows critical silent sensor state with animation', () => {
    const silentProps = {
      ...defaultProps,
      status: 'silent' as const,
      last_reading: new Date(Date.now() - 15 * 60 * 1000), // 15 minutes ago
    };

    render(<SensorStatus {...silentProps} />);
    
    expect(screen.getByText('SILENT (15m ago)')).toBeInTheDocument();
    expect(screen.getByText('Restart Sensor')).toBeInTheDocument();
    
    // Check for animation class
    const statusDot = screen.getByRole('status');
    expect(statusDot).toHaveClass('animate-pulse');
  });

  it('calls onRestart when restart button is clicked for silent sensor', async () => {
    const mockRestart = vi.fn();
    const silentProps = {
      ...defaultProps,
      status: 'silent' as const,
      onRestart: mockRestart,
    };

    render(<SensorStatus {...silentProps} />);
    
    const restartButton = screen.getByText('Restart Sensor');
    fireEvent.click(restartButton);
    
    await waitFor(() => {
      expect(mockRestart).toHaveBeenCalledWith('TEMP-A1-01');
    });
  });

  it('shows low battery warning with red text', () => {
    const lowBatteryProps = {
      ...defaultProps,
      battery_level: 15,
    };

    render(<SensorStatus {...lowBatteryProps} />);
    
    const batteryText = screen.getByText('15%');
    expect(batteryText).toHaveClass('text-red-600');
  });
});

// Hook testing
describe('useSensorMonitoring Hook', () => {
  it('should detect new silent sensor alerts', async () => {
    const { result } = renderHook(() => useSensorMonitoring('client-a'));
    
    // Simulate WebSocket alert
    act(() => {
      const mockAlert = {
        sensor_id: 'TEMP-A1-01',
        severity: 'critical',
        silence_duration: 20
      };
      // Trigger WebSocket event simulation
      result.current.handleSilentSensorAlert(mockAlert);
    });

    expect(result.current.silentAlerts).toHaveLength(1);
    expect(result.current.silentAlerts[0].sensor_id).toBe('TEMP-A1-01');
  });
});
```

## SECURITY STANDARDS

### Environment Variables
```bash
# .env.example - NUNCA commitear .env real
NODE_ENV=development
PORT=8000
API_VERSION=v1

# Database
DATABASE_URL=postgresql://user:password@localhost:5432/storepulse_dev
DATABASE_MAX_CONNECTIONS=20
TIMESCALEDB_ENABLED=true

# Redis
REDIS_URL=redis://localhost:6379
REDIS_PASSWORD=

# Google Cloud Platform
GOOGLE_CLOUD_PROJECT=storepulse-dev
PUBSUB_EMULATOR_HOST=localhost:8085
GOOGLE_APPLICATION_CREDENTIALS=path/to/service-account.json

# JWT
JWT_SECRET=generate-secure-random-secret-here
JWT_EXPIRES_IN=24h
JWT_REFRESH_EXPIRES_IN=7d

# Multi-Tenant Security
TENANT_ISOLATION_ENABLED=true
CROSS_TENANT_VALIDATION=strict

# Agent Communication
AGENT_API_KEY=generate-secure-agent-api-key
AGENT_HEARTBEAT_INTERVAL=30
AGENT_TIMEOUT_SECONDS=300

# Alert System
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
EMAIL_SMTP_URL=smtp://user:pass@smtp.gmail.com:587
SMS_PROVIDER=twilio
TWILIO_ACCOUNT_SID=your-account-sid

# Monitoring
LOG_LEVEL=info
SENTRY_DSN=https://your-sentry-dsn
PROMETHEUS_METRICS_ENABLED=true

# Rate Limiting
RATE_LIMIT_WINDOW_MS=900000
RATE_LIMIT_MAX_REQUESTS=100
```

### Multi-Tenant Input Validation
```python
from fastapi import Depends, HTTPException, Request
from pydantic import ValidationError

async def validate_tenant_access(
    request: Request,
    tenant_id: str = Path(...),
    current_user: User = Depends(get_current_user)
) -> str:
    """Validate that user has access to specified tenant."""
    
    # Check if user belongs to tenant
    if current_user.tenant_id != tenant_id:
        raise HTTPException(
            status_code=403,
            detail="Access denied: User does not belong to specified tenant"
        )
    
    # Validate tenant exists and is active
    tenant = await TenantService.get_active_tenant(tenant_id)
    if not tenant:
        raise HTTPException(
            status_code=404,
            detail="Tenant not found or inactive"
        )
    
    return tenant_id

class SensorControlRequest(BaseModel):
    sensor_id: str = Field(..., min_length=1, max_length=100, regex=r'^[A-Z0-9\-]+$')
    action: Literal["restart", "test", "configure"] = Field(...)
    tenant_id: str = Field(..., min_length=1, max_length=36)
    
    @validator('sensor_id')
    def validate_sensor_id_format(cls, v):
        """Ensure sensor ID follows expected format."""
        if not v.startswith(('TEMP-', 'DOOR-', 'MOTION-', 'POWER-', 'POS-')):
            raise ValueError('Sensor ID must start with valid type prefix')
        return v

@app.post("/api/v1/tenants/{tenant_id}/sensors/control")
async def control_sensor(
    request: SensorControlRequest,
    tenant_id: str = Depends(validate_tenant_access),
    current_user: User = Depends(get_current_user)
):
    """Control sensor with strict tenant isolation."""
    
    # Double-check tenant isolation
    if request.tenant_id != tenant_id:
        raise HTTPException(
            status_code=400,
            detail="Request tenant_id must match URL tenant_id"
        )
    
    # Validate sensor belongs to tenant
    sensor = await SensorService.get_sensor(request.sensor_id, tenant_id)
    if not sensor:
        raise HTTPException(
            status_code=404,
            detail="Sensor not found or does not belong to tenant"
        )
    
    # Execute control action
    result = await SensorService.execute_control_action(
        sensor_id=request.sensor_id,
        action=request.action,
        tenant_id=tenant_id,
        user_id=current_user.user_id
    )
    
    return {"success": True, "result": result}
```

## DOCUMENTATION STANDARDS

### Code Documentation
```python
"""
StorePulse Alert Service

Provides intelligent alert detection and multi-channel notification
for silent sensors, agent failures, and system anomalies.

Key Responsibilities:
- Real-time monitoring of sensor heartbeats
- Detection of silent sensors with type-specific thresholds
- Multi-channel alert dispatching (Slack, Email, SMS, Dashboard)
- Alert escalation based on severity and duration
- Integration with admin dashboard for manual interventions

Example Usage:
    ```python
    alert_service = AlertService(db_session, redis_client)
    
    # Detect silent sensors for a tenant
    silent_sensors = await alert_service.detect_silent_sensors("client-a")
    
    # Create and dispatch alert for critical sensor
    if silent_sensors:
        await alert_service.create_silent_sensor_alert(silent_sensors[0])
    ```

Alert Severity Levels:
- WARNING: Initial silence detection (5-15 min)
- CRITICAL: Extended silence (15+ min) or POS systems
- EMERGENCY: Business-critical sensors silent >30 min
"""

class AlertService:
    """
    Core alert service for StorePulse monitoring system.
    
    Manages detection, creation, and dispatching of alerts for
    silent sensors, offline agents, and system failures.
    """
    
    def __init__(self, db_session: AsyncSession, redis_client: Redis):
        """
        Initialize AlertService with database and cache connections.
        
        Args:
            db_session: Async SQLAlchemy database session
            redis_client: Redis client for real-time operations
        """
        self.db = db_session
        self.redis = redis_client
        self.logger = logging.getLogger(__name__)
    
    async def detect_silent_sensors(
        self, 
        tenant_id: str,
        silence_threshold_minutes: Optional[int] = None
    ) -> List[SilentSensorData]:
        """
        Detect sensors that have stopped reporting within threshold.
        
        Analyzes all active sensors for a tenant and identifies those
        that haven't reported readings within their expected intervals.
        Uses sensor-type-specific thresholds for accurate detection.
        
        Args:
            tenant_id: Unique identifier for the tenant
            silence_threshold_minutes: Override default thresholds (optional)
            
        Returns:
            List of SilentSensorData objects with detection details
            
        Raises:
            TenantNotFoundError: If tenant doesn't exist
            DatabaseError: If query execution fails
            
        Example:
            ```python
            silent_sensors = await alert_service.detect_silent_sensors("client-a")
            for sensor in silent_sensors:
                if sensor.severity == "emergency":
                    await dispatch_immediate_alert(sensor)
            ```
        """
        try:
            # Implementation with comprehensive error handling
            sensors = await self._get_active_sensors(tenant_id)
            silent_sensors = []
            
            for sensor in sensors:
                silence_duration = self._calculate_silence_duration(sensor)
                threshold = self._get_sensor_threshold(
                    sensor.sensor_type, 
                    silence_threshold_minutes
                )
                
                if silence_duration > threshold:
                    silent_sensor = SilentSensorData(
                        sensor_id=sensor.sensor_id,
                        tenant_id=tenant_id,
                        sensor_type=sensor.sensor_type,
                        silence_duration_minutes=silence_duration,
                        last_seen=sensor.last_reading,
                        severity=self._calculate_severity(silence_duration, sensor.sensor_type),
                        business_impact=self._assess_business_impact(sensor)
                    )
                    silent_sensors.append(silent_sensor)
            
            return silent_sensors
            
        except Exception as e:
            self.logger.error(
                "Failed to detect silent sensors",
                extra={"tenant_id": tenant_id, "error": str(e)}
            )
            raise
```

Este conjunto de estándares asegura que el código de StorePulse sea consistente, mantenible y robusto para el manejo de sistemas IoT críticos de retail multi-tenant.