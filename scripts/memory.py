import asyncio
import re
import sqlite3
import threading
import time
import unicodedata
from contextlib import closing
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DB_PATH = Path("/config/memory.db")
RESULT_ENTITY = "sensor.memory_result"
EXPIRATION_MAX_DAYS = 3650
SEARCH_LIMIT_MAX = 50
NEAR_DISTANCE = 5
CANDIDATE_CHECK_LIMIT = 5
HOUSEKEEPING_GRACE_DAYS = 10
HOUSEKEEPING_GRACE_MAX_DAYS = 365
VALUE_PREVIEW_CHARS = 120
BM25_WEIGHT = 0.5

EXTRA_CHAR_REPLACEMENTS = {
    "đ": "d",
    "Đ": "d",
    "ı": "i",  # noqa: RUF001
    "İ": "i",
    "ñ": "n",
    "Ñ": "n",
    "ç": "c",
    "Ç": "c",
    "ğ": "g",
    "Ğ": "g",
    "ş": "s",
    "Ş": "s",
    "ø": "o",
    "Ø": "o",
    "ł": "l",
    "Ł": "l",
    "ß": "ss",
    "Æ": "AE",
    "æ": "ae",
    "Œ": "OE",
    "œ": "oe",
    "Þ": "th",
    "þ": "th",
    "Ð": "d",
    "ð": "d",
    "Å": "a",
    "å": "a",
    "Ä": "a",
    "ä": "a",
    "Ö": "o",
    "ö": "o",
    "Ü": "u",
    "ü": "u",
}

_DB_READY = False
_DB_READY_LOCK = threading.Lock()

result_entity_name: dict[str, str] = {}


def _build_result_entity_name() -> dict[str, str]:
    """Build a friendly name dict for the result entity."""
    tail = RESULT_ENTITY.split(".")[-1]
    parts = [part.capitalize() for part in tail.split("_") if part]
    friendly = " ".join(parts) or tail
    return {"friendly_name": friendly}


def _ensure_result_entity_name(force: bool = False) -> None:
    """Ensure result_entity_name is populated, optionally forcing a refresh."""
    global result_entity_name
    if force or not result_entity_name:
        result_entity_name = _build_result_entity_name()


@pyscript_compile  # noqa: F821
def _utcnow_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(UTC).isoformat()


@pyscript_compile  # noqa: F821
def _dt_from_iso(s: str) -> datetime | None:
    """Parse an ISO string into datetime; return None if invalid."""
    try:
        return datetime.fromisoformat(s)
    except TypeError, ValueError:
        return None


