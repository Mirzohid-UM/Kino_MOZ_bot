# db/__init__.py
from .migrations import init_db  # async now!
from .core import init_pool, get_pool

from .movies import (
    add_movie,
    add_alias,
    add_movie_with_aliases,
    delete_movie_by_message_id,
    get_movies_limit,
    get_movies_like,
)

from .users import upsert_user, ensure_user_exists, count_users
from .audit import auditj, last_audit
from .utils import normalize