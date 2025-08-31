# StorePulse Development Makefile
# Streamlined commands for monorepo development

.PHONY: help setup build test clean deploy

# Configuration
PROJECT_ID ?= storepulse-prod
REGION ?= us-central1
REGISTRY ?= gcr.io

# Colors for output
GREEN = \033[32m
YELLOW = \033[33m
RED = \033[31m
NC = \033[0m # No Color

help: ## Show this help message
	@echo "$(GREEN)StorePulse Development Commands$(NC)"
	@echo "=================================="
	@awk 'BEGIN {FS = ":.*##"; printf "\n"} /^[a-zA-Z_-]+:.*?##/ { printf "  $(GREEN)%-15s$(NC) %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

##@ Development
setup: ## Setup development environment
	@echo "$(YELLOW)Setting up StorePulse development environment...$(NC)"
	@chmod +x tools/setup-dev.sh
	@./tools/setup-dev.sh

build: ## Build all services
	@echo "$(YELLOW)Building all services...$(NC)"
	docker-compose build

up: ## Start all services
	@echo "$(YELLOW)Starting all services...$(NC)"
	docker-compose up -d

down: ## Stop all services
	@echo "$(YELLOW)Stopping all services...$(NC)"
	docker-compose down

logs: ## View logs from all services
	docker-compose logs -f

restart: down up ## Restart all services

##@ Testing
test: ## Run all tests
	@echo "$(YELLOW)Running all tests...$(NC)"
	@$(MAKE) test-api
	@$(MAKE) test-gateway
	@$(MAKE) test-pos-agent
	@$(MAKE) test-functions

test-api: ## Test API service
	@echo "$(YELLOW)Testing API service...$(NC)"
	cd services/api && python -m pytest tests/ -v --cov=. --cov-report=term-missing

test-gateway: ## Test Gateway service
	@echo "$(YELLOW)Testing Gateway service...$(NC)"
	cd services/gateway && python -m pytest tests/ -v --cov=. --cov-report=term-missing

test-pos-agent: ## Test POS Agent
	@echo "$(YELLOW)Testing POS Agent...$(NC)"
	cd services/pos-agent && go test ./... -v -coverprofile=coverage.out

test-functions: ## Test Cloud Functions
	@echo "$(YELLOW)Testing Cloud Functions...$(NC)"
	cd services/functions && python -m pytest tests/ -v --cov=. --cov-report=term-missing

test-integration: ## Run integration tests
	@echo "$(YELLOW)Running integration tests...$(NC)"
	cd tests/integration && python -m pytest . -v

test-e2e: ## Run end-to-end tests
	@echo "$(YELLOW)Running E2E tests...$(NC)"
	cd tests/e2e && npm run test

##@ Code Quality
lint: ## Run linting on all services
	@echo "$(YELLOW)Linting all services...$(NC)"
	@$(MAKE) lint-python
	@$(MAKE) lint-go
	@$(MAKE) lint-js

lint-python: ## Lint Python services
	cd services/api && flake8 . && black --check . && isort --check-only .
	cd services/gateway && flake8 . && black --check . && isort --check-only .
	cd services/functions && flake8 . && black --check . && isort --check-only .

lint-go: ## Lint Go services
	cd services/pos-agent && go fmt ./... && go vet ./...

lint-js: ## Lint JavaScript services
	cd frontend/client-dashboard && npm run lint
	cd frontend/admin-dashboard && npm run lint

format: ## Format all code
	@echo "$(YELLOW)Formatting all code...$(NC)"
	cd services/api && black . && isort .
	cd services/gateway && black . && isort .
	cd services/functions && black . && isort .
	cd services/pos-agent && go fmt ./...
	cd frontend/client-dashboard && npm run format
	cd frontend/admin-dashboard && npm run format

##@ Build
build-api: ## Build API service image
	@echo "$(YELLOW)Building API service...$(NC)"
	docker build -t $(REGISTRY)/$(PROJECT_ID)/storepulse-api:latest services/api/

build-gateway: ## Build Gateway service image
	@echo "$(YELLOW)Building Gateway service...$(NC)"
	docker build -t $(REGISTRY)/$(PROJECT_ID)/storepulse-gateway:latest services/gateway/

build-pos-agent: ## Build POS Agent binaries
	@echo "$(YELLOW)Building POS Agent...$(NC)"
	cd services/pos-agent && make build

build-dashboards: ## Build dashboard applications
	@echo "$(YELLOW)Building dashboards...$(NC)"
	cd frontend/client-dashboard && npm run build
	cd frontend/admin-dashboard && npm run build

##@ Database
db-setup: ## Setup development database
	@echo "$(YELLOW)Setting up database...$(NC)"
	docker-compose up -d postgres
	sleep 5
	cd services/api && alembic upgrade head

db-migration: ## Create new database migration
	@echo "$(YELLOW)Creating database migration...$(NC)"
	@read -p "Migration name: " name; \
	cd services/api && alembic revision --autogenerate -m "$$name"

db-upgrade: ## Apply database migrations
	@echo "$(YELLOW)Applying database migrations...$(NC)"
	cd services/api && alembic upgrade head

db-reset: ## Reset development database
	@echo "$(YELLOW)Resetting database...$(NC)"
	docker-compose down postgres
	docker volume rm storepulse-workspace_postgres_data 2>/dev/null || true
	@$(MAKE) db-setup

##@ Deployment
deploy-dev: ## Deploy to development environment
	@echo "$(YELLOW)Deploying to development...$(NC)"
	./tools/deployment/deploy-dev.sh

deploy-staging: ## Deploy to staging environment
	@echo "$(YELLOW)Deploying to staging...$(NC)"
	./tools/deployment/deploy-staging.sh

deploy-prod: ## Deploy to production environment
	@echo "$(YELLOW)Deploying to production...$(NC)"
	@echo "$(RED)This will deploy to production. Are you sure? [y/N]$(NC)"
	@read -r CONFIRM; \
	if [ "$$CONFIRM" = "y" ] || [ "$$CONFIRM" = "Y" ]; then \
		./tools/deployment/deploy-production.sh; \
	else \
		echo "Deployment cancelled."; \
	fi

##@ Infrastructure
infra-plan: ## Plan infrastructure changes
	@echo "$(YELLOW)Planning infrastructure changes...$(NC)"
	cd infrastructure/terraform && terraform plan

infra-apply: ## Apply infrastructure changes
	@echo "$(YELLOW)Applying infrastructure changes...$(NC)"
	cd infrastructure/terraform && terraform apply

infra-destroy: ## Destroy infrastructure (BE CAREFUL!)
	@echo "$(RED)This will destroy ALL infrastructure. Are you sure? [y/N]$(NC)"
	@read -r CONFIRM; \
	if [ "$$CONFIRM" = "y" ] || [ "$$CONFIRM" = "Y" ]; then \
		cd infrastructure/terraform && terraform destroy; \
	else \
		echo "Destruction cancelled."; \
	fi

##@ Monitoring
health: ## Check health of all services
	@echo "$(YELLOW)Checking service health...$(NC)"
	@./tools/monitoring/health-check.sh

logs-api: ## View API service logs
	docker-compose logs -f api

logs-gateway: ## View Gateway service logs
	docker-compose logs -f gateway

metrics: ## Open monitoring dashboards
	@echo "$(YELLOW)Opening monitoring dashboards...$(NC)"
	@echo "Prometheus: http://localhost:9090"
	@echo "Grafana: http://localhost:3010 (admin/admin)"
	@if command -v open >/dev/null; then open http://localhost:3010; fi

##@ Tenant Management
onboard-tenant: ## Onboard new tenant
	@echo "$(YELLOW)Onboarding new tenant...$(NC)"
	@read -p "Tenant ID: " tenant_id; \
	read -p "Company Name: " company; \
	read -p "Number of stores: " stores; \
	read -p "Email: " email; \
	read -p "Admin contact: " admin; \
	python tools/onboarding/onboard_tenant.py \
		--tenant-id "$$tenant_id" \
		--company "$$company" \
		--stores "$$stores" \
		--email "$$email" \
		--admin "$$admin"

##@ Utilities
clean: ## Clean up development environment
	@echo "$(YELLOW)Cleaning up...$(NC)"
	docker-compose down
	docker system prune -f
	docker volume prune -f

reset: clean setup ## Reset entire development environment

install-deps: ## Install all dependencies
	@echo "$(YELLOW)Installing dependencies...$(NC)"
	cd services/api && pip install -r requirements.txt
	cd services/gateway && pip install -r requirements.txt
	cd services/functions && pip install -r requirements.txt
	cd services/pos-agent && go mod download
	cd frontend/client-dashboard && npm install
	cd frontend/admin-dashboard && npm install

security-scan: ## Run security scans
	@echo "$(YELLOW)Running security scans...$(NC)"
	@if command -v trivy >/dev/null; then \
		trivy fs . --severity HIGH,CRITICAL; \
	else \
		echo "$(RED)Trivy not installed. Install with: brew install trivy$(NC)"; \
	fi

##@ Documentation
docs-serve: ## Serve documentation locally
	@echo "$(YELLOW)Serving documentation...$(NC)"
	mkdocs serve

docs-build: ## Build documentation
	@echo "$(YELLOW)Building documentation...$(NC)"
	mkdocs build

##@ Default
all: setup build test ## Setup, build, and test everything