@pyscript_compile  # noqa: F821
def _get_db_connection() -> sqlite3.Connection:
    """Create a properly configured database connection."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("PRAGMA temp_store=MEMORY;")
    conn.execute("PRAGMA busy_timeout=3000;")
    return conn


@pyscript_compile  # noqa: F821
def _ensure_db() -> None:
    """Ensure database exists and tables/indices are created.

    Uses a short-lived connection to avoid leaving an idle connection open
    at import time.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(_get_db_connection()) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS mem
            (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                key          TEXT UNIQUE NOT NULL,
                value        TEXT        NOT NULL,
                scope        TEXT        NOT NULL,
                tags         TEXT        NOT NULL,
                tags_search  TEXT        NOT NULL,
                created_at   TEXT        NOT NULL,
                last_used_at TEXT        NOT NULL,
                expires_at   TEXT
            );
            """
        )
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS mem_fts USING fts5(
                key, value, tags,
                content='mem',
                content_rowid='id',
                tokenize = 'unicode61 remove_diacritics 2'
            );
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_mem_scope ON mem(scope);")
        conn.executescript(
            """
            CREATE TRIGGER IF NOT EXISTS mem_ai
                AFTER INSERT
                ON mem
            BEGIN
                INSERT INTO mem_fts(rowid, key, value, tags)
                VALUES (new.id,
                        new.key,
                        new.value,
                        new.tags_search);
            END;

            CREATE TRIGGER IF NOT EXISTS mem_ad
                AFTER DELETE
                ON mem
            BEGIN
                INSERT INTO mem_fts(mem_fts, rowid, key, value, tags)
                VALUES ('delete', old.id, old.key, old.value, old.tags_search);
            END;

            CREATE TRIGGER IF NOT EXISTS mem_au
                AFTER UPDATE OF key, value, tags_search
                ON mem
                WHEN (old.key IS NOT new.key)
                    OR (old.value IS NOT new.value)
                    OR (old.tags_search IS NOT new.tags_search)
            BEGIN
                INSERT INTO mem_fts(mem_fts, rowid, key, value, tags)
                VALUES ('delete', old.id, old.key, old.value, old.tags_search);
                INSERT INTO mem_fts(rowid, key, value, tags)
                VALUES (new.id,
                        new.key,
                        new.value,
                        new.tags_search);
            END;
            """
        )
        conn.execute("PRAGMA optimize;")
        conn.commit()


@pyscript_compile  # noqa: F821
def _ensure_db_once(force: bool = False) -> None:
    """Ensure the database schema exists once per runtime."""
    global _DB_READY
    if force:
        _DB_READY = False
    if _DB_READY and DB_PATH.exists():
        return
    with _DB_READY_LOCK:
        if force:
            _DB_READY = False
        if not _DB_READY or not DB_PATH.exists():
            _ensure_db()
            _DB_READY = True


@pyscript_compile  # noqa: F821
def _normalize_value(s: str) -> str:
    """Normalize a text value for storage (NFC)."""
    if s is None:
        return ""
    return unicodedata.normalize("NFC", str(s))


@pyscript_compile  # noqa: F821
def _strip_diacritics(value: str) -> str:
    """Remove diacritics and normalize locale-specific letters (Vietnamese, Turkish, Spanish, Germanic, Nordic)."""
    if value is None:
        return ""
    decomposed = unicodedata.normalize("NFKD", value)
    filtered: list[str] = []
    for ch in decomposed:
        replacement = EXTRA_CHAR_REPLACEMENTS.get(ch)
        if replacement is not None:
            if replacement:
                filtered.extend(replacement)
            continue
        if unicodedata.category(ch) == "Mn":
            continue
        filtered.append(ch)
    return "".join(filtered)


@pyscript_compile  # noqa: F821
def _normalize_search_text(value: str | None) -> str:
    """Lowercase, strip diacritics, and collapse whitespace for search usage."""
    if value is None:
        return ""
    lowered = str(value).lower()
    stripped = _strip_diacritics(lowered)
    cleaned = re.sub(r"[,/_]+", " ", stripped)
    cleaned = re.sub(r"[^a-z0-9]+", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


@pyscript_compile  # noqa: F821
def _normalize_tags(s: str) -> str:
    """Normalize tags similarly to keys but retain space-separated words."""
    return _normalize_search_text(s)


@pyscript_compile  # noqa: F821
def _normalize_key(s: str) -> str:
    """Normalize a key to [a-z0-9_], lowercase, no accents."""
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = _strip_diacritics(s)
    s = re.sub(r"[^a-z0-9_]", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def _condense_candidate_for_selection(
    entry: dict[str, Any], *, score: float | None = None
) -> dict[str, Any]:
    """Prepare a candidate dict with trimmed value and optional score."""
    value = entry.get("value")
    if isinstance(value, str) and len(value) > VALUE_PREVIEW_CHARS:
        value = value[: VALUE_PREVIEW_CHARS - 3] + "..."
    data = {
        "key": entry.get("key"),
        "value": value,
        "scope": entry.get("scope"),
        "tags": entry.get("tags"),
        "created_at": entry.get("created_at"),
        "last_used_at": entry.get("last_used_at"),
        "expires_at": entry.get("expires_at"),
    }
    if score is not None:
        data["match_score"] = score
    return data


@pyscript_compile  # noqa: F821
def _calculate_match_score(
    source_tokens: set[str], candidate_tokens: set[str], bm25_raw: float | None
) -> float:
    """Blend Jaccard overlap with BM25 to estimate relevance."""
    if not source_tokens or not candidate_tokens:
        jaccard_score = 0.0
    else:
        intersection = source_tokens.intersection(candidate_tokens)
        if not intersection:
            return 0.0
        union = source_tokens.union(candidate_tokens)
        union_size = len(union) or 1
        jaccard_score = len(intersection) / union_size
    if isinstance(bm25_raw, (int, float)):
        bm25_score = 1 / (1 + max(bm25_raw, 0))
        jaccard_weight = 1 - BM25_WEIGHT
        return BM25_WEIGHT * bm25_score + jaccard_weight * jaccard_score
    return jaccard_score


async def _search_tag_candidates(
    source: str,
    *,
    exclude_keys: set[str] | None = None,
    limit: int | None = None,
    log_context: str = "tag lookup",
) -> list[tuple[dict[str, Any], float]]:
    """Return (entry, score) tuples for memories sharing normalized tags."""
    tags_search = _normalize_tags(source or "")
    if not tags_search:
        return []
    tag_tokens = {token for token in tags_search.split() if token}
    if not tag_tokens:
        return []
    limit_value = (
        limit if limit is not None else min(CANDIDATE_CHECK_LIMIT, SEARCH_LIMIT_MAX)
    )
    limit_value = max(1, min(limit_value, SEARCH_LIMIT_MAX))
    try:
        raw_matches = await _memory_search_db(tags_search, limit=limit_value)
    except Exception as lookup_err:
        log.error(f"memory {log_context} failed for '{tags_search}': {lookup_err}")  # noqa: F821
        return []
    if not raw_matches:
        return []
    exclude_norm = (
        {_normalize_key(item) for item in exclude_keys if item}
        if exclude_keys
        else set()
    )
    dedup: dict[str, tuple[dict[str, Any], float]] = {}
    for item in raw_matches:
        existing_key = _normalize_key(item.get("key"))
        if not existing_key or existing_key in exclude_norm or existing_key in dedup:
            continue
        score_raw = item.get("match_score")
        score_val: float | None
        if isinstance(score_raw, (int, float)):
            score_val = float(score_raw)
        else:
            try:
                score_val = float(score_raw)
            except TypeError, ValueError:
                existing_tags_norm = _normalize_tags(item.get("tags"))
                candidate_tokens = {
                    token for token in existing_tags_norm.split() if token
                }
                score_val = _calculate_match_score(tag_tokens, candidate_tokens, None)
        if score_val is None or score_val <= 0:
            continue
        dedup[existing_key] = (item, score_val)
    if not dedup:
        return []
    sorted_candidates = sorted(dedup.values(), key=lambda pair: pair[1], reverse=True)
    return sorted_candidates[:limit_value]


async def _find_tag_matches_for_query(
    source: str,
    *,
    exclude_keys: set[str] | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Search for potential key matches based on normalized tags."""
    candidates = await _search_tag_candidates(
        source,
        exclude_keys=exclude_keys,
        limit=limit,
        log_context="tag lookup",
    )
    if not candidates:
        return []
    return [
        _condense_candidate_for_selection(entry, score=score)
        for entry, score in candidates
    ]


