# Tenant Management API
# StorePulse - CRUD operations for tenant and store management

from fastapi import APIRouter, HTTPException, Depends, status
from pydantic import BaseModel, EmailStr
from sqlalchemy import text
from typing import List, Optional
from datetime import datetime
import secrets
import hashlib
import logging

from .tenant_middleware import get_tenant_id
from .database import get_database

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/admin/tenants", tags=["Tenant Management"])

# Pydantic models
class TenantCreate(BaseModel):
    tenant_id: str
    company_name: str
    plan_type: str = "basic"
    max_stores: int = 30
    max_monthly_cost: float = 265.00
    billing_email: EmailStr
    admin_contact: str
    whatsapp_numbers: List[str] = []
    config: dict = {}

class TenantResponse(BaseModel):
    tenant_id: str
    company_name: str
    plan_type: str
    max_stores: int
    max_monthly_cost: float
    created_at: datetime
    is_active: bool
    billing_email: str
    admin_contact: str
    whatsapp_numbers: List[str]
    config: dict

class StoreCreate(BaseModel):
    store_id: str
    store_name: str
    config: dict = {}

class StoreResponse(BaseModel):
    tenant_id: str
    store_id: str
    store_name: str
    config: dict
    created_at: datetime
    is_active: bool

class APIKeyResponse(BaseModel):
    key_id: str
    tenant_id: str
    store_id: str
    api_key: str  # Only shown on creation
    created_at: datetime
    is_active: bool

