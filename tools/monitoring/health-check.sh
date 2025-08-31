#!/bin/bash
# StorePulse Health Check Script
# Validates all services are running correctly

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
API_URL="http://localhost:8080"
GATEWAY_URL="http://localhost:8081"
CLIENT_DASHBOARD_URL="http://localhost:3000"
ADMIN_DASHBOARD_URL="http://localhost:3001"
PROMETHEUS_URL="http://localhost:9090"
GRAFANA_URL="http://localhost:3010"

echo -e "${YELLOW}StorePulse Health Check${NC}"
echo "======================"
echo ""

# Function to check HTTP endpoint
check_http() {
    local name=$1
    local url=$2
    local expected_status=${3:-200}
    
    echo -n "Checking $name... "
    
    if response=$(curl -s -w "%{http_code}" -o /dev/null "$url" 2>/dev/null); then
        if [ "$response" -eq "$expected_status" ]; then
            echo -e "${GREEN}✓ OK ($response)${NC}"
            return 0
        else
            echo -e "${RED}✗ FAIL (HTTP $response)${NC}"
            return 1
        fi
    else
        echo -e "${RED}✗ FAIL (Connection refused)${NC}"
        return 1
    fi
}

# Function to check database connection
check_database() {
    echo -n "Checking PostgreSQL... "
    
    if docker-compose exec -T postgres pg_isready -U storepulse -d storepulse_dev > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        return 1
    fi
}

# Function to check Redis
check_redis() {
    echo -n "Checking Redis... "
    
    if docker-compose exec -T redis redis-cli ping > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        return 1
    fi
}

# Function to check Pub/Sub emulator
check_pubsub() {
    echo -n "Checking Pub/Sub Emulator... "
    
    if curl -s "http://localhost:8085" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        return 1
    fi
}

# Function to check Docker services
check_docker_services() {
    echo "Docker Services:"
    echo "=================="
    
    local services=(
        "storepulse-db"
        "storepulse-redis"
        "storepulse-api"
        "storepulse-gateway"
        "storepulse-functions"
        "storepulse-client-dashboard"
        "storepulse-admin-dashboard"
        "storepulse-pubsub"
    )
    
    local all_healthy=true
    
    for service in "${services[@]}"; do
        echo -n "  $service... "
        
        if docker ps --filter "name=$service" --filter "status=running" --format "{{.Names}}" | grep -q "$service"; then
            echo -e "${GREEN}✓ Running${NC}"
        else
            echo -e "${RED}✗ Not running${NC}"
            all_healthy=false
        fi
    done
    
    if [ "$all_healthy" = true ]; then
        return 0
    else
        return 1
    fi
}

# Function to test API endpoints
test_api_endpoints() {
    echo ""
    echo "API Endpoints:"
    echo "=============="
    
    local endpoints=(
        "GET $API_URL/health"
        "GET $API_URL/docs"
        "GET $GATEWAY_URL/health"
    )
    
    local all_healthy=true
    
    for endpoint in "${endpoints[@]}"; do
        local method=$(echo $endpoint | cut -d' ' -f1)
        local url=$(echo $endpoint | cut -d' ' -f2)
        
        echo -n "  $method $(basename $url)... "
        
        if [ "$method" = "GET" ]; then
            if curl -s -f "$url" > /dev/null 2>&1; then
                echo -e "${GREEN}✓ OK${NC}"
            else
                echo -e "${RED}✗ FAIL${NC}"
                all_healthy=false
            fi
        fi
    done
    
    if [ "$all_healthy" = true ]; then
        return 0
    else
        return 1
    fi
}

# Function to check service dependencies
check_dependencies() {
    echo ""
    echo "Service Dependencies:"
    echo "====================="
    
    local deps_healthy=true
    
    # Database
    if ! check_database; then
        deps_healthy=false
    fi
    
    # Redis
    if ! check_redis; then
        deps_healthy=false
    fi
    
    # Pub/Sub Emulator
    if ! check_pubsub; then
        deps_healthy=false
    fi
    
    if [ "$deps_healthy" = true ]; then
        return 0
    else
        return 1
    fi
}

# Function to check web interfaces
check_web_interfaces() {
    echo ""
    echo "Web Interfaces:"
    echo "==============="
    
    local web_healthy=true
    
    # Client Dashboard
    if ! check_http "Client Dashboard" "$CLIENT_DASHBOARD_URL"; then
        web_healthy=false
    fi
    
    # Admin Dashboard
    if ! check_http "Admin Dashboard" "$ADMIN_DASHBOARD_URL"; then
        web_healthy=false
    fi
    
    # Prometheus (optional)
    if docker ps --filter "name=storepulse-prometheus" --filter "status=running" --format "{{.Names}}" | grep -q "storepulse-prometheus"; then
        if ! check_http "Prometheus" "$PROMETHEUS_URL"; then
            web_healthy=false
        fi
    else
        echo "Prometheus... ${YELLOW}⚠ Not running (optional)${NC}"
    fi
    
    # Grafana (optional)
    if docker ps --filter "name=storepulse-grafana" --filter "status=running" --format "{{.Names}}" | grep -q "storepulse-grafana"; then
        if ! check_http "Grafana" "$GRAFANA_URL"; then
            web_healthy=false
        fi
    else
        echo "Grafana... ${YELLOW}⚠ Not running (optional)${NC}"
    fi
    
    if [ "$web_healthy" = true ]; then
        return 0
    else
        return 1
    fi
}

# Function to show service URLs
show_urls() {
    echo ""
    echo "Service URLs:"
    echo "============="
    echo "API Documentation: $API_URL/docs"
    echo "Gateway Health: $GATEWAY_URL/health"
    echo "Client Dashboard: $CLIENT_DASHBOARD_URL"
    echo "Admin Dashboard: $ADMIN_DASHBOARD_URL"
    
    if docker ps --filter "name=storepulse-prometheus" --filter "status=running" --format "{{.Names}}" | grep -q "storepulse-prometheus"; then
        echo "Prometheus: $PROMETHEUS_URL"
    fi
    
    if docker ps --filter "name=storepulse-grafana" --filter "status=running" --format "{{.Names}}" | grep -q "storepulse-grafana"; then
        echo "Grafana: $GRAFANA_URL (admin/admin)"
    fi
}

# Main health check
main() {
    local overall_healthy=true
    
    # Check Docker services
    echo ""
    if ! check_docker_services; then
        overall_healthy=false
    fi
    
    # Check dependencies
    if ! check_dependencies; then
        overall_healthy=false
    fi
    
    # Test API endpoints
    if ! test_api_endpoints; then
        overall_healthy=false
    fi
    
    # Check web interfaces
    if ! check_web_interfaces; then
        overall_healthy=false
    fi
    
    # Show results
    echo ""
    echo "Overall Status:"
    echo "==============="
    
    if [ "$overall_healthy" = true ]; then
        echo -e "${GREEN}✓ All systems operational!${NC}"
        show_urls
        exit 0
    else
        echo -e "${RED}✗ Some services are unhealthy${NC}"
        echo ""
        echo "Troubleshooting:"
        echo "- Check logs: docker-compose logs -f"
        echo "- Restart services: make restart"
        echo "- Reset environment: make reset"
        exit 1
    fi
}

# Check if docker-compose is available
if ! command -v docker-compose &> /dev/null; then
    echo -e "${RED}Error: docker-compose is required but not installed${NC}"
    exit 1
fi

# Run health check
main "$@"