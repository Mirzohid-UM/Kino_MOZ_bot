# db/__init__.py
from .migrations import init_db
from .movies import add_movie, delete_movie_by_message_id, get_movies_like, get_movies_limit
from .users import upsert_user, ensure_user_exists, count_users
from .access import grant_access, extend_access, has_access, count_active_subs, list_active_users, list_active_user_ids
from .audit import audit, last_audit,auditj
from .search_logs import log_search
from .access import list_active_users_with_profiles, get_expiring_between, was_notified, mark_notified
from .core import  normalize