# Tenant CRUD operations
@router.post("/", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
async def create_tenant(tenant: TenantCreate):
    """Create a new tenant (client)"""
    
    async with get_database() as db:
        # Check if tenant_id already exists
        check_query = text("SELECT tenant_id FROM tenants WHERE tenant_id = :tenant_id")
        result = await db.execute(check_query, {"tenant_id": tenant.tenant_id})
        
        if result.fetchone():
            raise HTTPException(409, f"Tenant {tenant.tenant_id} already exists")
        
        # Insert new tenant
        insert_query = text("""
            INSERT INTO tenants (
                tenant_id, company_name, plan_type, max_stores, max_monthly_cost,
                billing_email, admin_contact, whatsapp_numbers, config
            ) VALUES (
                :tenant_id, :company_name, :plan_type, :max_stores, :max_monthly_cost,
                :billing_email, :admin_contact, :whatsapp_numbers, :config
            )
        """)
        
        await db.execute(insert_query, {
            "tenant_id": tenant.tenant_id,
            "company_name": tenant.company_name,
            "plan_type": tenant.plan_type,
            "max_stores": tenant.max_stores,
            "max_monthly_cost": tenant.max_monthly_cost,
            "billing_email": tenant.billing_email,
            "admin_contact": tenant.admin_contact,
            "whatsapp_numbers": tenant.whatsapp_numbers,
            "config": tenant.config
        })
        
        await db.commit()
        
        logger.info(f"Created new tenant: {tenant.tenant_id} ({tenant.company_name})")
        
        # Return created tenant
        return await get_tenant(tenant.tenant_id)

@router.get("/", response_model=List[TenantResponse])
async def list_tenants(active_only: bool = True):
    """List all tenants"""
    
    async with get_database() as db:
        query = text("""
            SELECT tenant_id, company_name, plan_type, max_stores, max_monthly_cost,
                   created_at, is_active, billing_email, admin_contact, whatsapp_numbers, config
            FROM tenants
            WHERE (:active_only = FALSE OR is_active = TRUE)
            ORDER BY created_at DESC
        """)
        
        result = await db.execute(query, {"active_only": active_only})
        tenants = result.fetchall()
        
        return [TenantResponse(**dict(tenant)) for tenant in tenants]

@router.get("/{tenant_id}", response_model=TenantResponse)
async def get_tenant(tenant_id: str):
    """Get tenant details"""
    
    async with get_database() as db:
        query = text("""
            SELECT tenant_id, company_name, plan_type, max_stores, max_monthly_cost,
                   created_at, is_active, billing_email, admin_contact, whatsapp_numbers, config
            FROM tenants
            WHERE tenant_id = :tenant_id
        """)
        
        result = await db.execute(query, {"tenant_id": tenant_id})
        tenant = result.fetchone()
        
        if not tenant:
            raise HTTPException(404, f"Tenant {tenant_id} not found")
        
        return TenantResponse(**dict(tenant))

@router.put("/{tenant_id}", response_model=TenantResponse)
async def update_tenant(tenant_id: str, updates: dict):
    """Update tenant configuration"""
    
    if not updates:
        raise HTTPException(400, "No updates provided")
    
    # Build dynamic update query
    set_clauses = []
    params = {"tenant_id": tenant_id}
    
    allowed_fields = {
        "company_name", "plan_type", "max_stores", "max_monthly_cost",
        "billing_email", "admin_contact", "whatsapp_numbers", "config", "is_active"
    }
    
    for field, value in updates.items():
        if field in allowed_fields:
            set_clauses.append(f"{field} = :{field}")
            params[field] = value
    
    if not set_clauses:
        raise HTTPException(400, "No valid fields to update")
    
    async with get_database() as db:
        query = text(f"""
            UPDATE tenants 
            SET {', '.join(set_clauses)}
            WHERE tenant_id = :tenant_id
            RETURNING tenant_id
        """)
        
        result = await db.execute(query, params)
        updated = result.fetchone()
        
        if not updated:
            raise HTTPException(404, f"Tenant {tenant_id} not found")
        
        await db.commit()
        
        logger.info(f"Updated tenant {tenant_id}: {list(updates.keys())}")
        
        return await get_tenant(tenant_id)

# Store management
@router.post("/{tenant_id}/stores", response_model=StoreResponse, status_code=status.HTTP_201_CREATED)
async def create_store(tenant_id: str, store: StoreCreate):
    """Create a new store for tenant"""
    
    async with get_database() as db:
        # Verify tenant exists and check store limit
        tenant_query = text("SELECT max_stores FROM tenants WHERE tenant_id = :tenant_id AND is_active = TRUE")
        tenant_result = await db.execute(tenant_query, {"tenant_id": tenant_id})
        tenant_data = tenant_result.fetchone()
        
        if not tenant_data:
            raise HTTPException(404, f"Tenant {tenant_id} not found or inactive")
        
        # Count existing stores
        count_query = text("SELECT COUNT(*) as count FROM stores WHERE tenant_id = :tenant_id AND is_active = TRUE")
        count_result = await db.execute(count_query, {"tenant_id": tenant_id})
        store_count = count_result.fetchone().count
        
        if store_count >= tenant_data.max_stores:
            raise HTTPException(409, f"Store limit reached: {store_count}/{tenant_data.max_stores}")
        
        # Check if store_id already exists for this tenant
        check_query = text("SELECT store_id FROM stores WHERE tenant_id = :tenant_id AND store_id = :store_id")
        check_result = await db.execute(check_query, {"tenant_id": tenant_id, "store_id": store.store_id})
        
        if check_result.fetchone():
            raise HTTPException(409, f"Store {store.store_id} already exists for tenant {tenant_id}")
        
        # Insert new store
        insert_query = text("""
            INSERT INTO stores (tenant_id, store_id, store_name, config)
            VALUES (:tenant_id, :store_id, :store_name, :config)
        """)
        
        await db.execute(insert_query, {
            "tenant_id": tenant_id,
            "store_id": store.store_id,
            "store_name": store.store_name,
            "config": store.config
        })
        
        await db.commit()
        
        logger.info(f"Created store {store.store_id} for tenant {tenant_id}")
        
        return await get_store(tenant_id, store.store_id)

@router.get("/{tenant_id}/stores", response_model=List[StoreResponse])
async def list_tenant_stores(tenant_id: str):
    """List all stores for a tenant"""
    
    async with get_database() as db:
        query = text("""
            SELECT tenant_id, store_id, store_name, config, created_at, is_active
            FROM stores
            WHERE tenant_id = :tenant_id
            ORDER BY created_at DESC
        """)
        
        result = await db.execute(query, {"tenant_id": tenant_id})
        stores = result.fetchall()
        
        return [StoreResponse(**dict(store)) for store in stores]

@router.get("/{tenant_id}/stores/{store_id}", response_model=StoreResponse)
async def get_store(tenant_id: str, store_id: str):
    """Get store details"""
    
    async with get_database() as db:
        query = text("""
            SELECT tenant_id, store_id, store_name, config, created_at, is_active
            FROM stores
            WHERE tenant_id = :tenant_id AND store_id = :store_id
        """)
        
        result = await db.execute(query, {"tenant_id": tenant_id, "store_id": store_id})
        store = result.fetchone()
        
        if not store:
            raise HTTPException(404, f"Store {store_id} not found for tenant {tenant_id}")
        
        return StoreResponse(**dict(store))

# API Key management
@router.post("/{tenant_id}/stores/{store_id}/api-key", response_model=APIKeyResponse, status_code=status.HTTP_201_CREATED)
async def generate_api_key(tenant_id: str, store_id: str):
    """Generate new API key for store"""
    
    async with get_database() as db:
        # Verify store exists
        store_query = text("SELECT store_id FROM stores WHERE tenant_id = :tenant_id AND store_id = :store_id AND is_active = TRUE")
        store_result = await db.execute(store_query, {"tenant_id": tenant_id, "store_id": store_id})
        
        if not store_result.fetchone():
            raise HTTPException(404, f"Store {store_id} not found for tenant {tenant_id}")
        
        # Deactivate existing API keys for this store
        deactivate_query = text("""
            UPDATE store_api_keys 
            SET is_active = FALSE 
            WHERE tenant_id = :tenant_id AND store_id = :store_id
        """)
        await db.execute(deactivate_query, {"tenant_id": tenant_id, "store_id": store_id})
        
        # Generate new API key
        api_key = f"store_{tenant_id}_{store_id}_{secrets.token_urlsafe(32)}"
        key_id = f"store_{tenant_id}_{store_id}"
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        # Insert new API key
        insert_query = text("""
            INSERT INTO store_api_keys (key_id, tenant_id, store_id, key_hash)
            VALUES (:key_id, :tenant_id, :store_id, :key_hash)
        """)
        
        await db.execute(insert_query, {
            "key_id": key_id,
            "tenant_id": tenant_id,
            "store_id": store_id,
            "key_hash": key_hash
        })
        
        await db.commit()
        
        logger.info(f"Generated new API key for {tenant_id}/{store_id}")
        
        return APIKeyResponse(
            key_id=key_id,
            tenant_id=tenant_id,
            store_id=store_id,
            api_key=api_key,  # Only shown on creation
            created_at=datetime.utcnow(),
            is_active=True
        )

@router.get("/{tenant_id}/api-keys")
async def list_api_keys(tenant_id: str):
    """List API keys for tenant (without showing actual keys)"""
    
    async with get_database() as db:
        query = text("""
            SELECT key_id, tenant_id, store_id, created_at, last_used_at, is_active
            FROM store_api_keys
            WHERE tenant_id = :tenant_id
            ORDER BY created_at DESC
        """)
        
        result = await db.execute(query, {"tenant_id": tenant_id})
        keys = result.fetchall()
        
        return [
            {
                "key_id": key.key_id,
                "tenant_id": key.tenant_id,
                "store_id": key.store_id,
                "created_at": key.created_at,
                "last_used_at": key.last_used_at,
                "is_active": key.is_active
            }
            for key in keys
        ]

@router.delete("/{tenant_id}/api-keys/{key_id}")
async def revoke_api_key(tenant_id: str, key_id: str):
    """Revoke API key"""
    
    async with get_database() as db:
        query = text("""
            UPDATE store_api_keys 
            SET is_active = FALSE 
            WHERE key_id = :key_id AND tenant_id = :tenant_id
            RETURNING key_id
        """)
        
        result = await db.execute(query, {"key_id": key_id, "tenant_id": tenant_id})
        updated = result.fetchone()
        
        if not updated:
            raise HTTPException(404, f"API key {key_id} not found for tenant {tenant_id}")
        
        await db.commit()
        
        logger.info(f"Revoked API key {key_id} for tenant {tenant_id}")
        
        return {"message": f"API key {key_id} revoked successfully"}


# Tenant statistics and usage
@router.get("/{tenant_id}/stats")
async def get_tenant_stats(tenant_id: str):
    """Get tenant usage statistics"""
    
    async with get_database() as db:
        # Store count
        stores_query = text("SELECT COUNT(*) as count FROM stores WHERE tenant_id = :tenant_id AND is_active = TRUE")
        stores_result = await db.execute(stores_query, {"tenant_id": tenant_id})
        store_count = stores_result.fetchone().count
        
        # Events in last 24 hours
        events_query = text("""
            SELECT COUNT(*) as count 
            FROM metrics 
            WHERE tenant_id = :tenant_id 
            AND created_at > NOW() - INTERVAL '24 hours'
        """)
        events_result = await db.execute(events_query, {"tenant_id": tenant_id})
        daily_events = events_result.fetchone().count
        
        # Active alerts
        alerts_query = text("""
            SELECT COUNT(*) as count 
            FROM alerts 
            WHERE tenant_id = :tenant_id 
            AND status = 'active'
        """)
        alerts_result = await db.execute(alerts_query, {"tenant_id": tenant_id})
        active_alerts = alerts_result.fetchone().count
        
        # Last activity
        activity_query = text("""
            SELECT MAX(created_at) as last_activity 
            FROM metrics 
            WHERE tenant_id = :tenant_id
        """)
        activity_result = await db.execute(activity_query, {"tenant_id": tenant_id})
        last_activity = activity_result.fetchone().last_activity
        
        return {
            "tenant_id": tenant_id,
            "store_count": store_count,
            "daily_events": daily_events,
            "active_alerts": active_alerts,
            "last_activity": last_activity,
            "projected_monthly_events": daily_events * 30 if daily_events else 0
        }