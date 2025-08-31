# STOREPULSE - PATRONES DE DISEÑO

## FILOSOFÍA ARQUITECTURAL

### Edge-Computing First Architecture
El sistema está diseñado para operar en edge computing con capacidades offline, donde cada agente local puede funcionar independientemente y sincronizar cuando la conectividad esté disponible.

### Event-Driven Architecture (EDA)
Todos los cambios de estado importantes (sensores silenciosos, caídas de agents, sync failures) generan eventos que otros componentes pueden consumir de manera asíncrona.

### Defensive Programming
Cada componente está diseñado para fallar de manera graceful, validar todas las entradas y manejar errores de forma explícita, especialmente crítico en sistemas IoT de retail.

### Multi-Tenant Isolation
La organización del código garantiza aislamiento completo de datos entre diferentes clientes retail mientras optimiza infraestructura compartida.

## EVENT-DRIVEN PATTERNS

### 1. Event Bus Pattern
Centraliza la gestión de eventos entre todos los servicios del sistema StorePulse.

```typescript
// shared/events/event.bus.ts
export interface StorePulseEvent {
  readonly eventId: string;
  readonly eventType: string;
  readonly entityId: string;  // sensor_id, agent_id, etc.
  readonly tenantId: string;
  readonly timestamp: Date;
  readonly version: number;
  readonly payload: Record<string, unknown>;
  readonly metadata?: {
    storeLocation?: string;
    severity?: 'warning' | 'critical' | 'emergency';
    businessImpact?: 'low' | 'medium' | 'high';
    correlationId?: string;
  };
}

export class StorePulseEventBus {
  private handlers = new Map<string, EventHandler[]>();
  
  constructor(
    private pubSubClient: PubSub,
    private redisClient: Redis,
    private logger: Logger
  ) {}

  async publish(event: StorePulseEvent): Promise<void> {
    try {
      // Publish to Google Cloud Pub/Sub for cross-service communication
      const topicName = `storepulse-${event.tenantId}-${event.eventType}`;
      
      const messageId = await this.pubSubClient
        .topic(topicName)
        .publishMessage({
          data: Buffer.from(JSON.stringify(event)),
          attributes: {
            eventType: event.eventType,
            tenantId: event.tenantId,
            entityId: event.entityId,
            severity: event.metadata?.severity || 'medium',
          },
        });

      // Store in Redis for real-time dashboard updates
      await this.redisClient.lpush(
        `events:${event.tenantId}:recent`, 
        JSON.stringify(event)
      );
      await this.redisClient.ltrim(`events:${event.tenantId}:recent`, 0, 99); // Keep last 100

      this.logger.info('Event published', {
        eventId: event.eventId,
        eventType: event.eventType,
        messageId,
        tenantId: event.tenantId,
      });

      // Execute local handlers synchronously for immediate actions
      const localHandlers = this.handlers.get(event.eventType) || [];
      await Promise.allSettled(
        localHandlers.map(async handler => {
          try {
            await handler.handle(event);
          } catch (error) {
            this.logger.error('Local event handler failed', {
              eventType: event.eventType,
              error: error.message,
              handler: handler.constructor.name,
              tenantId: event.tenantId,
            });
          }
        })
      );
    } catch (error) {
      this.logger.error('Failed to publish event', {
        eventId: event.eventId,
        eventType: event.eventType,
        error: error.message,
      });
      throw error;
    }
  }

  subscribe<T extends StorePulseEvent>(
    eventType: string,
    handler: EventHandler<T>
  ): void {
    if (!this.handlers.has(eventType)) {
      this.handlers.set(eventType, []);
    }
    this.handlers.get(eventType)!.push(handler);
  }
}
```

### 2. Event Sourcing Pattern para Auditoria IoT
Almacena todos los cambios como una secuencia de eventos inmutables, crítico para sistemas IoT donde la trazabilidad es esencial.