@pyscript_compile  # noqa: F821
def _tokenize_query(q: str) -> list[str]:
    """Tokenize a free-text query into normalized word tokens for FTS."""
    normalized = _normalize_search_text(q)
    if not normalized:
        return []
    return normalized.split()


@pyscript_compile  # noqa: F821
def _near_distance_for_tokens(n: int) -> int:
    """Compute dynamic NEAR distance based on token count."""
    if n <= 1:
        return 0
    val = 2 * n - 1
    if val < 3:
        val = 3
    if val > NEAR_DISTANCE:
        val = NEAR_DISTANCE
    return val


@pyscript_compile  # noqa: F821
def _build_fts_queries(raw_query: str) -> list[str]:
    """Build a list of FTS5 MATCH query variants to improve recall.

    Strategy (ordered by priority):
    - PHRASE: exact phrase (highest precision when user typed a phrase)
    - NEAR: tokens appear within proximity (high relevance, dynamic distance)
    - AND: all tokens must appear (relevant but looser than NEAR)
    - OR*: any token with prefix match (broad recall)
    - RAW: the original raw query as a last option
    """
    normalized_query = _normalize_search_text(raw_query)
    tokens = normalized_query.split() if normalized_query else []
    variants = []

    if tokens:
        # 1) PHRASE exact order (if 2+ tokens)
        if len(tokens) >= 2:
            phrase = " ".join(tokens)
            variants.append(f'"{phrase}"')

        # 2) NEAR across all tokens (if 2+ tokens)
        if len(tokens) >= 2:
            near_inner = " ".join(tokens)
            near_dist = _near_distance_for_tokens(len(tokens))
            variants.append(f"NEAR({near_inner}, {near_dist})")

        # 3) AND of all tokens (or single token)
        if len(tokens) == 1:
            variants.append(tokens[0])
        else:
            variants.append(" AND ".join(tokens))

        # 4) OR with prefix match to broaden recall
        or_tokens = [f"{t}*" for t in tokens]
        variants.append(" OR ".join(or_tokens))

    # 5) RAW as very last resort if provided
    if normalized_query:
        variants.append(normalized_query)
    rq = (raw_query or "").strip()
    if rq:
        variants.append(rq)

    # Deduplicate while preserving order
    seen = set()
    out = []
    for v in variants:
        if v not in seen:
            out.append(v)
            seen.add(v)
    return out


@pyscript_compile  # noqa: F821
def _fetch_with_expiry(
    cur: sqlite3.Cursor, key: str
) -> tuple[bool, sqlite3.Row | None]:
    """Fetch the row and report whether it is expired; never deletes the row."""
    row = cur.execute(
        """
        SELECT key,
               value,
               scope,
               tags,
               created_at,
               last_used_at,
               expires_at
        FROM mem
        WHERE key = ?;
        """,
        (key,),
    ).fetchone()
    if not row:
        return False, None
    expires_at = row["expires_at"]
    if expires_at:
        dt = _dt_from_iso(expires_at)
        if dt and datetime.now(UTC) > dt:
            return True, row
    return False, row


def _set_result(state_value: str = "ok", **attrs: Any) -> None:
    """Set result sensor state and attributes."""
    _ensure_result_entity_name()
    attrs.update(result_entity_name)
    state.set(RESULT_ENTITY, value=state_value, new_attributes=attrs)  # noqa: F821


@pyscript_compile  # noqa: F821
def _reset_db_ready() -> None:
    """Mark the cached DB-ready flag as stale so the next call rebuilds."""
    global _DB_READY
    with _DB_READY_LOCK:
        _DB_READY = False


@pyscript_compile  # noqa: F821
def _memory_set_db_sync(
    key_norm: str,
    value_norm: str,
    scope_norm: str,
    tags_raw: str,
    tags_search: str,
    now_iso: str,
    expires_at: str | None,
) -> bool:
    """Persist a memory record, retrying once if schema objects are missing."""
    for attempt in range(2):
        try:
            _ensure_db_once(force=attempt == 1)
            with closing(_get_db_connection()) as conn:
                cur = conn.cursor()
                cur.execute(
                    """
                    INSERT INTO mem(key, value, scope, tags, tags_search, created_at, last_used_at, expires_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET value=excluded.value,
                                                   scope=excluded.scope,
                                                   tags=excluded.tags,
                                                   tags_search=excluded.tags_search,
                                                   last_used_at=excluded.last_used_at,
                                                   expires_at=excluded.expires_at
                    """,
                    (
                        key_norm,
                        value_norm,
                        scope_norm,
                        tags_raw,
                        tags_search,
                        now_iso,
                        now_iso,
                        expires_at,
                    ),
                )
                conn.commit()
            return True
        except sqlite3.OperationalError:
            _reset_db_ready()
            if attempt == 0:
                time.sleep(0.1)
                continue
            raise
    return False


