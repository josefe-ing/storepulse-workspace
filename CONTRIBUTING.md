# Contributing to StorePulse

Thank you for your interest in contributing to StorePulse! This document provides guidelines and information for contributors.

## 🚀 Getting Started

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Go 1.21+
- Node.js 18+
- Google Cloud CLI (for deployment)

### Development Setup
```bash
# Clone repository
git clone https://github.com/josefe-ing/storepulse-workspace.git
cd storepulse-workspace

# Setup development environment
make setup

# Start all services
make up

# Verify everything is working
make health
```

## 📋 Development Workflow

### 1. Create Feature Branch
```bash
git checkout -b feature/your-feature-name
# or
git checkout -b fix/bug-description
```

### 2. Make Changes
- Follow our [coding standards](docs/development/CODING-STANDARDS.md)
- Write tests for new functionality
- Update documentation as needed

### 3. Test Your Changes
```bash
# Run all tests
make test

# Run specific service tests
make test-api
make test-gateway
make test-pos-agent

# Check code quality
make lint
make format
```

### 4. Commit Changes
We use [Conventional Commits](https://www.conventionalcommits.org/):

```bash
# Feature
git commit -m "feat(api): add tenant usage analytics endpoint"

# Bug fix  
git commit -m "fix(gateway): resolve connection timeout issue"

# Documentation
git commit -m "docs: update deployment guide"

# Breaking change
git commit -m "feat(api)!: change authentication method to JWT only"
```

**Commit Types:**
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation only changes
- `style`: Changes that do not affect meaning (white-space, formatting)
- `refactor`: Code change that neither fixes bug nor adds feature
- `perf`: Performance improvements
- `test`: Adding missing tests
- `chore`: Changes to build process or auxiliary tools

### 5. Create Pull Request
- Use our [PR template](.github/pull_request_template.md)
- Include clear description of changes
- Reference related issues
- Ensure all CI checks pass

## 🏗️ Project Structure

### Monorepo Organization
```
services/          # Backend services
├── api/          # Cloud Run API (Python FastAPI)
├── gateway/      # Edge Gateway (Python FastAPI)
├── pos-agent/    # Windows POS Agent (Go)
└── functions/    # Cloud Functions (Python)

frontend/         # Frontend applications
├── client-dashboard/  # React client dashboard
└── admin-dashboard/   # React admin dashboard

infrastructure/   # Infrastructure as Code
├── terraform/    # GCP infrastructure
└── docker/       # Container configurations

tools/           # Operational tools
├── onboarding/  # Tenant onboarding
└── monitoring/  # Health checks
```

### Component Guidelines

#### API Service (`services/api/`)
- **Language**: Python 3.11 + FastAPI
- **Database**: PostgreSQL with SQLAlchemy
- **Authentication**: JWT + API Keys with multi-tenant isolation
- **Testing**: pytest with >80% coverage

#### Gateway Service (`services/gateway/`)
- **Language**: Python 3.11 + FastAPI
- **Storage**: SQLite for local buffering
- **Resilience**: 4+ hours offline operation
- **Sync**: Batch synchronization every 30 seconds

#### POS Agent (`services/pos-agent/`)
- **Language**: Go 1.21
- **Platform**: Windows (primary), Linux (secondary)
- **Deployment**: Single binary, Windows Service
- **Testing**: Go testing with race detection

#### Dashboards (`frontend/`)
- **Framework**: React 18 + TypeScript
- **Styling**: TailwindCSS (client), Material-UI (admin)
- **State**: Context API + React Query
- **Testing**: Jest + React Testing Library

## 🧪 Testing Guidelines

### Test Structure
```
tests/
├── unit/          # Unit tests (isolated components)
├── integration/   # Integration tests (service interactions)
├── e2e/          # End-to-end tests (full workflow)
└── load/         # Load testing (performance)
```

### Test Requirements
- **Unit Tests**: >80% coverage for all services
- **Integration Tests**: Critical user flows
- **E2E Tests**: Complete tenant onboarding workflow
- **Load Tests**: Support 30 stores, 19.5K events/hour

### Running Tests
```bash
# All tests
make test

# Specific service
make test-api
make test-gateway

# Integration tests
make test-integration

# Load tests
make test-load
```

## 📚 Documentation

### Documentation Types
- **API Documentation**: Auto-generated from OpenAPI specs
- **Architecture Docs**: High-level system design (`docs/architecture/`)
- **Business Docs**: Requirements and specifications (`docs/business/`)
- **Development Docs**: Guides and standards (`docs/development/`)

### Documentation Standards
- Use clear, concise language
- Include code examples where applicable
- Update documentation with code changes
- Use Mermaid diagrams for architecture

## 🔒 Security Guidelines

### Security Requirements
- **Authentication**: All endpoints must be authenticated
- **Authorization**: Implement proper role-based access
- **Input Validation**: Validate all user inputs
- **SQL Injection**: Use parameterized queries
- **XSS Protection**: Sanitize all outputs
- **Secrets**: Never commit secrets to repository

### Security Testing
```bash
# Security scan
make security-scan

# Dependency vulnerabilities
npm audit
go mod audit
pip audit
```

## 🚀 Deployment

### Environments
- **Development**: Local Docker Compose
- **Staging**: GCP with staging configuration
- **Production**: GCP with production configuration

### CI/CD Pipeline
Our CI/CD pipeline includes:
- **Path-based triggers**: Only build changed components
- **Parallel execution**: Independent service builds
- **Security scanning**: Vulnerability detection
- **Integration testing**: End-to-end validation
- **Automated deployment**: Zero-downtime deployments

## 📊 Performance Guidelines

### Performance Targets
- **API Latency**: <200ms (p95)
- **Gateway Sync**: <30 seconds
- **Dashboard Load**: <2 seconds
- **POS Agent Memory**: <10MB
- **Database Query**: <50ms

### Monitoring
- All services must expose health endpoints
- Use structured logging (JSON format)
- Include performance metrics
- Monitor resource usage

## 🤝 Code Review Process

### Review Checklist
- [ ] Code follows project standards
- [ ] Tests are included and passing
- [ ] Documentation is updated
- [ ] No security vulnerabilities
- [ ] Performance impact considered
- [ ] Backward compatibility maintained

### Review Timeline
- **Initial Review**: Within 24 hours
- **Follow-up**: Within 48 hours
- **Final Approval**: Within 72 hours

## 🏷️ Release Process

### Versioning
We use [Semantic Versioning](https://semver.org/):
- **Major**: Breaking changes (`v2.0.0`)
- **Minor**: New features (`v2.1.0`)
- **Patch**: Bug fixes (`v2.1.1`)

### Release Steps
1. Create release branch (`release/v2.1.0`)
2. Update version numbers
3. Update CHANGELOG.md
4. Create release PR
5. Deploy to staging
6. Run full test suite
7. Deploy to production
8. Create GitHub release with tags

## 💬 Community

### Communication Channels
- **Issues**: Bug reports and feature requests
- **Discussions**: General questions and ideas
- **Pull Requests**: Code contributions

### Getting Help
- Check existing [documentation](docs/)
- Search [existing issues](https://github.com/josefe-ing/storepulse-workspace/issues)
- Create new issue with detailed description

## 🙏 Recognition

Contributors will be recognized in:
- README.md contributors section
- Release notes
- Project documentation

Thank you for contributing to StorePulse! 🚀