```typescript
// shared/events/storepulse.event-store.ts
export class StorePulseEventStore {
  constructor(
    private db: Knex,
    private logger: Logger
  ) {}

  async append(
    streamId: string,
    events: StorePulseEvent[],
    expectedVersion?: number
  ): Promise<void> {
    await this.db.transaction(async (trx) => {
      // Verify expected version to prevent concurrency issues
      if (expectedVersion !== undefined) {
        const currentVersion = await this.getStreamVersion(trx, streamId);
        if (currentVersion !== expectedVersion) {
          throw new ConcurrencyError(
            `Expected version ${expectedVersion}, got ${currentVersion}`
          );
        }
      }

      // Insert events in order with tenant isolation
      for (const event of events) {
        await trx('event_store').insert({
          stream_id: streamId,
          event_id: event.eventId,
          event_type: event.eventType,
          entity_id: event.entityId,
          tenant_id: event.tenantId,
          event_data: JSON.stringify(event.payload),
          event_metadata: JSON.stringify(event.metadata || {}),
          version: event.version,
          timestamp: event.timestamp,
        });
      }
    });
  }

  async getEvents(
    streamId: string,
    fromVersion = 0,
    tenantId: string
  ): Promise<StorePulseEvent[]> {
    const rows = await this.db('event_store')
      .where({
        stream_id: streamId,
        tenant_id: tenantId,  // Always filter by tenant for security
      })
      .where('version', '>=', fromVersion)
      .orderBy('version', 'asc');

    return rows.map(row => ({
      eventId: row.event_id,
      eventType: row.event_type,
      entityId: row.entity_id,
      tenantId: row.tenant_id,
      timestamp: row.timestamp,
      version: row.version,
      payload: JSON.parse(row.event_data),
      metadata: JSON.parse(row.event_metadata),
    }));
  }

  async getRecentEventsForDashboard(
    tenantId: string,
    limit: number = 50
  ): Promise<StorePulseEvent[]> {
    const rows = await this.db('event_store')
      .where('tenant_id', tenantId)
      .where('timestamp', '>=', this.db.raw("NOW() - INTERVAL '24 hours'"))
      .orderBy('timestamp', 'desc')
      .limit(limit);

    return rows.map(this.mapRowToEvent);
  }
}
```

### 3. Command Pattern para Acciones de Control Remoto
Separa las operaciones de control remoto (restart sensor, sync agent) en comandos ejecutables.

```typescript
// modules/control/commands/sensor.commands.ts
export abstract class SensorCommand {
  abstract readonly tenantId: string;
  abstract readonly sensorId: string;
  abstract readonly userId: string;
  abstract readonly requestId: string;
}

export class RestartSensorCommand extends SensorCommand {
  constructor(
    public readonly tenantId: string,
    public readonly sensorId: string,
    public readonly userId: string,
    public readonly requestId: string,
    public readonly reason: string = 'Manual restart from admin dashboard',
    public readonly metadata?: Record<string, unknown>
  ) {
    super();
  }
}

export class TestSensorConnectionCommand extends SensorCommand {
  constructor(
    public readonly tenantId: string,
    public readonly sensorId: string,
    public readonly userId: string,
    public readonly requestId: string,
    public readonly testType: 'ping' | 'full_diagnostic' = 'ping'
  ) {
    super();
  }
}

// modules/control/handlers/sensor.command-handler.ts
export class SensorCommandHandler {
  constructor(
    private sensorService: SensorService,
    private eventBus: StorePulseEventBus,
    private redisClient: Redis,
    private logger: Logger
  ) {}

  async handle(command: RestartSensorCommand): Promise<void> {
    try {
      // Validate sensor exists and belongs to tenant
      const sensor = await this.sensorService.findSensorById(
        command.tenantId,
        command.sensorId
      );

      if (!sensor) {
        throw new NotFoundError('Sensor not found or access denied');
      }

      // Send restart command to agent via Redis pub/sub
      const controlMessage = {
        command: 'restart_sensor',
        sensor_id: command.sensorId,
        request_id: command.requestId,
        timestamp: new Date().toISOString(),
        timeout_seconds: 30,
      };

      await this.redisClient.publish(
        `agent:commands:${sensor.agentId}`,
        JSON.stringify(controlMessage)
      );

      // Create audit event
      const event = new SensorRestartCommandedEvent({
        tenantId: command.tenantId,
        entityId: command.sensorId,
        sensorId: command.sensorId,
        agentId: sensor.agentId,
        requestedBy: command.userId,
        reason: command.reason,
        requestId: command.requestId,
      });

      await this.eventBus.publish(event);

      this.logger.info('Sensor restart command sent', {
        tenantId: command.tenantId,
        sensorId: command.sensorId,
        agentId: sensor.agentId,
        userId: command.userId,
        requestId: command.requestId,
      });

    } catch (error) {
      this.logger.error('Failed to send sensor restart command', {
        tenantId: command.tenantId,
        sensorId: command.sensorId,
        error: error.message,
        requestId: command.requestId,
      });

      // Publish failure event
      const failureEvent = new SensorCommandFailedEvent({
        tenantId: command.tenantId,
        entityId: command.sensorId,
        commandType: 'restart_sensor',
        error: error.message,
        requestId: command.requestId,
      });

      await this.eventBus.publish(failureEvent);
      throw error;
    }
  }
}
```

### 4. Circuit Breaker Pattern para Resilencia
Maneja fallos en comunicación con agentes remotos de manera resiliente.

