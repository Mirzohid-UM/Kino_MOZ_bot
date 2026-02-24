# db/audit.py
from __future__ import annotations

import time
import json
from typing import Optional, Any, Dict, List, Union

from psycopg2.extras import Json
from .core import get_conn


MetaType = Optional[Union[str, Dict[str, Any], List[Any]]]


def _to_jsonb(meta: MetaType):
    """
    meta:
      - None -> NULL
      - dict/list -> Json(...) (jsonb)
      - str:
          * agar JSON bo'lsa -> Json(parsed)
          * JSON bo'lmasa -> {"text": "..."} ko'rinishida jsonb
    """
    if meta is None:
        return None

    if isinstance(meta, (dict, list)):
        return Json(meta, dumps=lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")))

    if isinstance(meta, str):
        s = meta.strip()
        if not s:
            return None
        # JSON stringmi tekshiramiz
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                obj = json.loads(s)
                return Json(obj, dumps=lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")))
            except Exception:
                pass
        # oddiy text bo'lsa ham JSONB qilib saqlaymiz
        return Json({"text": meta}, dumps=lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")))

    # boshqa typelar (int/bool/...) bo'lsa ham JSONB qilib qo'yamiz
    return Json(meta, dumps=lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")))


def audit(
    actor_id: int,
    action: str,
    target_id: Optional[int] = None,
    meta: MetaType = None,
) -> None:
    conn = get_conn()
    now = int(time.time())

    conn.execute(
        """
        INSERT INTO audit_log (actor_id, action, target_id, meta, created_at)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (int(actor_id), str(action), target_id, _to_jsonb(meta), now),
    )
    conn.commit()


def auditj(
    actor_id: int,
    action: str,
    target_id: Optional[int] = None,
    meta_obj: Optional[Dict[str, Any]] = None,
) -> None:
    audit(actor_id=actor_id, action=action, target_id=target_id, meta=meta_obj)


def last_audit(limit: int = 20) -> List[Dict[str, Any]]:
    conn = get_conn()
    rows = conn.execute(
        """
        SELECT id, actor_id, action, target_id, meta, created_at
        FROM audit_log
        ORDER BY id DESC
        LIMIT %s
        """,
        (int(limit),),
    ).fetchall()
    return [dict(r) for r in rows]