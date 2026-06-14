"""
Seed demo user. Idempotent.
Run: python /app/backend/seed_demo.py
"""
import asyncio
import uuid
from datetime import datetime, timezone


async def main() -> None:
    from app.core.database import AsyncSessionLocal, engine, Base
    from app.models.user import User
    from app.core.security import hash_password
    from sqlalchemy import select

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as db:
        r = await db.execute(select(User).where(User.email == "demo@tradeai.com"))
        existing = r.scalar_one_or_none()
        if existing:
            # Reset password to ensure credentials work
            existing.hashed_password = hash_password("Demo1234!")
            existing.is_active = True
            existing.is_verified = True
            await db.commit()
            print("Demo user already exists - password reset to Demo1234!")
            return

        db.add(User(
            id=uuid.uuid4(),
            email="demo@tradeai.com",
            username="demo_trader",
            full_name="Demo Trader",
            hashed_password=hash_password("Demo1234!"),
            is_active=True,
            is_verified=True,
            paper_trading_balance="1000000",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ))
        await db.commit()
        print("Demo user created: demo@tradeai.com / Demo1234!")


if __name__ == "__main__":
    asyncio.run(main())