```typescript
// shared/resilience/circuit-breaker.ts
export enum CircuitState {
  CLOSED = 'closed',
  OPEN = 'open',
  HALF_OPEN = 'half-open'
}

export class CircuitBreaker {
  private failureCount = 0;
  private lastFailureTime?: Date;
  private state = CircuitState.CLOSED;

  constructor(
    private failureThreshold: number = 5,
    private recoveryTimeoutMs: number = 60000,  // 1 minute
    private logger: Logger
  ) {}

  async execute<T>(
    operation: () => Promise<T>,
    fallback?: () => Promise<T>
  ): Promise<T> {
    if (this.state === CircuitState.OPEN) {
      if (this.shouldAttemptReset()) {
        this.state = CircuitState.HALF_OPEN;
        this.logger.info('Circuit breaker moved to HALF_OPEN state');
      } else {
        this.logger.warn('Circuit breaker is OPEN, using fallback');
        if (fallback) {
          return await fallback();
        }
        throw new Error('Circuit breaker is OPEN and no fallback provided');
      }
    }

    try {
      const result = await operation();
      this.onSuccess();
      return result;
    } catch (error) {
      this.onFailure();
      throw error;
    }
  }

  private shouldAttemptReset(): boolean {
    return this.lastFailureTime && 
           (Date.now() - this.lastFailureTime.getTime()) >= this.recoveryTimeoutMs;
  }

  private onSuccess(): void {
    this.failureCount = 0;
    this.state = CircuitState.CLOSED;
  }

  private onFailure(): void {
    this.failureCount++;
    this.lastFailureTime = new Date();

    if (this.failureCount >= this.failureThreshold) {
      this.state = CircuitState.OPEN;
      this.logger.error(`Circuit breaker opened after ${this.failureCount} failures`);
    }
  }
}

// Usage in Agent Communication Service
export class AgentCommunicationService {
  private circuitBreakers = new Map<string, CircuitBreaker>();

  constructor(private redisClient: Redis, private logger: Logger) {}

  async sendCommandToAgent(
    agentId: string,
    command: any,
    timeoutMs: number = 30000
  ): Promise<any> {
    const circuitBreaker = this.getOrCreateCircuitBreaker(agentId);

    return await circuitBreaker.execute(
      async () => {
        // Primary operation: send command and wait for response
        const response = await this.sendAndWaitForResponse(agentId, command, timeoutMs);
        return response;
      },
      async () => {
        // Fallback: log that agent is unreachable and return offline status
        this.logger.warn(`Agent ${agentId} unreachable, using fallback response`);
        return {
          success: false,
          error: 'Agent communication circuit breaker open',
          fallback: true
        };
      }
    );
  }

  private getOrCreateCircuitBreaker(agentId: string): CircuitBreaker {
    if (!this.circuitBreakers.has(agentId)) {
      this.circuitBreakers.set(
        agentId, 
        new CircuitBreaker(3, 60000, this.logger) // 3 failures, 1 minute recovery
      );
    }
    return this.circuitBreakers.get(agentId)!;
  }
}
```

## DOMAIN-DRIVEN DESIGN PATTERNS

### 1. Aggregate Pattern para Sensor Management
Encapsula lógica de negocio de sensores y mantiene consistencia.

