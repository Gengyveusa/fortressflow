#!/usr/bin/env python3
"""Seed the first admin user.

Usage:
    python seed_admin.py --email admin@example.com --password <password> --name "Admin"
"""

import argparse
import asyncio
import sys
from pathlib import Path

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.user import User, UserRole
from app.services.auth_service import hash_password


async def seed(email: str, password: str, name: str) -> None:
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == email))
        existing = result.scalar_one_or_none()

        if existing:
            print(f"User {email} already exists (id={existing.id}, role={existing.role.value}).")
            print("Updating to admin role...")
            existing.role = UserRole.admin
            existing.password_hash = hash_password(password)
            existing.full_name = name
            existing.is_active = True
            await session.commit()
            print(f"Updated {email} -> admin.")
            return

        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=name,
            role=UserRole.admin,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        print(f"Created admin user: {email} (id={user.id})")


def main() -> None:
    parser = argparse.ArgumentParser(description="Seed admin user for FortressFlow")
    parser.add_argument("--email", required=True, help="Admin email address")
    parser.add_argument("--password", required=True, help="Admin password")
    parser.add_argument("--name", default="Admin", help="Full name (default: Admin)")
    args = parser.parse_args()

    if len(args.password) < 8:
        print("Error: password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    asyncio.run(seed(args.email, args.password, args.name))


if __name__ == "__main__":
    main()
