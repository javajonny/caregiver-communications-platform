import os
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any, Optional, Type, TypeVar

from fastapi import HTTPException
from sqlalchemy.orm import Session

T = TypeVar("T")


def get_or_404(
    db: Session,
    model: Type[T],
    id_value: Any,
    id_attr: str = "id",
    detail: Optional[str] = None,
) -> T:
    """
    Fetch a single row from the DB by a given attribute (defaults to primary id).
    If not found, raise a 404 HTTPException.

    Example usages:
        client = get_or_404(db, Client, client_id)
        contact = get_or_404(db, ClientContact, contact_id)
        residence = get_or_404(db, ClientCurrentResidence, client_id, id_attr="client_id")
    """
    if not hasattr(model, id_attr):
        raise ValueError(f"Model {model.__name__} has no attribute '{id_attr}'")

    obj = db.query(model).filter(getattr(model, id_attr) == id_value).first()
    if not obj:
        raise HTTPException(status_code=404, detail=detail or f"{model.__name__} not found")
    return obj


def get_now(tz: ZoneInfo | None = None) -> datetime:
    """
    Returns the current datetime in the given timezone.
    If the FAKE_NOW environment variable is set (format: YYYY-MM-DDTHH:MM:SS),
    returns that fixed time instead — useful for dev/testing shift logic.

    Example:
        FAKE_NOW=2026-03-30T10:00:00  # pretend it is 10:00 AM
    """
    fake = os.environ.get("FAKE_NOW")
    if fake:
        try:
            naive = datetime.fromisoformat(fake)
            return naive.replace(tzinfo=tz) if tz else naive
        except ValueError:
            pass  # Fall through to real time if value is malformed
    return datetime.now(tz) if tz else datetime.now()


import re

def validate_password_strength(password: str):
    if len(password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters long")
    if not re.search(r"[A-Z]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one uppercase letter")
    if not re.search(r"[a-z]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one lowercase letter")
    if not re.search(r"\d", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one digit")
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        raise HTTPException(status_code=400, detail="Password must contain at least one special character")
