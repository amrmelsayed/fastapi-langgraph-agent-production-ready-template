"""
JWK-based authentication for FastAPI
"""
import os
from typing import Optional, Dict, Any, Annotated
from functools import lru_cache
import jwt
from jwt import PyJWKClient
from fastapi import HTTPException, Header
from pydantic import BaseModel


class AuthUser(BaseModel):
    """Authenticated user information extracted from JWT"""
    user_id: str
    email: Optional[str] = None


class JWKConfig:
    """JWK authentication configuration"""
    AUTH_URL: Optional[str] = os.environ.get("AUTH_URL")
    _JWT_ISSUER_ENV: str = os.environ.get("JWT_ISSUER", "")
    JWT_ISSUER: list[str] = [iss.strip() for iss in _JWT_ISSUER_ENV.split(",") if iss.strip()]
    JWT_AUDIENCE: str = os.environ.get("JWT_AUDIENCE", "")
    JWT_ALGORITHMS: list[str] = ["EdDSA", "RS256"]


@lru_cache(maxsize=1)
def get_jwks_client() -> PyJWKClient:
    """
    Get cached JWKS client for JWT verification

    Returns:
        Cached PyJWKClient instance

    Raises:
        ValueError: If AUTH_URL is not configured
    """
    if not JWKConfig.AUTH_URL:
        raise ValueError("AUTH_URL environment variable is required for JWK authentication")

    jwks_url = f"{JWKConfig.AUTH_URL}/api/auth/jwks"
    return PyJWKClient(jwks_url)


def verify_jwt(token: str) -> Dict[str, Any]:
    """
    Verify JWT token using JWK and return decoded payload

    Args:
        token: JWT token string

    Returns:
        Decoded JWT payload dictionary

    Raises:
        HTTPException: If token is invalid, expired, or verification fails
    """
    try:
        jwks_client = get_jwks_client()
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        # Decode and verify the JWT
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=JWKConfig.JWT_ALGORITHMS,
            issuer=JWKConfig.JWT_ISSUER if JWKConfig.JWT_ISSUER else None,
            audience=JWKConfig.JWT_AUDIENCE,
            options={"verify_exp": True}
        )

        return payload

    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Authentication failed: {str(e)}")


async def get_current_user(
    authorization: Annotated[str | None, Header()] = None
) -> AuthUser:
    """
    FastAPI dependency to validate JWT and extract user information

    Args:
        authorization: Authorization header with Bearer token

    Returns:
        AuthUser with user_id and optional email

    Raises:
        HTTPException: If authorization header is missing or invalid
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid authorization header"
        )

    token = authorization[7:]  # Remove "Bearer " prefix
    payload = verify_jwt(token)

    return AuthUser(
        user_id=payload.get("sub"),
        email=payload.get("email")
    )
