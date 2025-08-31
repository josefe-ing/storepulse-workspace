# Multi-Tenant Context Middleware
# StorePulse - Tenant isolation and context management

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from typing import Optional
import hashlib
import asyncio
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class TenantContextMiddleware:
    """
    Middleware para manejar contexto multi-tenant automáticamente.
    
    Funcionalidades:
    - Extrae tenant_id del API key
    - Configura Row Level Security en PostgreSQL
    - Valida límites por tenant
    - Cache de API keys para performance
    """
    
    def __init__(self):
        self.api_key_cache = {}  # Simple in-memory cache
        self.cache_ttl = 300  # 5 minutes
        
    async def __call__(self, request: Request, call_next):
        # Skip tenant context for health checks
        if request.url.path in ["/health", "/docs", "/openapi.json"]:
            return await call_next(request)
            
        try:
            # Extract and validate API key
            tenant_id, store_id = await self._extract_tenant_context(request)
            
            if not tenant_id:
                return JSONResponse(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    content={"detail": "Invalid or missing API key"}
                )
            
            # Set request context
            request.state.tenant_id = tenant_id
            request.state.store_id = store_id
            
            # Set database tenant context for RLS
            await self._set_database_context(tenant_id)
            
            # Validate tenant limits (async, don't block request)
            asyncio.create_task(self._validate_tenant_limits(tenant_id))
            
            response = await call_next(request)
            
            # Log tenant activity
            await self._log_tenant_activity(tenant_id, store_id, request)
            
            return response
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Tenant middleware error: {e}")
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={"detail": "Internal server error"}
            )
    
    async def _extract_tenant_context(self, request: Request) -> tuple[Optional[str], Optional[str]]:
        """Extract tenant_id and store_id from API key"""
        
        # Get API key from Authorization header
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None, None
            
        api_key = auth_header.replace("Bearer ", "")
        if not api_key:
            return None, None
        
        # Check cache first
        cache_key = hashlib.sha256(api_key.encode()).hexdigest()
        cached_result = self.api_key_cache.get(cache_key)
        
        if cached_result and cached_result['expires'] > datetime.utcnow():
            return cached_result['tenant_id'], cached_result['store_id']
        
        # Database lookup
        tenant_id, store_id = await self._lookup_api_key(api_key)
        
        # Cache result
        if tenant_id:
            self.api_key_cache[cache_key] = {
                'tenant_id': tenant_id,
                'store_id': store_id,
                'expires': datetime.utcnow() + timedelta(seconds=self.cache_ttl)
            }
        
        return tenant_id, store_id
    
    async def _lookup_api_key(self, api_key: str) -> tuple[Optional[str], Optional[str]]:
        """Lookup API key in database"""
        from .database import get_database
        
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        async with get_database() as db:
            query = text("""
                SELECT k.tenant_id, k.store_id 
                FROM store_api_keys k
                JOIN tenants t ON k.tenant_id = t.tenant_id
                WHERE k.key_hash = :key_hash 
                AND k.is_active = TRUE 
                AND t.is_active = TRUE
            """)
            
            result = await db.execute(query, {"key_hash": key_hash})
            row = result.fetchone()
            
            if row:
                # Update last_used_at
                await db.execute(
                    text("UPDATE store_api_keys SET last_used_at = NOW() WHERE key_hash = :key_hash"),
                    {"key_hash": key_hash}
                )
                await db.commit()
                
                return row.tenant_id, row.store_id
            
            return None, None
    
    async def _set_database_context(self, tenant_id: str):
        """Set tenant context for Row Level Security"""
        from .database import get_database
        
        async with get_database() as db:
            await db.execute(text(f"SET app.tenant_id = '{tenant_id}'"))
    
    async def _validate_tenant_limits(self, tenant_id: str):
        """Validate tenant limits (async - don't block request)"""
        try:
            from .services.tenant_service import TenantLimitsService
            
            limits_service = TenantLimitsService()
            
            # Check store count limit
            await limits_service.validate_store_limit(tenant_id)
            
            # Check cost limit (hourly check)
            current_hour = datetime.utcnow().hour
            if current_hour % 4 == 0:  # Check every 4 hours
                await limits_service.check_cost_limit(tenant_id)
                
        except Exception as e:
            logger.warning(f"Tenant limits validation failed for {tenant_id}: {e}")
    
    async def _log_tenant_activity(self, tenant_id: str, store_id: str, request: Request):
        """Log tenant activity for analytics"""
        logger.info(f"Tenant activity", extra={
            "tenant_id": tenant_id,
            "store_id": store_id,
            "method": request.method,
            "path": request.url.path,
            "timestamp": datetime.utcnow().isoformat()
        })