@pyscript_compile  # noqa: F821
def _memory_key_exists_db_sync(key_norm: str) -> bool:
    """Return True if a memory row already exists for key."""
    for attempt in range(2):
        try:
            _ensure_db_once(force=attempt == 1)
            with closing(_get_db_connection()) as conn:
                cur = conn.cursor()
                row = cur.execute(
                    "SELECT 1 FROM mem WHERE key = ? LIMIT 1",
                    (key_norm,),
                ).fetchone()
                return row is not None
        except sqlite3.OperationalError:
            _reset_db_ready()
            if attempt == 0:
                time.sleep(0.1)
                continue
            raise
    return False


@pyscript_compile  # noqa: F821
def _memory_get_db_sync(key_norm: str) -> tuple[str, dict[str, Any] | None]:
    """Fetch a memory by key, updating access time and handling expiry."""
    for attempt in range(2):
        try:
            _ensure_db_once(force=attempt == 1)
            with closing(_get_db_connection()) as conn:
                cur = conn.cursor()
                expired, row = _fetch_with_expiry(cur, key_norm)
                if row is None:
                    return "not_found", None
                row_data = {
                    "key": row["key"],
                    "value": row["value"],
                    "scope": row["scope"],
                    "tags": row["tags"],
                    "created_at": row["created_at"],
                    "last_used_at": row["last_used_at"],
                    "expires_at": row["expires_at"],
                }
                if expired:
                    return "expired", row_data
                last_used_iso = _utcnow_iso()
                cur.execute(
                    "UPDATE mem SET last_used_at=? WHERE key=?",
                    (last_used_iso, key_norm),
                )
                conn.commit()
            row_data["last_used_at"] = last_used_iso
            return "ok", row_data
        except sqlite3.OperationalError:
            _reset_db_ready()
            if attempt == 0:
                time.sleep(0.1)
                continue
            raise
    return "error", None


@pyscript_compile  # noqa: F821
def _memory_search_db_sync(query: str, limit: int) -> list[dict[str, Any]]:
    """Run the primary search query, returning matching memory rows."""
    normalized_query = _normalize_search_text(query)
    query_tokens = set(normalized_query.split()) if normalized_query else set()
    for attempt in range(2):
        try:
            _ensure_db_once(force=attempt == 1)
            with closing(_get_db_connection()) as conn:
                cur = conn.cursor()
                found_by_key: dict[str, sqlite3.Row] = {}
                total_rows: list[sqlite3.Row] = []
                match_variants = _build_fts_queries(query)

                for mv in match_variants:
                    if len(found_by_key) >= limit:
                        break
                    try:
                        fetched = cur.execute(
                            """
                            SELECT DISTINCT m.key,
                                            m.value,
                                            m.scope,
                                            m.tags,
                                            m.tags_search,
                                            m.created_at,
                                            m.last_used_at,
                                            m.expires_at,
                                            mem_fts.rank AS rank
                            FROM mem_fts
                                     JOIN mem AS m
                                          ON m.id = mem_fts.rowid
                            WHERE mem_fts MATCH ?
                            ORDER BY rank, m.last_used_at DESC
                            LIMIT ?;
                            """,
                            (mv, limit),
                        ).fetchall()
                    except sqlite3.Error as error:
                        log.warning(f"FTS variant failed: {error}")  # noqa: F821
                        continue
                    for row in fetched:
                        key = row["key"]
                        if key not in found_by_key:
                            found_by_key[key] = row
                            total_rows.append(row)
                        if len(found_by_key) >= limit:
                            break
                if not total_rows:
                    # Fallback to LIKE using normalized query to match normalized columns (key, tags)
                    # We prioritize normalized matching because key/tags are the primary search vectors.
                    like_q = f"%{normalized_query}%"
                    total_rows = cur.execute(
                        """
                        SELECT DISTINCT m.key,
                                        m.value,
                                        m.scope,
                                        m.tags,
                                        m.tags_search,
                                        m.created_at,
                                        m.last_used_at,
                                        m.expires_at,
                                        NULL AS rank
                        FROM mem AS m
                        WHERE m.value LIKE ?
                           OR m.tags LIKE ?
                           OR m.tags_search LIKE ?
                           OR m.key LIKE ?
                        ORDER BY m.last_used_at DESC
                        LIMIT ?;
                        """,
                        (like_q, like_q, like_q, like_q, limit),
                    ).fetchall()
            results: list[dict[str, Any]] = []
            for row in total_rows:
                candidate_source = row["tags_search"] or _normalize_tags(row["tags"])
                candidate_tokens = {
                    token for token in candidate_source.split() if token
                }
                match_score = _calculate_match_score(
                    query_tokens, candidate_tokens, row["rank"]
                )
                results.append(
                    {
                        "key": row["key"],
                        "value": row["value"],
                        "scope": row["scope"],
                        "tags": row["tags"],
                        "created_at": row["created_at"],
                        "last_used_at": row["last_used_at"],
                        "expires_at": row["expires_at"],
                        "match_score": match_score,
                    }
                )
            return results
        except sqlite3.OperationalError:
            _reset_db_ready()
            if attempt == 0:
                time.sleep(0.1)
                continue
            raise
    return []


