# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**StorePulse** is a multi-tenant retail monitoring platform designed for edge computing environments. The system monitors Point of Sale (POS) terminals and environmental sensors (temperature, humidity, door status) in real-time across retail store chains. The architecture prioritizes offline-first operation with cloud synchronization.

## Architecture

### System Design
- **Edge-First Architecture**: Each store operates independently with local agents and gateways
- **Multi-Tenant**: Single deployment serves multiple retail clients with strict data isolation
- **Event-Driven**: Uses event sourcing and CQRS patterns for audit trails and resilience
- **Technology Stack**: Go (agents), Python/FastAPI (backend), React (frontend), PostgreSQL + TimescaleDB (storage), Google Cloud Platform (cloud services)

### Key Components
1. **Edge Layer (Store)**:
   - POS Agents (Go executables on Windows terminals)
   - Local Gateway (Python/FastAPI with SQLite buffer)
   - IoT Sensors (WiFi-enabled temperature/door sensors)

2. **Cloud Layer (GCP)**:
   - API Gateway (Cloud Run)
   - Message Queue (Pub/Sub)
   - Processing (Cloud Functions)
   - Storage (Cloud SQL PostgreSQL with TimescaleDB)

3. **Presentation Layer**:
   - Client Dashboard (React + Vite + TailwindCSS)
   - Admin Dashboard (React + Material-UI)

## Development Standards

### Python/FastAPI Backend
- **Required**: Type hints for all functions and classes
- **Testing**: Pytest with async support, 80%+ coverage required
- **Error Handling**: Custom `StorePulseError` exceptions with tenant context
- **Database**: Always include `tenant_id` in queries for security isolation
- **Logging**: Structured logging with tenant/entity context

### Go Agents
- **Structure**: Modular design with health checks, network monitoring, and gateway communication
- **Deployment**: Windows services with automatic restart capability
- **Configuration**: YAML-based configuration with environment overrides

### React Frontend
- **Architecture**: Component-based with custom hooks for sensor monitoring
- **State Management**: React Context for tenant isolation and WebSocket connections
- **Styling**: TailwindCSS with responsive design
- **Real-time**: WebSocket connections for live sensor updates

### Database Patterns
- **Multi-tenancy**: Row Level Security (RLS) with tenant_id partitioning
- **Time-series**: TimescaleDB hypertables for sensor readings
- **Event Sourcing**: Immutable event store for audit trails
- **Migrations**: Alembic with careful attention to tenant isolation

## Critical Business Logic

### Sensor Monitoring
- **Silent Sensor Detection**: Different thresholds by sensor type (POS: 2min, Temperature: 10min, Door: 5min)
- **Alert Escalation**: Warning → Critical → Emergency based on silence duration
- **Recovery Detection**: Automatic alert resolution when sensors resume reporting

### Multi-Tenant Security
- **Tenant Isolation**: All database queries must include `tenant_id` filter
- **API Security**: Validate user belongs to requested tenant on every endpoint
- **Data Separation**: No cross-tenant data access allowed

### Offline Resilience
- **Local Buffer**: SQLite WAL mode for concurrent access, 4+ hours retention
- **Sync Strategy**: Compressed batch uploads with exponential backoff retry
- **Circuit Breaker**: Agent communication failures handled gracefully

## Common Commands

Since this is a documentation-only repository, there are no build/test commands. The actual implementation would typically use:

- **Python**: `poetry install`, `pytest`, `uvicorn`, `alembic upgrade head`
- **Go**: `go build`, `go test`, `go mod tidy`
- **React**: `npm install`, `npm run dev`, `npm run build`
- **Infrastructure**: `terraform plan/apply` for GCP resources

## Design Patterns

### Required Patterns
- **Event Sourcing**: All state changes stored as immutable events
- **CQRS**: Separate read/write models for performance
- **Circuit Breaker**: Resilient communication with remote agents
- **Repository Pattern**: Abstract data access with tenant security
- **Value Objects**: Sensor configurations and alert thresholds
- **Aggregate Pattern**: Sensor business logic encapsulation

### Anti-Patterns to Avoid
- Cross-tenant data queries without proper isolation
- Synchronous processing of sensor data (use async/events)
- Hard-coded sensor thresholds (use configuration)
- Direct database access without repository layer

## Sensor Types & Thresholds

### Critical Business Sensors
- **POS Terminals**: Alert after 2 minutes silence (business critical)
- **Power Monitoring**: Alert after 3 minutes (infrastructure critical)

### Environmental Sensors
- **Temperature**: Alert after 10 minutes (product safety)
- **Door Sensors**: Alert after 5 minutes (security)
- **Motion Sensors**: Alert after 15 minutes (occupancy)

## Development Focus Areas

When working on this system, prioritize:

1. **Tenant Isolation**: Every query, API endpoint, and data access must respect tenant boundaries
2. **Offline Resilience**: Components must work without internet connectivity
3. **Real-time Monitoring**: Sensor silence detection and alert generation
4. **Data Integrity**: Event sourcing ensures complete audit trails
5. **Performance**: Time-series data optimization for large-scale deployments

## System Constraints

- **Scale**: 100+ stores per tenant, 10+ sensors per store
- **Latency**: < 200ms API response times, 30s dashboard updates
- **Availability**: 99.9% uptime requirement
- **Data Retention**: 1 year sensor readings, permanent event store
- **Cost**: $300/month per tenant cloud budget