```typescript
// modules/sensors/domain/sensor.aggregate.ts
export class SensorAggregate {
  private events: StorePulseEvent[] = [];

  constructor(
    public readonly sensorId: string,
    public readonly tenantId: string,
    public readonly agentId: string,
    public readonly sensorType: SensorType,
    public readonly location: string,
    private status: SensorStatus,
    private lastReading: Date | null,
    private batteryLevel: number | null,
    private signalStrength: number,
    private errorCount: number = 0,
    private version: number = 0
  ) {}

  updateStatus(
    newStatus: SensorStatus,
    reason: string,
    userId: string,
    metadata?: Record<string, unknown>
  ): StorePulseEvent[] {
    // Business rule: Can't transition to certain states directly
    if (!this.isValidStatusTransition(this.status, newStatus)) {
      throw new BusinessRuleViolationError(
        `Invalid status transition from ${this.status} to ${newStatus}`,
        { currentStatus: this.status, newStatus, sensorId: this.sensorId }
      );
    }

    const oldStatus = this.status;
    this.status = newStatus;
    this.version++;

    // Generate status change event
    const statusChangedEvent = new SensorStatusChangedEvent({
      tenantId: this.tenantId,
      entityId: this.sensorId,
      sensorId: this.sensorId,
      agentId: this.agentId,
      oldStatus,
      newStatus,
      reason,
      changedBy: userId,
      metadata,
      version: this.version,
    });

    this.events.push(statusChangedEvent);

    // If sensor goes silent, generate alert event
    if (newStatus === SensorStatus.SILENT && oldStatus !== SensorStatus.SILENT) {
      const silenceAlertEvent = new SensorSilentAlertEvent({
        tenantId: this.tenantId,
        entityId: this.sensorId,
        sensorId: this.sensorId,
        sensorType: this.sensorType,
        location: this.location,
        lastSeen: this.lastReading,
        severity: this.calculateSilentSeverity(),
        businessImpact: this.assessBusinessImpact(),
        version: this.version,
      });

      this.events.push(silenceAlertEvent);
    }

    // If sensor recovers from silent state, generate recovery event
    if (oldStatus === SensorStatus.SILENT && newStatus === SensorStatus.ACTIVE) {
      const recoveryEvent = new SensorRecoveredEvent({
        tenantId: this.tenantId,
        entityId: this.sensorId,
        sensorId: this.sensorId,
        downDuration: this.calculateDownDuration(),
        version: this.version,
      });

      this.events.push(recoveryEvent);
    }

    return this.getUncommittedEvents();
  }

  recordReading(
    value: number,
    unit: string,
    timestamp: Date = new Date(),
    metadata?: Record<string, unknown>
  ): StorePulseEvent[] {
    // Business rule: Can't record readings for inactive sensors
    if (this.status !== SensorStatus.ACTIVE) {
      throw new BusinessRuleViolationError(
        `Cannot record reading for sensor in ${this.status} status`,
        { sensorId: this.sensorId, status: this.status }
      );
    }

    this.lastReading = timestamp;
    this.version++;

    // If sensor was previously silent, it has recovered
    const wasRecovered = this.status === SensorStatus.SILENT;
    if (wasRecovered) {
      this.status = SensorStatus.ACTIVE;
    }

    const readingEvent = new SensorReadingRecordedEvent({
      tenantId: this.tenantId,
      entityId: this.sensorId,
      sensorId: this.sensorId,
      value,
      unit,
      timestamp,
      metadata,
      version: this.version,
    });

    this.events.push(readingEvent);

    if (wasRecovered) {
      const recoveryEvent = new SensorRecoveredEvent({
        tenantId: this.tenantId,
        entityId: this.sensorId,
        sensorId: this.sensorId,
        downDuration: this.calculateDownDuration(),
        version: this.version,
      });

      this.events.push(recoveryEvent);
    }

    return this.getUncommittedEvents();
  }

  private isValidStatusTransition(from: SensorStatus, to: SensorStatus): boolean {
    const validTransitions: Record<SensorStatus, SensorStatus[]> = {
      [SensorStatus.ACTIVE]: [SensorStatus.INACTIVE, SensorStatus.ERROR, SensorStatus.SILENT],
      [SensorStatus.INACTIVE]: [SensorStatus.ACTIVE, SensorStatus.ERROR, SensorStatus.SILENT],
      [SensorStatus.ERROR]: [SensorStatus.ACTIVE, SensorStatus.INACTIVE, SensorStatus.SILENT],
      [SensorStatus.SILENT]: [SensorStatus.ACTIVE, SensorStatus.ERROR],  // Can't go directly to inactive
    };

    return validTransitions[from]?.includes(to) || false;
  }

  private calculateSilentSeverity(): string {
    const silenceDuration = this.calculateSilenceDuration();
    const thresholds = this.getSensorTypeThresholds();

    if (silenceDuration > thresholds.emergency) return 'emergency';
    if (silenceDuration > thresholds.critical) return 'critical';
    return 'warning';
  }

  private assessBusinessImpact(): string {
    // POS and power sensors have high business impact
    if (this.sensorType === SensorType.POS || this.sensorType === SensorType.POWER) {
      return 'high';
    }
    
    // Temperature sensors for refrigeration are medium impact
    if (this.sensorType === SensorType.TEMPERATURE) {
      return 'medium';
    }

    return 'low';
  }

  getUncommittedEvents(): StorePulseEvent[] {
    const events = [...this.events];
    this.events = [];
    return events;
  }

  static fromHistory(events: StorePulseEvent[]): SensorAggregate {
    if (events.length === 0) {
      throw new Error('Cannot create sensor aggregate from empty event history');
    }

    const firstEvent = events[0];
    if (firstEvent.eventType !== 'sensor.created') {
      throw new Error('First event must be sensor.created');
    }

    const aggregate = new SensorAggregate(
      firstEvent.entityId,
      firstEvent.tenantId,
      firstEvent.payload.agentId as string,
      firstEvent.payload.sensorType as SensorType,
      firstEvent.payload.location as string,
      SensorStatus.ACTIVE,
      null,
      null,
      100,
      0,
      0
    );

    // Apply historical events
    events.slice(1).forEach(event => {
      aggregate.applyEvent(event);
    });

    return aggregate;
  }

  private applyEvent(event: StorePulseEvent): void {
    switch (event.eventType) {
      case 'sensor.status.changed':
        this.status = event.payload.newStatus as SensorStatus;
        break;
      case 'sensor.reading.recorded':
        this.lastReading = new Date(event.payload.timestamp as string);
        break;
      case 'sensor.battery.updated':
        this.batteryLevel = event.payload.batteryLevel as number;
        break;
    }
    this.version = event.version;
  }
}
```

