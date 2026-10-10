"""
Backend/make_admin.py

Give (or take away) admin rights from the command line. Run it from the project
root, with DATABASE_URL pointing at the database you want to change:

    python -m Backend.make_admin you@example.com
    python -m Backend.make_admin you@example.com --revoke

Admin is deliberately not something a request can grant itself, so the first
admin has to be created here.
"""

import sys

from sqlalchemy import func

from Backend.database import SessionLocal
from Backend.models import User


def main(argv: list[str]) -> int:
    args = [a for a in argv if not a.startswith("--")]
    if len(args) != 1:
        print("Usage: python -m Backend.make_admin EMAIL [--revoke]")
        return 2
    email = args[0].strip().lower()
    role = "user" if "--revoke" in argv else "admin"

    db = SessionLocal()
    try:
        user = db.query(User).filter(func.lower(User.email) == email).first()
        if not user:
            print(f"No user with email {email}. Register that account first.")
            return 1
        user.role = role
        db.commit()
        print(f"{user.email} is now '{role}'.")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))