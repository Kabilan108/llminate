from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import APIRouter, Request, HTTPException, Depends, Body
from authlib.integrations.starlette_client import OAuthError
from fastapi.responses import RedirectResponse

from core.auth import (
    oauth,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_new_access_token,
)
from api.deps import get_db, get_settings, AsyncIOMotorClient, Settings
from schema.auth import OAuthUser, OAuthUserInDB, User

router = APIRouter()
auth_scheme = HTTPBearer()


@router.get("/login", name="login")
async def login(request: Request):
    redirect_uri = request.url_for("token")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/token", name="token")
async def token(
    request: Request,
    settings: Settings = Depends(get_settings),
    db: AsyncIOMotorClient = Depends(get_db),
) -> RedirectResponse:
    try:
        google_token = await oauth.google.authorize_access_token(request)
        user_info = OAuthUser(**google_token.get("userinfo"))

        user: OAuthUserInDB = await authenticate_user(db, user_info)

        access_token = create_access_token(sub=user.sub)
        refresh_token = create_refresh_token(sub=user.sub)
        redirect_url = f"{settings.CLIENT_URL}/app#access_token={access_token}&refresh_token={refresh_token}"
        return RedirectResponse(url=redirect_url)
    except OAuthError as e:
        raise HTTPException(status_code=400, detail=f"OAuth error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to authenticate user: {e}")


@router.get("/user", name="user", response_model=User)
async def user(
    access_token: HTTPAuthorizationCredentials = Depends(HTTPBearer()),
    db: AsyncIOMotorClient = Depends(get_db),
):
    if access_token is None:
        raise HTTPException(
            status_code=401,
            detail="No authentication token provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await get_current_user(access_token.credentials, db)
    return {"user": user}


@router.post("/refresh", name="refresh")
async def refresh(
    refresh_token: str = Body(...),
    db: AsyncIOMotorClient = Depends(get_db),
):
    access_token = await get_new_access_token(refresh_token, db)
    return {"access_token": access_token}