### 2. Repository Pattern con Multi-Tenant Security
Abstrae el acceso a datos manteniendo aislamiento de tenants.

```typescript
// modules/sensors/domain/sensor.repository.interface.ts
export interface ISensorRepository {
  findById(tenantId: string, sensorId: string): Promise<SensorAggregate | null>;
  findByAgent(tenantId: string, agentId: string): Promise<SensorAggregate[]>;
  findSilentSensors(tenantId: string, thresholdMinutes: number): Promise<SensorAggregate[]>;
  findByType(tenantId: string, sensorType: SensorType): Promise<SensorAggregate[]>;
  save(aggregate: SensorAggregate): Promise<void>;
  delete(tenantId: string, sensorId: string): Promise<void>;
}

// modules/sensors/infrastructure/sensor.repository.ts
export class SensorRepository implements ISensorRepository {
  constructor(
    private db: Knex,
    private eventStore: StorePulseEventStore,
    private logger: Logger
  ) {}

  async findById(tenantId: string, sensorId: string): Promise<SensorAggregate | null> {
    try {
      // Always include tenant_id in queries for security
      const sensorData = await this.db('sensors')
        .where({
          sensor_id: sensorId,
          tenant_id: tenantId,  // Critical: Always filter by tenant
          deleted_at: null
        })
        .first();

      if (!sensorData) {
        return null;
      }

      // Load events for this sensor
      const events = await this.eventStore.getEvents(
        sensorId, 
        0, 
        tenantId  // Pass tenant to event store for additional security
      );

      if (events.length > 0) {
        return SensorAggregate.fromHistory(events);
      }

      // If no events exist, create from database snapshot
      return this.createAggregateFromSnapshot(sensorData);

    } catch (error) {
      this.logger.error('Failed to load sensor aggregate', {
        tenantId,
        sensorId,
        error: error.message,
      });
      throw new RepositoryError('Failed to load sensor', error);
    }
  }

  async findSilentSensors(
    tenantId: string, 
    thresholdMinutes: number = 10
  ): Promise<SensorAggregate[]> {
    const cutoffTime = new Date(Date.now() - thresholdMinutes * 60 * 1000);

    try {
      const silentSensorData = await this.db('sensors')
        .where('tenant_id', tenantId)
        .where('deleted_at', null)
        .where(builder => {
          builder
            .where('last_reading', '<', cutoffTime)
            .orWhereNull('last_reading');
        })
        .whereNotIn('status', ['silent'])  // Don't re-detect already marked silent
        .orderBy('last_reading', 'asc');

      // Convert to aggregates
      const aggregates = await Promise.all(
        silentSensorData.map(async (data) => {
          const events = await this.eventStore.getEvents(
            data.sensor_id, 
            0, 
            tenantId
          );
          
          if (events.length > 0) {
            return SensorAggregate.fromHistory(events);
          }
          
          return this.createAggregateFromSnapshot(data);
        })
      );

      return aggregates.filter(Boolean);

    } catch (error) {
      this.logger.error('Failed to find silent sensors', {
        tenantId,
        thresholdMinutes,
        error: error.message,
      });
      throw error;
    }
  }

  async save(aggregate: SensorAggregate): Promise<void> {
    const events = aggregate.getUncommittedEvents();
    
    if (events.length === 0) {
      return;
    }

    try {
      await this.db.transaction(async (trx) => {
        // Save events to event store
        await this.eventStore.append(aggregate.sensorId, events);

        // Update read model (projection)
        await this.updateReadModel(trx, aggregate);

        // Update sensor status for quick queries
        await this.updateSensorSnapshot(trx, aggregate);
      });

    } catch (error) {
      this.logger.error('Failed to save sensor aggregate', {
        tenantId: aggregate.tenantId,
        sensorId: aggregate.sensorId,
        eventsCount: events.length,
        error: error.message,
      });
      throw error;
    }
  }

  private async updateReadModel(
    trx: Knex.Transaction,
    aggregate: SensorAggregate
  ): Promise<void> {
    // Update the sensor read model table for fast queries
    await trx('sensors')
      .where({
        sensor_id: aggregate.sensorId,
        tenant_id: aggregate.tenantId,
      })
      .update({
        status: aggregate.status,
        last_reading: aggregate.lastReading,
        battery_level: aggregate.batteryLevel,
        signal_strength: aggregate.signalStrength,
        error_count: aggregate.errorCount,
        updated_at: new Date(),
        version: aggregate.version,
      });
  }

  private createAggregateFromSnapshot(sensorData: any): SensorAggregate {
    return new SensorAggregate(
      sensorData.sensor_id,
      sensorData.tenant_id,
      sensorData.agent_id,
      sensorData.sensor_type,
      sensorData.location,
      sensorData.status,
      sensorData.last_reading,
      sensorData.battery_level,
      sensorData.signal_strength,
      sensorData.error_count,
      sensorData.version
    );
  }
}
```

