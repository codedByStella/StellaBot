"""Persistence facade preserving the application's stable internal API."""

from companion_app.database.common import (
    BASE_DIR,
    DB_FILE,
    COMPANION_PROFILE_FILE,
    COMPANION_STATE_FILE,
    _load_json,
    _save_json,
)
from companion_app.database.core import (
    _contains_any,
    _infer_companion_state,
    _init_memory_db,
    _load_companion_state,
    _save_companion_state,
    get_memories,
    save_memory,
    should_remember,
)
from companion_app.database.history import (
    _init_shared_history,
    _maybe_save_shared_moment,
    _save_shared_moment,
    get_shared_history,
)
from companion_app.database.preferences import (
    _init_user_preferences,
    _learn_user_preference,
    _load_companion_profile,
    get_user_preferences,
)
from companion_app.database.companion_memory import (
    COMPANION_SOCIAL_LOCK,
    COMPANION_SOCIAL_THREAD_MAX,
    COMPANION_SOCIAL_THREADS,
    _extract_companion_self_beliefs,
    _extract_companion_social_threads,
    _init_companion_self_memory,
    _save_companion_self_beliefs,
    _update_companion_social_threads,
    get_companion_self_memory,
)
