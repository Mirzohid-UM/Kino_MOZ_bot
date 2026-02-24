# db/__init__.py
from .migrations import init_db

from .core import get_conn

from .movies import (
    add_movie,
    add_alias,
    delete_movie_by_message_id,
    get_movies_limit,
    get_movies_like,        # tavsiya
      # eski importlar buzilmasin deb qoldirilgan bo'lsa
)

from .users import upsert_user, ensure_user_exists, count_users

from .access import (
    grant_access,
    extend_access,
    has_access,
    count_active_subs,
    list_active_users,
    list_active_user_ids,
    list_active_users_with_profiles,
    get_expiring_between,
    was_notified,
    mark_notified,
)

from .audit import audit, auditj, last_audit

from .search_logs import log_search
from .utils import normalize