@pyscript_compile  # noqa: F821
def _memory_forget_db_sync(key_norm: str) -> int:
    """Delete a memory row by key and return the number of rows removed."""
    for attempt in range(2):
        try:
            _ensure_db_once(force=attempt == 1)
            with closing(_get_db_connection()) as conn:
                cur = conn.cursor()
                cur.execute("DELETE FROM mem WHERE key=?", (key_norm,))
                rowcount = getattr(cur, "rowcount", -1)
                deleted = rowcount if rowcount and rowcount > 0 else 0
                conn.commit()
            return deleted
        except sqlite3.OperationalError:
            _reset_db_ready()
            if attempt == 0:
                time.sleep(0.1)
                continue
            raise
    return 0


@pyscript_compile  # noqa: F821
def _memory_purge_expired_db_sync(grace_days: int = 0) -> int:
    """Remove expired rows older than the grace period and report how many were purged."""
    grace = max(int(grace_days), 0)
    cutoff_dt = datetime.now(UTC) - timedelta(days=grace)
    cutoff_iso = cutoff_dt.isoformat()
    for attempt in range(2):
        try:
            _ensure_db_once(force=attempt == 1)
            with closing(_get_db_connection()) as conn:
                cur = conn.cursor()
                cur.execute(
                    "DELETE FROM mem WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (cutoff_iso,),
                )
                rowcount = getattr(cur, "rowcount", -1)
                removed = rowcount if rowcount and rowcount > 0 else 0
                conn.commit()
            return removed
        except sqlite3.OperationalError:
            _reset_db_ready()
            if attempt == 0:
                time.sleep(0.1)
                continue
            raise
    return 0


@pyscript_compile  # noqa: F821
def _memory_reindex_fts_db_sync() -> tuple[int, int]:
    """Rebuild the FTS index, returning counts before and after the rebuild."""
    for attempt in range(2):
        try:
            _ensure_db_once(force=attempt == 1)
            with closing(_get_db_connection()) as conn:
                cur = conn.cursor()
                cur.execute("BEGIN IMMEDIATE")
                try:
                    cur.execute("SELECT COUNT(*) FROM mem_fts")
                    before = cur.fetchone()[0]
                except sqlite3.Error:
                    before = 0

                cur.execute("DROP TABLE IF EXISTS mem_fts")
                cur.execute(
                    """
                    CREATE VIRTUAL TABLE mem_fts USING fts5(
                        key, value, tags,
                        content='mem',
                        content_rowid='id',
                        tokenize = 'unicode61 remove_diacritics 2'
                    );
                    """
                )

                cur.executescript(
                    """
                    CREATE TRIGGER IF NOT EXISTS mem_ai
                        AFTER INSERT
                        ON mem
                    BEGIN
                        INSERT INTO mem_fts(rowid, key, value, tags)
                        VALUES (new.id,
                                new.key,
                                new.value,
                                new.tags_search);
                    END;

                    CREATE TRIGGER IF NOT EXISTS mem_ad
                        AFTER DELETE
                        ON mem
                    BEGIN
                        INSERT INTO mem_fts(mem_fts, rowid, key, value, tags)
                        VALUES ('delete', old.id, old.key, old.value, old.tags_search);
                    END;

                    CREATE TRIGGER IF NOT EXISTS mem_au
                        AFTER UPDATE OF key, value, tags_search
                        ON mem
                        WHEN (old.key IS NOT new.key)
                            OR (old.value IS NOT new.value)
                            OR (old.tags_search IS NOT new.tags_search)
                    BEGIN
                        INSERT INTO mem_fts(mem_fts, rowid, key, value, tags)
                        VALUES ('delete', old.id, old.key, old.value, old.tags_search);
                        INSERT INTO mem_fts(rowid, key, value, tags)
                        VALUES (new.id,
                                new.key,
                                new.value,
                                new.tags_search);
                    END;
                    """
                )

                cur.execute("INSERT INTO mem_fts(mem_fts) VALUES('rebuild')")
                cur.execute("SELECT COUNT(*) FROM mem_fts")
                after = cur.fetchone()[0]
                conn.commit()
            return before, after
        except sqlite3.OperationalError:
            _reset_db_ready()
            if attempt == 0:
                time.sleep(0.1)
                continue
            raise
    return 0, 0


@pyscript_compile  # noqa: F821
def _memory_health_check_db_sync() -> tuple[int, int, int]:
    """Return basic health counts (total, expired, FTS rows) for diagnostics."""
    for attempt in range(2):
        try:
            _ensure_db_once(force=attempt == 1)
            with closing(_get_db_connection()) as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM mem")
                rows = cur.fetchone()[0]
                now_iso = _utcnow_iso()
                cur.execute(
                    "SELECT COUNT(*) FROM mem WHERE expires_at IS NOT NULL AND expires_at < ?",
                    (now_iso,),
                )
                expired = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM mem_fts")
                fts_rows = cur.fetchone()[0]
            return rows, expired, fts_rows
        except sqlite3.OperationalError:
            _reset_db_ready()
            if attempt == 0:
                time.sleep(0.1)
                continue
            raise
    return 0, 0, 0


