# db/audit.py
from __future__ import annotations
import time
from .core import get_conn
from typing import Optional, Any, Dict
import json


def audit(
    actor_id: int,
    action: str,
    target_id: Optional[int] = None,
    meta: Optional[str] = None,
) -> None:
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO audit_log (actor_id, action, target_id, meta, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (int(actor_id), str(action), target_id, meta, int(time.time())),
    )
    conn.commit()


def last_audit(limit: int = 20):
    conn = get_conn()
    return conn.execute(
        """
        SELECT actor_id, action, target_id, meta, created_at
        FROM audit_log
        ORDER BY id DESC
        LIMIT ?
        """,
        (int(limit),),
    ).fetchall()


def auditj(actor_id: int, action: str, target_id: Optional[int] = None, meta_obj: Optional[Dict[str, Any]] = None) -> None:
    """meta ni JSON qilib yozadi (keyin o‘qish oson bo‘ladi)."""
    meta = None
    if meta_obj is not None:
        meta = json.dumps(meta_obj, ensure_ascii=False, separators=(",", ":"))
    audit(actor_id=actor_id, action=action, target_id=target_id, meta=meta)