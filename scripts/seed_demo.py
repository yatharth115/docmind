import argparse
import os
import sys
from pathlib import Path

from app.core.security import hash_password
from app.db.models import Document, User
from app.db.session import SessionLocal
from eval.ingest_corpus import ingest_pdf


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("pdfs", nargs="+")
    ap.add_argument("--email", default="demo@docmind.demo")
    ap.add_argument("--size", type=int, default=200)
    ap.add_argument("--overlap", type=int, default=30)
    args = ap.parse_args()

    password = os.environ.get("DEMO_PASSWORD", "")
    if not 8 <= len(password) <= 72:
        sys.exit("Set DEMO_PASSWORD (8 to 72 characters) in the environment first.")

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.email == args.email).first()
        if user is None:
            user = User(email=args.email, hashed_password=hash_password(password))
            db.add(user)
            db.commit()
            db.refresh(user)
            print(f"created user {args.email}")
        else:
            user.hashed_password = hash_password(password)
            db.commit()
            print(f"updated password for {args.email}")

        for p in args.pdfs:
            path = Path(p)
            existing = (
                db.query(Document)
                .filter(Document.user_id == user.id, Document.filename == path.name)
                .first()
            )
            if existing and existing.status == "ready":
                print(f"skip   {path.name} (already loaded)")
                continue
            if existing:
                db.delete(existing)
                db.commit()
            print(f"ingest {path.name}")
            n = ingest_pdf(db, user, path, args.size, args.overlap)
            print(f"   done: {n} chunks")
    finally:
        db.close()


if __name__ == "__main__":
    main()