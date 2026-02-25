# db/audit.py
from __future__ import annotations

import time
import json
from typing import Any, Dict, List, Optional, Union

from db.core import get_pool

MetaType = Optional[Union[str, Dict[str, Any], List[Any], int, float, bool]]

def _normalize_meta(meta: MetaType) -> Any:
    """
    asyncpg uchun:
      - None -> None (NULL)
      - dict/list/bool/int/... -> o'z holicha (jsonb)
      - str:
          * agar JSON bo'lsa -> parsed obj
          * bo'lmasa -> {"text": "..."}
    """
    if meta is None:
        return None

    if isinstance(meta, (dict, list, int, float, bool)):
        return meta

    if isinstance(meta, str):
        s = meta.strip()
        if not s:
            return None
        # JSON stringmi?
        if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
            try:
                return json.loads(s)
            except Exception:
                pass
        return {"text": meta}

    # fallback: json-serializable qilishga urinib ko'ramiz
    try:
        json.dumps(meta, ensure_ascii=False)
        return meta
    except Exception:
        return {"text": str(meta)}

async def auditj(*, actor_id: int, action: str, target_id: Optional[int] = None, meta: MetaType = None) -> None:
    now = int(time.time())
    meta_obj = _normalize_meta(meta)

    pool = get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO audit_log (actor_id, action, target_id, meta, created_at)
            VALUES ($1, $2, $3, $4::jsonb, $5)
            """,
            int(actor_id), str(action), target_id, meta_obj, now
        )

async def last_audit(limit: int = 20) -> List[Dict[str, Any]]:
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, actor_id, action, target_id, meta, created_at
            FROM audit_log
            ORDER BY id DESC
            LIMIT $1
            """,
            int(limit),
        )
    return [dict(r) for r in rows]