### 3. Value Object Pattern para Configuración de Sensores
Encapsula valores relacionados y sus validaciones específicas de IoT.

```typescript
// shared/domain/value-objects/sensor-configuration.ts
export class SensorConfiguration {
  constructor(
    public readonly readingInterval: number,  // seconds
    public readonly alertThresholds: AlertThresholds,
    public readonly batteryWarningLevel: number,  // percentage
    public readonly signalStrengthThreshold: number  // percentage
  ) {
    if (readingInterval < 5 || readingInterval > 3600) {
      throw new Error('Reading interval must be between 5 seconds and 1 hour');
    }
    
    if (batteryWarningLevel < 0 || batteryWarningLevel > 100) {
      throw new Error('Battery warning level must be between 0 and 100 percent');
    }
    
    if (signalStrengthThreshold < 0 || signalStrengthThreshold > 100) {
      throw new Error('Signal strength threshold must be between 0 and 100 percent');
    }
  }

  static forSensorType(sensorType: SensorType): SensorConfiguration {
    const configurations: Record<SensorType, SensorConfiguration> = {
      [SensorType.TEMPERATURE]: new SensorConfiguration(
        300,  // 5 minutes
        new AlertThresholds(600, 1200, 1800),  // 10min, 20min, 30min
        20,   // 20% battery warning
        30    // 30% signal threshold
      ),
      [SensorType.DOOR]: new SensorConfiguration(
        60,   // 1 minute
        new AlertThresholds(300, 900, 1800),   // 5min, 15min, 30min
        15,   // 15% battery warning
        25    // 25% signal threshold
      ),
      [SensorType.POS]: new SensorConfiguration(
        30,   // 30 seconds - critical business sensor
        new AlertThresholds(120, 300, 600),    // 2min, 5min, 10min
        25,   // 25% battery warning
        40    // 40% signal threshold
      ),
      [SensorType.POWER]: new SensorConfiguration(
        60,   // 1 minute
        new AlertThresholds(180, 600, 1200),   // 3min, 10min, 20min
        30,   // 30% battery warning
        35    // 35% signal threshold
      ),
      [SensorType.MOTION]: new SensorConfiguration(
        180,  // 3 minutes
        new AlertThresholds(900, 1800, 3600),  // 15min, 30min, 1hour
        20,   // 20% battery warning
        20    // 20% signal threshold
      ),
    };

    return configurations[sensorType];
  }

  isCriticalSensor(): boolean {
    return this.alertThresholds.criticalSeconds < 600; // Less than 10 minutes means critical
  }

  shouldAlertOnBattery(currentLevel: number): boolean {
    return currentLevel <= this.batteryWarningLevel;
  }

  shouldAlertOnSignal(currentStrength: number): boolean {
    return currentStrength <= this.signalStrengthThreshold;
  }
}

export class AlertThresholds {
  constructor(
    public readonly warningSeconds: number,
    public readonly criticalSeconds: number,
    public readonly emergencySeconds: number
  ) {
    if (warningSeconds >= criticalSeconds || criticalSeconds >= emergencySeconds) {
      throw new Error('Alert thresholds must be in ascending order');
    }
    
    if (warningSeconds < 60) {
      throw new Error('Warning threshold must be at least 60 seconds');
    }
  }

  calculateSeverity(silenceDurationSeconds: number): 'warning' | 'critical' | 'emergency' {
    if (silenceDurationSeconds >= this.emergencySeconds) return 'emergency';
    if (silenceDurationSeconds >= this.criticalSeconds) return 'critical';
    return 'warning';
  }

  getNextEscalationTime(currentSeverity: 'warning' | 'critical' | 'emergency'): number | null {
    switch (currentSeverity) {
      case 'warning':
        return this.criticalSeconds;
      case 'critical':
        return this.emergencySeconds;
      case 'emergency':
        return null; // No further escalation
    }
  }
}

// modules/sensors/domain/value-objects/sensor-health.ts
export class SensorHealth {
  constructor(
    public readonly batteryLevel: number | null,
    public readonly signalStrength: number,
    public readonly lastReading: Date | null,
    public readonly errorCount: number,
    private readonly configuration: SensorConfiguration
  ) {}

  isHealthy(): boolean {
    return (
      this.isBatteryHealthy() &&
      this.isSignalHealthy() &&
      this.isReadingRecent() &&
      this.errorCount < 5
    );
  }

  isBatteryHealthy(): boolean {
    if (this.batteryLevel === null) return true; // Some sensors don't have batteries
    return !this.configuration.shouldAlertOnBattery(this.batteryLevel);
  }

  isSignalHealthy(): boolean {
    return !this.configuration.shouldAlertOnSignal(this.signalStrength);
  }

  isReadingRecent(): boolean {
    if (!this.lastReading) return false;
    
    const silenceDuration = (Date.now() - this.lastReading.getTime()) / 1000;
    return silenceDuration < this.configuration.alertThresholds.warningSeconds;
  }

  getHealthScore(): number {
    let score = 100;
    
    if (!this.isBatteryHealthy()) {
      score -= 25;
    }
    
    if (!this.isSignalHealthy()) {
      score -= 20;
    }
    
    if (!this.isReadingRecent()) {
      const silenceDuration = this.getSilenceDurationSeconds();
      if (silenceDuration > this.configuration.alertThresholds.emergencySeconds) {
        score -= 40;
      } else if (silenceDuration > this.configuration.alertThresholds.criticalSeconds) {
        score -= 30;
      } else {
        score -= 15;
      }
    }
    
    score -= Math.min(this.errorCount * 2, 20); // Max 20 points for errors
    
    return Math.max(0, score);
  }

  private getSilenceDurationSeconds(): number {
    if (!this.lastReading) return Infinity;
    return (Date.now() - this.lastReading.getTime()) / 1000;
  }

  getHealthStatus(): 'excellent' | 'good' | 'warning' | 'critical' | 'emergency' {
    const score = this.getHealthScore();
    
    if (score >= 90) return 'excellent';
    if (score >= 75) return 'good';
    if (score >= 50) return 'warning';
    if (score >= 25) return 'critical';
    return 'emergency';
  }
}
```