async def _memory_set_db(
    key_norm: str,
    value_norm: str,
    scope_norm: str,
    tags_raw: str,
    tags_search: str,
    now_iso: str,
    expires_at: str | None,
) -> bool:
    """Async wrapper around _memory_set_db_sync to keep writes off the event loop."""
    return await asyncio.to_thread(
        _memory_set_db_sync,
        key_norm,
        value_norm,
        scope_norm,
        tags_raw,
        tags_search,
        now_iso,
        expires_at,
    )


async def _memory_key_exists_db(key_norm: str) -> bool:
    """Async wrapper that checks key existence via _memory_key_exists_db_sync."""
    return await asyncio.to_thread(_memory_key_exists_db_sync, key_norm)


async def _memory_get_db(key_norm: str) -> tuple[str, dict[str, Any] | None]:
    """Async wrapper for _memory_get_db_sync handling DB access in a thread."""
    return await asyncio.to_thread(_memory_get_db_sync, key_norm)


async def _memory_search_db(query: str, limit: int) -> list[dict[str, Any]]:
    """Async wrapper that runs _memory_search_db_sync without blocking."""
    return await asyncio.to_thread(_memory_search_db_sync, query, limit)


async def _memory_forget_db(key_norm: str) -> int:
    """Async wrapper for _memory_forget_db_sync."""
    return await asyncio.to_thread(_memory_forget_db_sync, key_norm)


async def _memory_purge_expired_db(grace_days: int = 0) -> int:
    """Async wrapper for the purge helper supporting a grace window."""
    return await asyncio.to_thread(_memory_purge_expired_db_sync, grace_days)


async def _memory_reindex_fts_db() -> tuple[int, int]:
    """Async wrapper rebuilding the FTS index via _memory_reindex_fts_db_sync."""
    return await asyncio.to_thread(_memory_reindex_fts_db_sync)


async def _memory_health_check_db() -> tuple[int, int, int]:
    """Async wrapper running the health-check query in a thread."""
    return await asyncio.to_thread(_memory_health_check_db_sync)


@service(supports_response="only")  # noqa: F821
async def memory_set(
    key: str,
    value: str,
    scope: str = "user",
    expiration_days: int = 180,
    tags: str = "",
    force_new: bool = False,
):
    """
    yaml
    name: Memory Set
    description: Create or update a memory entry with optional expiration and tags. When creating a brand-new key, tag overlaps trigger a duplicate_tags error; successful responses include key_exists to clarify whether the entry was updated or newly inserted.
    fields:
      key:
        name: Key
        description: Unique key of the entry.
        required: true
        example: "car_parking_slot"
        selector:
          text:
      value:
        name: Value
        description: Value to store (string or JSON-encoded structure).
        required: true
        example: "Column B2E9"
        selector:
          text:
      scope:
        name: Scope
        description: Arbitrary grouping label for organization.
        default: user
        example: user
        selector:
          select:
            options:
              - user
              - household
              - session
      expiration_days:
        name: Expiration (days)
        description: Days until expiration; 0 keeps forever.
        default: 180
        example: 30
        selector:
          number:
            min: 0
            max: 3650
            mode: box
      tags:
        name: Tags
        description: Optional space-separated tags for improved search.
        example: "car parking slot"
        selector:
          text:
      force_new:
        name: Force New
        description: Proceed even when tags overlap with other entries.
        example: false
        selector:
          boolean:
    """
    key_norm = _normalize_key(key)
    if not key_norm or value is None:
        _set_result(
            "error",
            op="set",
            key=key_norm or "",
            error="key_or_value_missing",
        )
        log.error("memory_set: missing key or value")  # noqa: F821
        return {
            "status": "error",
            "op": "set",
            "key": key_norm or "",
            "error": "key_or_value_missing",
        }

    try:
        expiration_days_i = int(expiration_days)
    except TypeError, ValueError:
        expiration_days_i = 0
    if expiration_days_i < 0:
        expiration_days_i = 0
    if expiration_days_i > EXPIRATION_MAX_DAYS:
        expiration_days_i = EXPIRATION_MAX_DAYS

    if isinstance(force_new, str):
        force_new_bool = force_new.strip().lower() in {"1", "true", "yes", "y", "on"}
    else:
        force_new_bool = bool(force_new)
    forced_duplicate_override = False

    try:
        scope_norm = ("" if scope is None else str(scope).strip()).lower() or "user"
        value_norm = _normalize_value(value)
        tags_raw = _normalize_value(tags) if tags else _normalize_value(key)
        tags_search = _normalize_tags(tags_raw)

        now = datetime.now(UTC)
        now_iso = now.isoformat()
        expires_at = (
            (now + timedelta(days=expiration_days_i)).isoformat()
            if expiration_days_i
            else None
        )

        key_exists = await _memory_key_exists_db(key_norm)

        duplicate_matches: list[tuple[dict[str, Any], float]] = []
        if not key_exists and tags_search:
            duplicate_matches = await _search_tag_candidates(
                tags_search,
                exclude_keys={key_norm},
                limit=CANDIDATE_CHECK_LIMIT,
                log_context="set: duplicate lookup",
            )

        duplicate_options: list[dict[str, Any]] = []
        if duplicate_matches:
            duplicate_options = [
                _condense_candidate_for_selection(match, score=score)
                for match, score in duplicate_matches
            ]

        if duplicate_options and not key_exists:
            if not force_new_bool:
                _set_result(
                    "error",
                    op="set",
                    key=key_norm,
                    tags=tags_raw,
                    error="duplicate_tags",
                    matches=duplicate_options,
                )
                log.error("memory_set: duplicate tags detected, refusing to overwrite")  # noqa: F821
                return {
                    "status": "error",
                    "op": "set",
                    "key": key_norm,
                    "tags": tags_raw,
                    "error": "duplicate_tags",
                    "matches": duplicate_options,
                }
            forced_duplicate_override = True
            log.warning("memory_set: duplicate tags override forced by force_new")  # noqa: F821

        ok_db = await _memory_set_db(
            key_norm=key_norm,
            value_norm=value_norm,
            scope_norm=scope_norm,
            tags_raw=tags_raw,
            tags_search=tags_search,
            now_iso=now_iso,
            expires_at=expires_at,
        )

        if not ok_db:
            return {
                "status": "error",
                "op": "set",
                "key": key_norm,
                "error": "memory_set_db returned False",
            }

        result_details: dict[str, Any] = {
            "value": value_norm,
            "scope": scope_norm,
            "tags": tags_raw,
            "expires_at": expires_at,
            "key_exists": key_exists,
            "force_new_applied": forced_duplicate_override,
        }
        if forced_duplicate_override:
            result_details["duplicate_matches"] = duplicate_options

        _set_result("ok", op="set", key=key_norm, **result_details)

        response: dict[str, Any] = {
            "status": "ok",
            "op": "set",
            "key": key_norm,
            "value": value_norm,
            "scope": scope_norm,
            "tags": tags_raw,
            "expires_at": expires_at,
            "key_exists": key_exists,
            "force_new_applied": forced_duplicate_override,
        }
        if forced_duplicate_override:
            response["duplicate_matches"] = duplicate_options
        return response
    except Exception as e:
        log.error(f"memory_set failed: {e}")  # noqa: F821
        _set_result("error", op="set", key=key_norm, error=str(e))
        return {"status": "error", "op": "set", "key": key_norm, "error": str(e)}


