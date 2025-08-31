# Multi-Tenant Authentication
# StorePulse - JWT and API Key authentication with tenant context

from fastapi import HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import text
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import jwt
import hashlib
import secrets
import logging

from .database import get_database
from .tenant_middleware import get_tenant_id

logger = logging.getLogger(__name__)

# Security scheme
security = HTTPBearer()

class AuthService:
    """Multi-tenant authentication service"""
    
    def __init__(self, jwt_secret: str, jwt_algorithm: str = "HS256"):
        self.jwt_secret = jwt_secret
        self.jwt_algorithm = jwt_algorithm
        self.access_token_expire_minutes = 60  # 1 hour
    
    # JWT Authentication (for dashboards)
    async def create_access_token(self, user_data: Dict) -> str:
        """Create JWT access token for dashboard users"""
        
        expire = datetime.utcnow() + timedelta(minutes=self.access_token_expire_minutes)
        
        payload = {
            "sub": user_data["user_id"],
            "tenant_id": user_data["tenant_id"],
            "user_type": user_data.get("user_type", "client"),
            "permissions": user_data.get("permissions", []),
            "exp": expire,
            "iat": datetime.utcnow(),
            "iss": "storepulse-auth"
        }
        
        token = jwt.encode(payload, self.jwt_secret, algorithm=self.jwt_algorithm)
        return token
    
    async def verify_access_token(self, token: str) -> Dict:
        """Verify and decode JWT access token"""
        
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Check if token is expired
            if datetime.utcnow() > datetime.fromtimestamp(payload["exp"]):
                raise HTTPException(401, "Token expired")
            
            # Verify tenant still exists and is active
            tenant_id = payload.get("tenant_id")
            if tenant_id and not await self._verify_tenant_active(tenant_id):
                raise HTTPException(401, "Tenant inactive or not found")
            
            return payload
            
        except jwt.InvalidTokenError as e:
            raise HTTPException(401, f"Invalid token: {str(e)}")
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            raise HTTPException(401, "Token verification failed")
    
    # API Key Authentication (for gateways)
    async def verify_api_key(self, api_key: str) -> Dict:
        """Verify API key and return tenant/store context"""
        
        if not api_key:
            raise HTTPException(401, "API key required")
        
        # Hash the key for database lookup
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        
        async with get_database() as db:
            query = text("""
                SELECT 
                    k.tenant_id, k.store_id, k.key_id,
                    t.company_name, t.is_active as tenant_active,
                    s.store_name, s.is_active as store_active
                FROM store_api_keys k
                JOIN tenants t ON k.tenant_id = t.tenant_id
                JOIN stores s ON k.tenant_id = s.tenant_id AND k.store_id = s.store_id
                WHERE k.key_hash = :key_hash 
                AND k.is_active = TRUE
            """)
            
            result = await db.execute(query, {"key_hash": key_hash})
            key_data = result.fetchone()
            
            if not key_data:
                logger.warning(f"Invalid API key attempt: {api_key[:16]}...")
                raise HTTPException(401, "Invalid API key")
            
            if not key_data.tenant_active:
                raise HTTPException(401, "Tenant account is inactive")
            
            if not key_data.store_active:
                raise HTTPException(401, "Store is inactive")
            
            # Update last_used_at
            await db.execute(
                text("UPDATE store_api_keys SET last_used_at = NOW() WHERE key_hash = :key_hash"),
                {"key_hash": key_hash}
            )
            await db.commit()
            
            return {
                "tenant_id": key_data.tenant_id,
                "store_id": key_data.store_id,
                "key_id": key_data.key_id,
                "company_name": key_data.company_name,
                "store_name": key_data.store_name,
                "auth_type": "api_key"
            }
    
    # User Management (for dashboard authentication)
    async def create_dashboard_user(
        self, 
        tenant_id: str, 
        email: str, 
        user_type: str = "client",
        permissions: List[str] = None
    ) -> Dict:
        """Create dashboard user for tenant"""
        
        # Generate temporary password (should be changed on first login)
        temp_password = secrets.token_urlsafe(16)
        password_hash = self._hash_password(temp_password)
        
        async with get_database() as db:
            # Check if user already exists
            check_query = text("""
                SELECT user_id FROM dashboard_users 
                WHERE email = :email AND tenant_id = :tenant_id
            """)
            existing = await db.execute(check_query, {"email": email, "tenant_id": tenant_id})
            
            if existing.fetchone():
                raise HTTPException(409, f"User {email} already exists for tenant {tenant_id}")
            
            # Insert new user
            user_id = f"user_{tenant_id}_{secrets.token_urlsafe(8)}"
            
            insert_query = text("""
                INSERT INTO dashboard_users (
                    user_id, tenant_id, email, password_hash, user_type, permissions, created_at
                ) VALUES (
                    :user_id, :tenant_id, :email, :password_hash, :user_type, :permissions, NOW()
                )
            """)
            
            await db.execute(insert_query, {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "email": email,
                "password_hash": password_hash,
                "user_type": user_type,
                "permissions": permissions or ["read:metrics", "read:alerts"]
            })
            
            await db.commit()
            
            logger.info(f"Created dashboard user {email} for tenant {tenant_id}")
            
            return {
                "user_id": user_id,
                "tenant_id": tenant_id,
                "email": email,
                "user_type": user_type,
                "permissions": permissions or ["read:metrics", "read:alerts"],
                "temp_password": temp_password,  # Only returned on creation
                "password_change_required": True
            }
    
    async def authenticate_dashboard_user(self, email: str, password: str) -> Dict:
        """Authenticate dashboard user and return user data"""
        
        password_hash = self._hash_password(password)
        
        async with get_database() as db:
            query = text("""
                SELECT 
                    u.user_id, u.tenant_id, u.email, u.user_type, u.permissions,
                    u.password_change_required, u.last_login_at,
                    t.company_name, t.is_active as tenant_active
                FROM dashboard_users u
                JOIN tenants t ON u.tenant_id = t.tenant_id
                WHERE u.email = :email 
                AND u.password_hash = :password_hash 
                AND u.is_active = TRUE
            """)
            
            result = await db.execute(query, {"email": email, "password_hash": password_hash})
            user_data = result.fetchone()
            
            if not user_data:
                logger.warning(f"Failed login attempt for {email}")
                raise HTTPException(401, "Invalid email or password")
            
            if not user_data.tenant_active:
                raise HTTPException(401, "Tenant account is inactive")
            
            # Update last login
            await db.execute(
                text("UPDATE dashboard_users SET last_login_at = NOW() WHERE user_id = :user_id"),
                {"user_id": user_data.user_id}
            )
            await db.commit()
            
            return {
                "user_id": user_data.user_id,
                "tenant_id": user_data.tenant_id,
                "email": user_data.email,
                "user_type": user_data.user_type,
                "permissions": user_data.permissions,
                "company_name": user_data.company_name,
                "password_change_required": user_data.password_change_required,
                "last_login_at": user_data.last_login_at
            }
    
    async def _verify_tenant_active(self, tenant_id: str) -> bool:
        """Verify tenant exists and is active"""
        
        async with get_database() as db:
            query = text("SELECT is_active FROM tenants WHERE tenant_id = :tenant_id")
            result = await db.execute(query, {"tenant_id": tenant_id})
            tenant = result.fetchone()
            
            return tenant and tenant.is_active
    
    def _hash_password(self, password: str) -> str:
        """Hash password using SHA-256 (simple for MVP)"""
        # In production, use bcrypt or similar
        return hashlib.sha256(password.encode()).hexdigest()


