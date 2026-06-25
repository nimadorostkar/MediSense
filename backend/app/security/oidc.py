"""OAuth2 / OIDC bearer-token validation (spec §2, §8).

Two paths behind one interface:
- DEV_AUTH=true: accept a locally-signed HS256 dev token so the stack runs
  without the hospital IdP. `mint_dev_token` issues one for dev/tests.
- Production: validate RS256 tokens against the hospital IdP's JWKS
  (OIDC_ISSUER / OIDC_AUDIENCE / OIDC_JWKS_URL). The JWKS path is implemented
  behind config and used when DEV_AUTH is false.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import jwt

from app.config import settings
from app.errors import AuthError

_DEV_ALG = "HS256"


@dataclass
class User:
    sub: str
    name: str
    role: str
    region: str = "cn-pilot"


def mint_dev_token(sub: str, name: str, role: str, ttl: int = 3600) -> str:
    if not settings.dev_auth:
        raise AuthError("Dev tokens are disabled (DEV_AUTH=false)")
    now = int(time.time())
    payload = {
        "sub": sub,
        "name": name,
        "role": role,
        "iss": "medisense-dev",
        "aud": settings.oidc_audience,
        "iat": now,
        "exp": now + ttl,
        "region": settings.data_region,
    }
    return jwt.encode(payload, settings.dev_auth_secret, algorithm=_DEV_ALG)


def _decode_dev(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.dev_auth_secret,
            algorithms=[_DEV_ALG],
            audience=settings.oidc_audience,
            options={"verify_aud": True},
        )
    except jwt.PyJWTError as exc:
        raise AuthError(f"Invalid dev token: {exc}") from exc


def _decode_oidc(token: str) -> dict:  # pragma: no cover - requires live IdP/JWKS
    if not (settings.oidc_issuer and settings.oidc_jwks_url):
        raise AuthError("OIDC not configured")
    try:
        jwks_client = jwt.PyJWKClient(settings.oidc_jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
        )
    except jwt.PyJWTError as exc:
        raise AuthError(f"Invalid token: {exc}") from exc


def validate_token(token: str) -> User:
    claims = _decode_dev(token) if settings.dev_auth else _decode_oidc(token)
    role = claims.get("role") or (claims.get("roles") or [None])[0]
    if not role:
        raise AuthError("Token missing role claim")
    return User(
        sub=str(claims.get("sub", "unknown")),
        name=str(claims.get("name", claims.get("sub", "unknown"))),
        role=str(role),
        region=str(claims.get("region", settings.data_region)),
    )