@service(supports_response="only")  # noqa: F821
async def memory_get(key: str):
    """
    yaml
    name: Memory Get
    description: Get a memory entry by key, updating last_used_at; returns `ambiguous` when similar suggestions exist and `status=expired` with the stored payload so callers can reuse it when the record has expired.
    fields:
      key:
        name: Key
        description: Key to fetch.
        required: true
        example: "car_parking_slot"
        selector:
          text:
    """
    key_norm = _normalize_key(key)
    if not key_norm:
        _set_result("error", op="get", key=key or "", error="key_missing")
        return {
            "status": "error",
            "op": "get",
            "key": key or "",
            "error": "key_missing",
        }

    try:
        status, payload = await _memory_get_db(key_norm)
    except Exception as e:
        log.error(f"memory_get failed: {e}")  # noqa: F821
        _set_result("error", op="get", key=key_norm, error=str(e))
        return {"status": "error", "op": "get", "key": key_norm, "error": str(e)}

    if status == "expired":
        payload = payload or {"key": key_norm}
        attrs: dict[str, Any] = {**payload, "expired": True}
        if "error" not in attrs:
            attrs["error"] = "expired"
        _set_result("expired", op="get", **attrs)
        return {"status": "expired", "op": "get", **attrs}

    if status == "not_found":
        matches = await _find_tag_matches_for_query(
            key or key_norm, exclude_keys={key_norm}
        )
        error_code = "ambiguous" if matches else "not_found"
        _set_result(
            "error",
            op="get",
            key=key_norm,
            error=error_code,
            matches=matches,
        )
        return {
            "status": "error",
            "op": "get",
            "key": key_norm,
            "error": error_code,
            "matches": matches,
        }

    res = payload or {}
    _set_result("ok", op="get", **res)
    return {"status": "ok", "op": "get", **res}


@service(supports_response="only")  # noqa: F821
async def memory_search(query: str, limit: int = 5):
    """
    yaml
    name: Memory Search
    description: Search entries across key/value/tags using FTS; falls back to LIKE if MATCH fails.
    fields:
      query:
        name: Query
        description: FTS search query.
        required: true
        example: "parking slot"
        selector:
          text:
      limit:
        name: Limit
        description: Maximum number of results to return.
        default: 5
        example: 5
        selector:
          number:
            min: 1
            max: 50
    """
    if not query:
        _set_result("error", op="search", query=query or "", error="query_missing")
        return {
            "status": "error",
            "op": "search",
            "query": query or "",
            "error": "query_missing",
        }

    try:
        lim = int(limit)
    except TypeError, ValueError:
        lim = 5
    if lim < 1:
        lim = 1
    if lim > SEARCH_LIMIT_MAX:
        lim = SEARCH_LIMIT_MAX

    try:
        results = await _memory_search_db(query, lim)
    except Exception as e:
        log.error(f"memory_search failed: {e}")  # noqa: F821
        _set_result("error", op="search", query=query, error=str(e))
        return {"status": "error", "op": "search", "query": query, "error": str(e)}

    _set_result(
        "ok",
        op="search",
        query=query,
        count=len(results),
        results=results,
    )
    return {
        "status": "ok",
        "op": "search",
        "query": query,
        "count": len(results),
        "results": results,
    }


