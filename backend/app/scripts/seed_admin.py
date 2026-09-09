"""Creates one local admin user, since there's no public signup (accounts are admin-provisioned).

Usage: uv run python -m app.scripts.seed_admin <email> <password>
"""

import asyncio
import sys

from sqlalchemy import select

from app.core.security import hash_password
from app.db.base import SessionLocal
from app.models.user import User


async def seed_admin(email: str, password: str) -> None:
    async with SessionLocal() as db:
        existing = await db.execute(select(User).where(User.email == email))
        if existing.scalar_one_or_none() is not None:
            print(f"User {email} already exists, skipping.")
            return

        db.add(User(email=email, password_hash=hash_password(password), role="admin"))
        await db.commit()
        print(f"Created admin user {email}.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: uv run python -m app.scripts.seed_admin <email> <password>")
        sys.exit(1)

    asyncio.run(seed_admin(sys.argv[1], sys.argv[2]))