# Initialize auth service (will be configured in main app)
auth_service: Optional[AuthService] = None

def init_auth_service(jwt_secret: str):
    """Initialize auth service with JWT secret"""
    global auth_service
    auth_service = AuthService(jwt_secret)

# Dependencies for FastAPI
async def get_current_user_jwt(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """FastAPI dependency to get current user from JWT token"""
    
    if not auth_service:
        raise HTTPException(500, "Auth service not initialized")
    
    token = credentials.credentials
    user_data = await auth_service.verify_access_token(token)
    return user_data

async def get_current_user_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> Dict:
    """FastAPI dependency to get current user from API key"""
    
    if not auth_service:
        raise HTTPException(500, "Auth service not initialized")
    
    api_key = credentials.credentials
    key_data = await auth_service.verify_api_key(api_key)
    return key_data

# Permission checking
def require_permissions(required_permissions: List[str]):
    """Decorator to require specific permissions"""
    
    def dependency(current_user: Dict = Depends(get_current_user_jwt)):
        user_permissions = current_user.get("permissions", [])
        
        for permission in required_permissions:
            if permission not in user_permissions:
                raise HTTPException(
                    403, 
                    f"Permission denied. Required: {permission}"
                )
        
        return current_user
    
    return dependency

def require_tenant_access(tenant_id: str):
    """Decorator to require access to specific tenant"""
    
    def dependency(current_user: Dict = Depends(get_current_user_jwt)):
        if current_user.get("tenant_id") != tenant_id:
            raise HTTPException(
                403, 
                f"Access denied to tenant {tenant_id}"
            )
        
        return current_user
    
    return dependency

# Database schema for dashboard users
DASHBOARD_USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS dashboard_users (
    user_id VARCHAR(100) PRIMARY KEY,
    tenant_id VARCHAR(50) NOT NULL,
    email VARCHAR(255) NOT NULL,
    password_hash VARCHAR(128) NOT NULL,
    user_type VARCHAR(20) DEFAULT 'client',  -- 'client', 'admin', 'readonly'
    permissions JSONB DEFAULT '[]',
    is_active BOOLEAN DEFAULT TRUE,
    password_change_required BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    
    FOREIGN KEY (tenant_id) REFERENCES tenants(tenant_id),
    UNIQUE(email, tenant_id)
);

CREATE INDEX idx_dashboard_users_email ON dashboard_users(email);
CREATE INDEX idx_dashboard_users_tenant ON dashboard_users(tenant_id);
"""