@service(supports_response="only")  # noqa: F821
async def memory_forget(key: str):
    """
    yaml
    name: Memory Forget
    description: Delete a memory entry by key and remove it from the FTS index; returns `ambiguous` when nothing is removed but suggestions exist.
    fields:
      key:
        name: Key
        description: Key to delete.
        required: true
        example: "car_parking_slot"
        selector:
          text:
    """
    key_norm = _normalize_key(key)
    if not key_norm:
        _set_result("error", op="forget", key=key or "", error="key_missing")
        return {
            "status": "error",
            "op": "forget",
            "key": key or "",
            "error": "key_missing",
        }
    try:
        deleted = await _memory_forget_db(key_norm)
    except Exception as e:
        log.error(f"memory_forget failed: {e}")  # noqa: F821
        _set_result("error", op="forget", key=key_norm, error=str(e))
        return {"status": "error", "op": "forget", "key": key_norm, "error": str(e)}

    if deleted == 0:
        matches = await _find_tag_matches_for_query(
            key or key_norm, exclude_keys={key_norm}
        )
        error_code = "ambiguous" if matches else "not_found"
        _set_result(
            "error",
            op="forget",
            key=key_norm,
            error=error_code,
            matches=matches,
        )
        return {
            "status": "error",
            "op": "forget",
            "key": key_norm,
            "error": error_code,
            "matches": matches,
        }

    _set_result("ok", op="forget", key=key_norm, deleted=deleted)
    return {"status": "ok", "op": "forget", "key": key_norm, "deleted": deleted}


@service(supports_response="only")  # noqa: F821
async def memory_purge_expired(grace_days: int | None = None):
    """
    yaml
    name: Memory Purge Expired
    description: Remove expired rows older than the provided grace period; manual calls default to 0 days while daily housekeeping uses HOUSEKEEPING_GRACE_DAYS.
    fields:
      grace_days:
        name: Grace Days
        description: Extra days to keep expired entries before deletion (clamped to HOUSEKEEPING_GRACE_MAX_DAYS).
        default: 0
        example: 10
        selector:
          number:
            min: 0
            max: 365
    """
    if grace_days is None:
        grace = 0
    else:
        try:
            grace = int(grace_days)
        except TypeError, ValueError:
            grace = 0
    if grace < 0:
        grace = 0
    if grace > HOUSEKEEPING_GRACE_MAX_DAYS:
        grace = HOUSEKEEPING_GRACE_MAX_DAYS

    try:
        removed = await _memory_purge_expired_db(grace)
    except Exception as e:
        log.error(f"memory_purge_expired failed: {e}")  # noqa: F821
        _set_result("error", op="purge_expired", grace_days=grace, error=str(e))
        return {
            "status": "error",
            "op": "purge_expired",
            "grace_days": grace,
            "error": str(e),
        }

    _set_result("ok", op="purge_expired", grace_days=grace, removed=removed)
    return {
        "status": "ok",
        "op": "purge_expired",
        "grace_days": grace,
        "removed": removed,
    }


@service(supports_response="only")  # noqa: F821
async def memory_reindex_fts():
    """
    yaml
    name: Memory Reindex FTS
    description: Rebuild the FTS index from the main table. Useful when mem_fts is empty or out of sync.
    """
    try:
        before, after = await _memory_reindex_fts_db()
    except Exception as e:
        log.error(f"memory_reindex_fts failed: {e}")  # noqa: F821
        _set_result("error", op="reindex_fts", error=str(e))
        return {"status": "error", "op": "reindex_fts", "error": str(e)}

    _set_result("ok", op="reindex_fts", removed=before, inserted=after)
    return {
        "status": "ok",
        "op": "reindex_fts",
        "removed": before,
        "inserted": after,
    }


@time_trigger("startup")  # noqa: F821
@service(supports_response="only")  # noqa: F821
async def memory_health_check():
    """
    yaml
    name: Memory Health Check
    description: Run a quick health check (counts, expired, FTS rows), update the sensor, and return details.
    """
    _ensure_result_entity_name(force=True)
    try:
        rows, expired, fts_rows = await _memory_health_check_db()
        ts = _utcnow_iso()
        _set_result(
            "idle",
            op="health",
            db_path=DB_PATH,
            rows=rows,
            expired=expired,
            fts_rows=fts_rows,
            ts=ts,
        )
        log.info(  # noqa: F821
            f"memory.py health: rows={rows}, expired={expired}, fts_rows={fts_rows}"
        )
        return {
            "status": "ok",
            "op": "health",
            "db_path": DB_PATH,
            "rows": rows,
            "expired": expired,
            "fts_rows": fts_rows,
            "ts": ts,
        }
    except Exception as e:
        log.error(f"memory_health_check failed: {e}")  # noqa: F821
        _set_result("error", op="health", error=str(e))
        return {"status": "error", "op": "health", "error": str(e)}


@time_trigger("cron(0 3 * * *)")  # noqa: F821
async def memory_daily_housekeeping():
    """Daily housekeeping: purge entries older than HOUSEKEEPING_GRACE_DAYS and tidy the FTS index."""
    try:
        await memory_purge_expired(grace_days=HOUSEKEEPING_GRACE_DAYS)
    except Exception as e:
        log.error(f"memory_daily_housekeeping failed: {e}")  # noqa: F821
