# coding: utf-8
"""Cookie-based local user authentication endpoints."""
from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from trading_v2.api.dependencies import get_auth_service
from trading_v2.auth.models import AuthStatus, Credentials, User
from trading_v2.auth.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])
COOKIE = "curs_v2_session"

def _set_cookie(response: Response, token: str, secure: bool) -> None:
    response.set_cookie(COOKIE, token, httponly=True, samesite="lax", secure=secure, max_age=604800, path="/")

@router.post("/register", response_model=User, status_code=status.HTTP_201_CREATED)
async def register(command: Credentials, response: Response, service: Annotated[AuthService, Depends(get_auth_service)], request: Request) -> User:
    try:
        user, token = service.register(command.username, command.password)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    _set_cookie(response, token, request.url.scheme == "https")
    return user

@router.post("/login", response_model=User)
async def login(command: Credentials, response: Response, service: Annotated[AuthService, Depends(get_auth_service)], request: Request) -> User:
    result = service.authenticate(command.username, command.password)
    if result is None:
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    user, token = result
    _set_cookie(response, token, request.url.scheme == "https")
    return user

@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request, response: Response, service: Annotated[AuthService, Depends(get_auth_service)]) -> None:
    service.revoke_token(request.cookies.get(COOKIE))
    response.delete_cookie(COOKIE, path="/")

@router.get("/me", response_model=AuthStatus)
async def me(request: Request, service: Annotated[AuthService, Depends(get_auth_service)]) -> AuthStatus:
    if not request.app.state.settings.auth_enabled:
        from datetime import datetime, timezone
        return AuthStatus(authenticated=True, user=User(id="development", username="development", created_at=datetime.now(timezone.utc)))
    user = service.user_from_token(request.cookies.get(COOKIE))
    return AuthStatus(authenticated=user is not None, user=user)
