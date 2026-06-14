"""
Authentication routes — signup, login, refresh.
Path: backend/app/api/v1/auth.py
"""
import uuid
import secrets
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token, decode_token
from app.models.user import User
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse, RefreshRequest, ForgotPasswordRequest, ResetPasswordRequest
from app.services.email_service import send_password_reset_email

logger = logging.getLogger(__name__)
router = APIRouter()


async def _get_by_email(db: AsyncSession, email: str) -> User | None:
    r = await db.execute(select(User).where(User.email == email))
    return r.scalar_one_or_none()


async def _get_by_username(db: AsyncSession, username: str) -> User | None:
    r = await db.execute(select(User).where(User.username == username))
    return r.scalar_one_or_none()


@router.post("/signup", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def signup(data: UserCreate, db: AsyncSession = Depends(get_db)):
    if await _get_by_email(db, data.email):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Email already registered.")
    if await _get_by_username(db, data.username):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Username already taken.")

    user = User(
        id=uuid.uuid4(),
        email=data.email,
        username=data.username,
        full_name=data.full_name,
        hashed_password=hash_password(data.password),
        email_verification_token=secrets.token_urlsafe(32),
        is_active=True,
        is_verified=False,
    )
    db.add(user)
    await db.flush()
    logger.info(f"User registered: {user.email}")
    return user


@router.post("/login", response_model=TokenResponse)
async def login(data: UserLogin, db: AsyncSession = Depends(get_db)):
    user = await _get_by_email(db, data.email)
    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Account is disabled.")

    user.last_login = datetime.now(timezone.utc)
    token_data = {"sub": str(user.id), "email": user.email}
    logger.info(f"User logged in: {user.email}")
    return TokenResponse(
        access_token=create_access_token(token_data),
        refresh_token=create_refresh_token(token_data),
        user=user,
    )


@router.post("/refresh")
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if payload.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid token type.")
    user_id = payload.get("sub")
    r = await db.execute(select(User).where(User.id == user_id))
    user = r.scalar_one_or_none()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User not found.")
    token_data = {"sub": str(user.id), "email": user.email}
    return {"access_token": create_access_token(token_data), "token_type": "bearer"}


@router.post("/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    user = await _get_by_email(db, data.email)
    if not user:
        # Don't reveal whether the email exists
        return {"message": "If that email is registered, a password reset link has been sent."}

    token = secrets.token_urlsafe(32)
    user.password_reset_token = token
    user.password_reset_expires = datetime.now(timezone.utc) + timedelta(hours=1)
    await db.flush()

    logger.info(f"Password reset token generated for {user.email}")

    reset_url = f"{settings.APP_URL or 'http://localhost:3001'}/reset-password/{token}"

    # Send email via SendGrid — returns False if no API key is configured
    # Offload to thread pool to avoid blocking the async event loop
    email_sent = await asyncio.to_thread(send_password_reset_email, user.email, reset_url)

    if email_sent:
        logger.info(f"Password reset email sent to {user.email}")
    else:
        logger.info(f"SendGrid not configured — reset URL: {reset_url}")

    return {
        "message": "If that email is registered, a password reset link has been sent.",
        # In dev mode, return reset URL so user can test without email
        "reset_url": reset_url if not settings.SENDGRID_API_KEY else None,
    }


@router.post("/reset-password")
async def reset_password(data: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    r = await db.execute(
        select(User).where(User.password_reset_token == data.token)
    )
    user = r.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token.")
    if user.password_reset_expires and user.password_reset_expires < datetime.now(timezone.utc):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Reset token has expired.")

    user.hashed_password = hash_password(data.password)
    user.password_reset_token = None
    user.password_reset_expires = None
    await db.flush()

    logger.info(f"Password reset successful for {user.email}")
    return {"message": "Password reset successfully. You can now log in with your new password."}


@router.get("/verify-email/{token}")
async def verify_email(token: str, db: AsyncSession = Depends(get_db)):
    r = await db.execute(select(User).where(User.email_verification_token == token))
    user = r.scalar_one_or_none()
    if not user:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired link.")
    user.is_verified = True
    user.email_verification_token = None
    return {"message": "Email verified successfully."}