class TenantLimitsService:
    """Service for validating tenant limits and quotas"""
    
    async def validate_store_limit(self, tenant_id: str):
        """Validate that tenant hasn't exceeded store limit"""
        from .database import get_database
        
        async with get_database() as db:
            # Get tenant limits
            tenant_query = text("""
                SELECT max_stores, max_monthly_cost 
                FROM tenants 
                WHERE tenant_id = :tenant_id AND is_active = TRUE
            """)
            tenant_result = await db.execute(tenant_query, {"tenant_id": tenant_id})
            tenant = tenant_result.fetchone()
            
            if not tenant:
                raise HTTPException(404, f"Tenant {tenant_id} not found or inactive")
            
            # Count active stores
            stores_query = text("""
                SELECT COUNT(*) as store_count 
                FROM stores 
                WHERE tenant_id = :tenant_id AND is_active = TRUE
            """)
            stores_result = await db.execute(stores_query, {"tenant_id": tenant_id})
            store_count = stores_result.fetchone().store_count
            
            if store_count >= tenant.max_stores:
                logger.warning(f"Store limit exceeded for tenant {tenant_id}: {store_count}/{tenant.max_stores}")
                raise HTTPException(429, f"Store limit exceeded: {store_count}/{tenant.max_stores}")
    
    async def check_cost_limit(self, tenant_id: str) -> float:
        """Check if tenant is approaching cost limits"""
        # TODO: Integrate with GCP Billing API
        # For now, return estimated cost based on usage
        
        estimated_monthly_cost = await self._estimate_monthly_cost(tenant_id)
        
        from .database import get_database
        async with get_database() as db:
            tenant_query = text("""
                SELECT max_monthly_cost, billing_email 
                FROM tenants 
                WHERE tenant_id = :tenant_id
            """)
            result = await db.execute(tenant_query, {"tenant_id": tenant_id})
            tenant = result.fetchone()
            
            if estimated_monthly_cost > tenant.max_monthly_cost * 0.8:  # 80% threshold
                await self._send_cost_alert(tenant_id, estimated_monthly_cost, tenant.billing_email)
            
            return estimated_monthly_cost
    
    async def _estimate_monthly_cost(self, tenant_id: str) -> float:
        """Estimate monthly cost based on current usage"""
        from .database import get_database
        
        async with get_database() as db:
            # Count events in last 7 days to project monthly
            query = text("""
                SELECT COUNT(*) as event_count
                FROM metrics 
                WHERE tenant_id = :tenant_id 
                AND created_at > NOW() - INTERVAL '7 days'
            """)
            result = await db.execute(query, {"tenant_id": tenant_id})
            weekly_events = result.fetchone().event_count
            
            # Simple cost estimation (events * cost_per_event * 4 weeks)
            monthly_events = weekly_events * 4
            estimated_cost = self._calculate_gcp_costs(monthly_events)
            
            return estimated_cost
    
    def _calculate_gcp_costs(self, monthly_events: int) -> float:
        """Calculate estimated GCP costs based on events"""
        # Simplified cost model
        base_cost = 60  # Cloud Run always-warm
        db_cost = 68    # Cloud SQL
        
        # Variable costs
        function_cost = (monthly_events / 1000) * 0.02  # Cloud Functions
        pubsub_cost = (monthly_events / 1000000) * 40   # Pub/Sub
        
        return base_cost + db_cost + function_cost + pubsub_cost
    
    async def _send_cost_alert(self, tenant_id: str, estimated_cost: float, billing_email: str):
        """Send cost alert to tenant"""
        logger.warning(f"Cost alert for tenant {tenant_id}: ${estimated_cost:.2f}")
        
        # TODO: Implement email/WhatsApp notification
        # For now, just log
        pass


# FastAPI integration
def get_tenant_id(request: Request) -> str:
    """Dependency to get current tenant_id"""
    if not hasattr(request.state, 'tenant_id'):
        raise HTTPException(401, "No tenant context available")
    return request.state.tenant_id

def get_store_id(request: Request) -> str:
    """Dependency to get current store_id"""
    if not hasattr(request.state, 'store_id'):
        raise HTTPException(401, "No store context available")
    return request.state.store_id