## EDGE COMPUTING PATTERNS

### 1. Offline-First Agent Pattern
Agente que opera primariamente offline con sincronización periódica.

```python
# agents/base_agent.py
import asyncio
import sqlite3
import json
import gzip
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from enum import Enum

class AgentState(Enum):
    ONLINE = "online"
    OFFLINE = "offline"
    SYNCING = "syncing"
    ERROR = "error"

class OfflineFirstAgent:
    def __init__(self, agent_id: str, tenant_id: str, config: dict):
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.config = config
        self.state = AgentState.OFFLINE
        
        # Initialize SQLite buffer with WAL mode for concurrency
        self.buffer_db = self.init_sqlite_buffer()
        
        # Sync manager for resilient uploads
        self.sync_manager = SyncManager(agent_id, self.buffer_db)
        
        # Heartbeat manager for connectivity monitoring
        self.heartbeat_manager = HeartbeatManager(agent_id, tenant_id)
        
    def init_sqlite_buffer(self) -> sqlite3.Connection:
        """Initialize SQLite database with WAL mode for offline buffer."""
        db_path = f"data/{self.agent_id}_buffer.db"
        conn = sqlite3.connect(db_path, check_same_thread=False)
        
        # Enable WAL mode for concurrent access
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        
        # Create buffer tables
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sensor_readings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sensor_id TEXT NOT NULL,
                sensor_type TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT,
                timestamp DATETIME NOT NULL,
                metadata TEXT,
                synced INTEGER DEFAULT 0,
                retry_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS pos_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_id TEXT NOT NULL,
                event_type TEXT NOT NULL,
                amount REAL,
                timestamp DATETIME NOT NULL,
                metadata TEXT,
                synced INTEGER DEFAULT 0,
                retry_count INTEGER DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sync_batches (
                batch_id TEXT PRIMARY KEY,
                batch_type TEXT NOT NULL,
                record_count INTEGER NOT NULL,
                compressed_data BLOB NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                uploaded_at DATETIME,
                status TEXT DEFAULT 'pending'
            )
        """)
        
        conn.commit()
        return conn
        
    async def start(self):
        """Start the agent with all background tasks."""
        self.logger.info(f"Starting agent {self.agent_id}")
        
        # Start background tasks
        tasks = [
            asyncio.create_task(self.sensor_collection_loop()),
            asyncio.create_task(self.pos_monitoring_loop()),
            asyncio.create_task(self.heartbeat_loop()),
            asyncio.create_task(self.sync_loop()),
            asyncio.create_task(self.cleanup_loop()),
        ]
        
        try:
            await asyncio.gather(*tasks)
        except Exception as e:
            self.logger.error(f"Agent {self.agent_id} crashed: {e}")
            await self.handle_agent_crash(e)
    
    async def sensor_collection_loop(self):
        """Continuously collect sensor data."""
        while True:
            try:
                sensors = await self.discover_sensors()
                
                for sensor in sensors:
                    try:
                        reading = await self.read_sensor(sensor)
                        await self.buffer_sensor_reading(reading)
                        
                    except Exception as e:
                        self.logger.error(f"Failed to read sensor {sensor.id}: {e}")
                        await self.record_sensor_error(sensor.id, str(e))
                
                # Sleep based on configuration
                await asyncio.sleep(self.config.get('sensor_interval', 60))
                
            except Exception as e:
                self.logger.error(f"Sensor collection loop error: {e}")
                await asyncio.sleep(30)  # Back off on errors
    
    async def buffer_sensor_reading(self, reading: dict):
        """Buffer sensor reading to SQLite for eventual sync."""
        try:
            cursor = self.buffer_db.cursor()
            cursor.execute("""
                INSERT INTO sensor_readings 
                (sensor_id, sensor_type, value, unit, timestamp, metadata)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                reading['sensor_id'],
                reading['sensor_type'],
                reading['value'],
                reading.get('unit'),
                reading['timestamp'],
                json.dumps(reading.get('metadata', {}))
            ))
            self.buffer_db.commit()
            
            # Update buffer size metric
            await self.update_buffer_metrics()
            
        except Exception as e:
            self.logger.error(f"Failed to buffer sensor reading: {e}")
    
    async def sync_loop(self):
        """Periodically sync buffered data to cloud."""
        while True:
            try:
                if await self.check_connectivity():
                    self.state = AgentState.SYNCING
                    await self.sync_manager.sync_pending_data()
                    self.state = AgentState.ONLINE
                else:
                    self.state = AgentState.OFFLINE
                    
                # Sleep based on connectivity
                sleep_duration = 30 if self.state == AgentState.ONLINE else 60
                await asyncio.sleep(sleep_duration)
                
            except Exception as e:
                self.logger.error(f"Sync loop error: {e}")
                self.state = AgentState.ERROR
                await asyncio.sleep(120)  # Back off more on sync errors

class SyncManager:
    def __init__(self, agent_id: str, buffer_db: sqlite3.Connection):
        self.agent_id = agent_id
        self.buffer_db = buffer_db
        self.max_batch_size = 100
        self.compression_enabled = True
        
    async def sync_pending_data(self):
        """Sync all pending data in batches with compression."""
        pending_readings = await self.get_pending_readings()
        pending_pos_events = await self.get_pending_pos_events()
        
        if pending_readings:
            await self.sync_sensor_readings(pending_readings)
            
        if pending_pos_events:
            await self.sync_pos_events(pending_pos_events)
    
    async def sync_sensor_readings(self, readings: List[dict]):
        """Sync sensor readings in compressed batches."""
        for i in range(0, len(readings), self.max_batch_size):
            batch = readings[i:i + self.max_batch_size]
            
            try:
                # Compress batch data
                batch_data = json.dumps(batch).encode('utf-8')
                if self.compression_enabled:
                    batch_data = gzip.compress(batch_data)
                
                # Upload to cloud
                success = await self.upload_batch(
                    batch_type='sensor_readings',
                    data=batch_data,
                    compressed=self.compression_enabled
                )
                
                if success:
                    # Mark as synced
                    ids = [reading['id'] for reading in batch]
                    await self.mark_readings_synced(ids)
                    
                else:
                    # Increment retry count
                    await self.increment_retry_count(
                        'sensor_readings', 
                        [r['id'] for r in batch]
                    )
                    
            except Exception as e:
                self.logger.error(f"Failed to sync readings batch: {e}")
    
    async def upload_batch(
        self, 
        batch_type: str, 
        data: bytes, 
        compressed: bool = False
    ) -> bool:
        """Upload compressed batch to cloud API with retry logic."""
        headers = {
            'X-Tenant-ID': self.tenant_id,
            'X-Agent-ID': self.agent_id,
            'Content-Type': 'application/json',
        }
        
        if compressed:
            headers['Content-Encoding'] = 'gzip'
        
        max_retries = 3
        for attempt in range(max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        f"{self.config['api_url']}/v1/ingest/{batch_type}",
                        data=data,
                        headers=headers,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as response:
                        
                        if response.status == 200:
                            return True
                        elif response.status in [500, 502, 503, 504]:
                            # Server errors - retry with exponential backoff
                            wait_time = 2 ** attempt
                            await asyncio.sleep(wait_time)
                            continue
                        else:
                            # Client errors - don't retry
                            self.logger.error(
                                f"Upload failed with status {response.status}"
                            )
                            return False
                            
            except asyncio.TimeoutError:
                self.logger.warning(f"Upload timeout on attempt {attempt + 1}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
                    
            except Exception as e:
                self.logger.error(f"Upload error on attempt {attempt + 1}: {e}")
                if attempt < max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
        
        return False
```

Estos patrones forman la base arquitectural robusta de StorePulse, proporcionando resiliencia, escalabilidad y mantenibilidad específicamente diseñados para sistemas IoT de retail multi-tenant con capacidades edge computing.