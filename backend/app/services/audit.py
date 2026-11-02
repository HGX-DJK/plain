"""操作日志。"""
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.models.system import OperationLog, User


def log_action(
    db: Session,
    user: User | None,
    action: str,
    target: str | None = None,
    detail: dict[str, Any] | None = None,
    ip: str | None = None,
) -> None:
    db.add(
        OperationLog(
            user_id=user.id if user else None,
            username=user.username if user else None,
            action=action,
            target=target,
            detail=detail,
            ip=ip,
            created_at=datetime.now(timezone.utc),
        )
    )
