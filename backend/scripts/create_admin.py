# Name: Rahul Singh Bana
# Email: bana.saa@gmail.com
# LinkedIn: https://www.linkedin.com/in/rahulsinghbana
#
# Bootstraps the first admin account (or promotes an existing user to
# admin). There is no public "become admin" endpoint by design, so this is
# the only way to get an admin into a fresh database.
#
# Usage (from backend/, with the venv active):
#   python -m scripts.create_admin \
#       --email admin@example.com --password "change-me" --full-name "Admin"

import argparse

from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.user import UserRole
from app.repositories import user_repository


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or promote a user to admin.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--full-name", default="Administrator")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        existing = user_repository.get_by_email(db, args.email)
        if existing is not None:
            user_repository.update(db, existing, role=UserRole.ADMIN, is_active=True)
            print(f"Promoted existing user {args.email} to admin.")
            return

        user_repository.create(
            db,
            email=args.email,
            hashed_password=hash_password(args.password),
            full_name=args.full_name,
            role=UserRole.ADMIN,
        )
        print(f"Created admin user {args.email}.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
