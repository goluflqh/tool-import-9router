"""
9router Import Tool - Local Server
Auto-detect 9router SQLite database and serve import UI.
"""

import base64
import json
import os
import re
import shutil
import sqlite3
import uuid
import webbrowser
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

PORT = 9876
PROVIDER = "codex"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BACKUP_ROOT = os.path.join(SCRIPT_DIR, "backups")
CODEX_CONFIG_PATH = os.path.join(os.path.expanduser("~"), ".codex", "config.toml")
CODEX_AUTH_PATH = os.path.join(os.path.expanduser("~"), ".codex", "auth.json")
LEGACY_DB_JSON = os.path.join(os.environ.get("APPDATA", ""), "9router", "db.json")
CLIPROXY_CANDIDATES = [
    os.path.join("D:\\", "CLIProxyAPI"),
    os.path.join(os.path.expanduser("~"), "CLIProxyAPI"),
    os.path.join(os.path.expanduser("~"), "Downloads", "CLIProxyAPI"),
]

# Keep Codex config portable across router9 and cliproxy: both can use the
# plain name, while 9router resolves it through this alias.
DEFAULT_MODEL_ALIASES = {
    "gpt-5.5": "cx/gpt-5.5",
}


def find_sqlite():
    candidates = [
        os.path.join(os.environ.get("APPDATA", ""), "9router", "db", "data.sqlite"),
        os.path.join(os.path.expanduser("~"), "AppData", "Roaming", "9router", "db", "data.sqlite"),
        os.path.join(os.path.expanduser("~"), ".config", "9router", "db", "data.sqlite"),
        os.path.join(os.path.expanduser("~"), "Library", "Application Support", "9router", "db", "data.sqlite"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


SQLITE_PATH = find_sqlite()


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def backup_path(path, label=None):
    if not path or not os.path.exists(path):
        return None
    os.makedirs(BACKUP_ROOT, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = label or os.path.basename(path)
    bk = os.path.join(BACKUP_ROOT, "{}.backup-{}".format(base, ts))
    shutil.copy2(path, bk)
    return bk


def backup_sqlite():
    return backup_path(SQLITE_PATH, "data.sqlite")


def connect_db():
    return sqlite3.connect(SQLITE_PATH, timeout=10)


def parse_json(value, fallback=None):
    if fallback is None:
        fallback = {}
    if not value:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return fallback


def decode_jwt_payload(token):
    if not token or not isinstance(token, str) or "." not in token:
        return {}
    try:
        part = token.split(".")[1]
        part += "=" * ((4 - len(part) % 4) % 4)
        return json.loads(base64.urlsafe_b64decode(part.encode("ascii")).decode("utf-8"))
    except Exception:
        return {}


def find_cliproxy_root():
    for root in CLIPROXY_CANDIDATES:
        if os.path.exists(os.path.join(root, "config.yaml")) and os.path.isdir(root):
            return root
    return None


def cliproxy_auth_dir():
    root = find_cliproxy_root()
    if not root:
        return None
    auth_dir = os.path.join(root, "runtime-auths")
    config = os.path.join(root, "config.yaml")
    try:
        with open(config, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("auth-dir:"):
                    raw = line.split(":", 1)[1].split("#", 1)[0].strip().strip('"').strip("'")
                    if raw:
                        raw = os.path.expanduser(raw)
                        auth_dir = raw if os.path.isabs(raw) else os.path.abspath(os.path.join(root, raw))
                    break
    except Exception:
        pass
    return auth_dir


def backup_cliproxy_auths():
    auth_dir = cliproxy_auth_dir()
    if not auth_dir or not os.path.isdir(auth_dir):
        return None
    os.makedirs(BACKUP_ROOT, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(BACKUP_ROOT, "cliproxy-runtime-auths.backup-{}".format(ts))
    os.makedirs(dest, exist_ok=True)
    for name in os.listdir(auth_dir):
        src = os.path.join(auth_dir, name)
        if os.path.isfile(src) and name.lower().endswith(".json"):
            shutil.copy2(src, os.path.join(dest, name))
    return dest


def desired_model_aliases():
    aliases = {}
    if LEGACY_DB_JSON and os.path.exists(LEGACY_DB_JSON):
        try:
            with open(LEGACY_DB_JSON, "r", encoding="utf-8") as f:
                legacy = json.load(f)
            legacy_aliases = legacy.get("modelAliases")
            if isinstance(legacy_aliases, dict):
                aliases.update({str(k): str(v) for k, v in legacy_aliases.items() if k and v})
        except Exception:
            pass
    aliases.update(DEFAULT_MODEL_ALIASES)
    return aliases


def get_model_aliases(db=None):
    if not SQLITE_PATH or not os.path.exists(SQLITE_PATH):
        return {}
    owns_db = db is None
    db = db or connect_db()
    try:
        rows = db.execute("SELECT key, value FROM kv WHERE scope='modelAliases'").fetchall()
        return {k: parse_json(v, v) for k, v in rows}
    finally:
        if owns_db:
            db.close()


def ensure_model_aliases(db=None):
    if not SQLITE_PATH or not os.path.exists(SQLITE_PATH):
        return {"ok": False, "changed": False, "error": "9router database not found", "aliases": desired_model_aliases()}

    owns_db = db is None
    db = db or connect_db()
    aliases = desired_model_aliases()
    changed = []
    try:
        current = get_model_aliases(db)
        for alias, model in aliases.items():
            if current.get(alias) != model:
                db.execute(
                    "INSERT OR REPLACE INTO kv(scope, key, value) VALUES('modelAliases', ?, ?)",
                    (alias, json.dumps(model, ensure_ascii=False)),
                )
                changed.append({"alias": alias, "model": model})
        if owns_db:
            db.commit()
        return {"ok": True, "changed": bool(changed), "changedAliases": changed, "aliases": aliases}
    finally:
        if owns_db:
            db.close()


def token_summary(data):
    data = data or {}
    rt = data.get("refreshToken") or ""
    at = data.get("accessToken") or ""
    exp = data.get("expiresAt") or ""
    status = "unknown"
    seconds_left = None
    if exp:
        try:
            dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
            seconds_left = int((dt - datetime.now(timezone.utc)).total_seconds())
            if seconds_left <= 0:
                status = "expired"
            elif seconds_left <= 1800:
                status = "expiring_soon"
            else:
                status = "valid"
        except Exception:
            status = "unknown"
    elif at:
        status = "no_expiry"
    return {
        "hasAccessToken": bool(at),
        "hasRefreshToken": bool(rt),
        "accessStatus": status,
        "accessSecondsLeft": seconds_left,
    }


def redact_data(data):
    data = dict(data or {})
    for key in ("accessToken", "refreshToken", "idToken"):
        if data.get(key):
            val = str(data[key])
            data[key] = "{}...{}".format(val[:6], val[-4:]) if len(val) > 14 else "***"
    data["tokenStatus"] = token_summary(data)
    return data


def get_connections(include_secrets=False):
    if not SQLITE_PATH or not os.path.exists(SQLITE_PATH):
        return []
    db = connect_db()
    cur = db.cursor()
    cur.execute(
        "SELECT id, provider, authType, name, email, priority, isActive, data, createdAt, updatedAt "
        "FROM providerConnections WHERE provider=? ORDER BY priority",
        (PROVIDER,),
    )
    cols = [d[0] for d in cur.description]
    result = []
    for r in cur.fetchall():
        row = dict(zip(cols, r))
        data = parse_json(row.get("data"), {})
        row["isActive"] = bool(row.get("isActive"))
        row["data"] = data if include_secrets else redact_data(data)
        result.append(row)
    db.close()
    return result


def _nested(conn, key, default=""):
    if key in conn and conn.get(key) is not None:
        return conn.get(key)
    data = conn.get("data")
    if isinstance(data, dict) and data.get(key) is not None:
        return data.get(key)
    return default


def _provider_specific(conn):
    psd = _nested(conn, "providerSpecificData", {})
    return psd if isinstance(psd, dict) else {}


def _clean_refresh_token(value):
    raw = value or ""
    rejected_jwe = isinstance(raw, str) and raw.startswith("eyJ")
    if rejected_jwe:
        return "", True
    return raw, False


def _int_or_zero(value):
    return value if isinstance(value, int) else 0


def _token_field(data, camel, snake):
    return (data or {}).get(camel) or (data or {}).get(snake) or ""


def _build_data_blob(conn, existing_data, now, counters, fallback_data=None, fallback_source=""):
    existing_data = dict(existing_data or {})
    fallback_data = dict(fallback_data or {})
    access_token = _nested(conn, "accessToken", "") or _nested(conn, "access_token", "")
    raw_refresh = _nested(conn, "refreshToken", "") or _nested(conn, "refresh_token", "")
    refresh_token, rejected_jwe = _clean_refresh_token(raw_refresh)
    id_token = _nested(conn, "idToken", "") or _nested(conn, "id_token", "")
    expires_at = _nested(conn, "expiresAt", "") or _nested(conn, "expires", "") or _nested(conn, "expired", "")
    expires_in = _nested(conn, "expiresIn", None)
    fallback_refresh = _token_field(fallback_data, "refreshToken", "refresh_token")
    fallback_id = _token_field(fallback_data, "idToken", "id_token")
    fallback_exp = fallback_data.get("expiresAt") or fallback_data.get("expires") or fallback_data.get("expired") or ""

    if rejected_jwe:
        counters["rejectedSessionToken"] += 1
    if refresh_token:
        counters["providedRefresh"] += 1
    elif existing_data.get("refreshToken"):
        counters["preservedRefresh"] += 1
    elif fallback_refresh:
        counters["hydratedRefresh"] += 1

    provider_specific = dict(fallback_data.get("providerSpecificData") or {})
    provider_specific.update(existing_data.get("providerSpecificData") or {})
    for key, value in _provider_specific(conn).items():
        if value not in (None, ""):
            provider_specific[key] = value
    payload = decode_jwt_payload(access_token)
    auth = payload.get("https://api.openai.com/auth") or {}
    if conn.get("account_id") or auth.get("chatgpt_account_id"):
        provider_specific.setdefault("chatgptAccountId", conn.get("account_id") or auth.get("chatgpt_account_id"))
    if auth.get("chatgpt_plan_type"):
        provider_specific.setdefault("chatgptPlanType", auth.get("chatgpt_plan_type"))

    data_blob = {
        "accessToken": access_token or existing_data.get("accessToken") or "",
        "refreshToken": refresh_token or existing_data.get("refreshToken") or fallback_refresh or "",
        "idToken": id_token or existing_data.get("idToken") or fallback_id or "",
        "expiresAt": expires_at or existing_data.get("expiresAt") or fallback_exp or "",
        "expiresIn": _int_or_zero(expires_in) or _int_or_zero(existing_data.get("expiresIn")),
        "testStatus": _nested(conn, "testStatus", "") or existing_data.get("testStatus") or "active",
        "lastUsedAt": _nested(conn, "lastUsedAt", "") or existing_data.get("lastUsedAt") or now,
        "consecutiveUseCount": existing_data.get("consecutiveUseCount", 0),
        "backoffLevel": 0,
        "providerSpecificData": provider_specific,
        "lastError": None,
        "lastErrorAt": None,
    }

    final = token_summary(data_blob)
    if not final["hasRefreshToken"]:
        counters["missingRefresh"] += 1
    if final["hasAccessToken"] and not final["hasRefreshToken"]:
        counters["accessOnly"] += 1
    if final["accessStatus"] == "expired":
        counters["expiredAccess"] += 1
    elif final["accessStatus"] == "expiring_soon":
        counters["expiringSoonAccess"] += 1

    return data_blob, {
        "hasRefreshToken": final["hasRefreshToken"],
        "refreshStatus": "provided" if refresh_token else ("preserved" if existing_data.get("refreshToken") else ("hydrated" if fallback_refresh else "missing")),
        "refreshSource": "input" if refresh_token else ("9router" if existing_data.get("refreshToken") else (fallback_source if fallback_refresh else "")),
        "accessStatus": final["accessStatus"],
        "rejectedSessionToken": rejected_jwe,
    }


def import_connections(connections):
    if not SQLITE_PATH or not os.path.exists(SQLITE_PATH):
        return 0, 0, ["9router database not found"], {}, {"ok": False}

    backup_sqlite()
    db = connect_db()
    cur = db.cursor()
    cur.execute(
        "SELECT id, provider, authType, name, email, priority, isActive, data, createdAt, updatedAt "
        "FROM providerConnections WHERE provider=?",
        (PROVIDER,),
    )
    cols = [d[0] for d in cur.description]
    existing_map = {}
    for r in cur.fetchall():
        row = dict(zip(cols, r))
        email_key = (row.get("email") or row.get("name") or "").lower().strip()
        if email_key:
            row["data"] = parse_json(row.get("data"), {})
            existing_map[email_key] = row

    inserted = 0
    updated = 0
    errors = []
    details = []
    counters = {
        "providedRefresh": 0,
        "preservedRefresh": 0,
        "hydratedRefresh": 0,
        "missingRefresh": 0,
        "accessOnly": 0,
        "rejectedSessionToken": 0,
        "expiredAccess": 0,
        "expiringSoonAccess": 0,
    }
    now = now_iso()
    refresh_sources = _refresh_sources()

    try:
        with db:
            for conn in connections:
                email_val = (conn.get("email") or conn.get("name") or "").strip()
                email_key = email_val.lower()
                name = conn.get("name") or email_val or "ChatGPT Account"
                if not email_key:
                    errors.append("Missing email/name; skipped one connection")
                    continue

                old = existing_map.get(email_key)
                old_data = old.get("data") if old else {}
                fallback = refresh_sources.get(email_key, {})
                data_blob, detail = _build_data_blob(
                    conn,
                    old_data,
                    now,
                    counters,
                    fallback_data=fallback.get("data"),
                    fallback_source=fallback.get("source", ""),
                )
                data_json = json.dumps(data_blob, ensure_ascii=False)

                if old:
                    cur.execute(
                        "UPDATE providerConnections "
                        "SET authType=?, name=?, email=?, isActive=?, data=?, updatedAt=? "
                        "WHERE id=? AND provider=?",
                        ("oauth", name, email_val, 1, data_json, now, old["id"], PROVIDER),
                    )
                    updated += 1
                    details.append({"email": email_val, "action": "updated", **detail})
                else:
                    cur.execute("SELECT MAX(priority) FROM providerConnections WHERE provider=?", (PROVIDER,))
                    max_pri = cur.fetchone()[0] or 0
                    new_id = str(uuid.uuid4())
                    cur.execute(
                        "INSERT INTO providerConnections "
                        "(id,provider,authType,name,email,priority,isActive,data,createdAt,updatedAt) "
                        "VALUES (?,?,?,?,?,?,?,?,?,?)",
                        (new_id, PROVIDER, "oauth", name, email_val, max_pri + 1, 1, data_json, now, now),
                    )
                    existing_map[email_key] = {"id": new_id, "priority": max_pri + 1, "data": data_blob}
                    inserted += 1
                    details.append({"email": email_val, "action": "inserted", **detail})

            alias_report = ensure_model_aliases(db)
    except Exception as e:
        db.close()
        return inserted, updated, [str(e)], counters, {"ok": False, "error": str(e)}

    db.close()
    counters["details"] = details
    return inserted, updated, errors, counters, alias_report


def delete_connection(conn_id):
    if not SQLITE_PATH or not os.path.exists(SQLITE_PATH):
        return False
    backup_sqlite()
    db = connect_db()
    cur = db.cursor()
    cur.execute("DELETE FROM providerConnections WHERE id=? AND provider=?", (conn_id, PROVIDER))
    deleted = cur.rowcount
    db.commit()
    db.close()
    return deleted > 0


def _time_score(value):
    if not value:
        return 0
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).timestamp()
    except Exception:
        return 0


def _dedupe_score(row):
    data = parse_json(row.get("data"), {})
    status = token_summary(data)
    seconds_left = status.get("accessSecondsLeft")
    if seconds_left is None:
        seconds_left = -10**12
    return (
        1 if status.get("hasRefreshToken") else 0,
        1 if row.get("isActive") else 0,
        1 if data.get("testStatus") == "active" else 0,
        seconds_left,
        _time_score(row.get("updatedAt")),
        -int(row.get("priority") or 0),
    )


def dedupe_connections():
    if not SQLITE_PATH or not os.path.exists(SQLITE_PATH):
        return {"ok": False, "removed": 0, "groups": [], "error": "9router database not found"}

    backup = backup_sqlite()
    db = connect_db()
    cur = db.cursor()
    cur.execute(
        "SELECT id, provider, authType, name, email, priority, isActive, data, createdAt, updatedAt "
        "FROM providerConnections WHERE provider=? ORDER BY priority",
        (PROVIDER,),
    )
    cols = [d[0] for d in cur.description]
    groups = {}
    for r in cur.fetchall():
        row = dict(zip(cols, r))
        key = (row.get("email") or row.get("name") or "").lower().strip()
        if key:
            groups.setdefault(key, []).append(row)

    removed_ids = []
    details = []
    try:
        with db:
            for email, rows in groups.items():
                if len(rows) < 2:
                    continue
                keep = max(rows, key=_dedupe_score)
                losers = [row for row in rows if row["id"] != keep["id"]]
                for row in losers:
                    cur.execute("DELETE FROM providerConnections WHERE id=? AND provider=?", (row["id"], PROVIDER))
                    removed_ids.append(row["id"])
                details.append({
                    "email": email,
                    "keptId": keep["id"],
                    "removed": len(losers),
                })

            if removed_ids:
                cur.execute("SELECT id FROM providerConnections WHERE provider=? ORDER BY priority, updatedAt", (PROVIDER,))
                for priority, (conn_id,) in enumerate(cur.fetchall(), start=1):
                    cur.execute("UPDATE providerConnections SET priority=? WHERE id=? AND provider=?", (priority, conn_id, PROVIDER))
    except Exception as e:
        db.close()
        return {"ok": False, "removed": len(removed_ids), "groups": details, "backup": backup, "error": str(e)}

    db.close()
    return {"ok": True, "removed": len(removed_ids), "groups": details, "backup": backup}


def export_codex_payload(include_secrets=True):
    conns = []
    for row in get_connections(include_secrets=include_secrets):
        data = row.pop("data", {}) or {}
        conns.append({**data, **row})
    return {
        "generatedAt": now_iso(),
        "note": "Codex provider connections export for 9router Import Tool. Avoid full DB import unless you know it replaces 9router state.",
        "providerConnections": conns,
        "modelAliases": {**get_model_aliases(), **desired_model_aliases()},
    }


def codex_auth_status():
    if not os.path.exists(CODEX_AUTH_PATH):
        return {"ok": False, "path": CODEX_AUTH_PATH, "hasAccessToken": False, "hasRefreshToken": False}
    try:
        with open(CODEX_AUTH_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
        tokens = raw.get("tokens") if isinstance(raw.get("tokens"), dict) else raw
        return {
            "ok": True,
            "path": CODEX_AUTH_PATH,
            "hasAccessToken": bool(tokens.get("access_token") or tokens.get("accessToken")),
            "hasRefreshToken": bool(tokens.get("refresh_token") or tokens.get("refreshToken")),
            "modifiedAt": datetime.fromtimestamp(os.path.getmtime(CODEX_AUTH_PATH)).astimezone().isoformat(timespec="seconds"),
        }
    except Exception as e:
        return {"ok": False, "path": CODEX_AUTH_PATH, "hasAccessToken": False, "hasRefreshToken": False, "error": str(e)}


def codex_auth_connection():
    if not os.path.exists(CODEX_AUTH_PATH):
        return None, "Codex auth.json not found"
    try:
        with open(CODEX_AUTH_PATH, "r", encoding="utf-8") as f:
            raw = json.load(f)
    except Exception as e:
        return None, "Cannot read Codex auth.json: {}".format(str(e))

    tokens = raw.get("tokens") if isinstance(raw.get("tokens"), dict) else raw
    access_token = tokens.get("access_token") or tokens.get("accessToken") or ""
    refresh_token = tokens.get("refresh_token") or tokens.get("refreshToken") or ""
    id_token = tokens.get("id_token") or tokens.get("idToken") or ""
    if not access_token:
        return None, "Codex auth.json has no access token"

    payload = decode_jwt_payload(access_token)
    id_payload = decode_jwt_payload(id_token)
    auth = payload.get("https://api.openai.com/auth") or id_payload.get("https://api.openai.com/auth") or {}
    profile = payload.get("https://api.openai.com/profile") or id_payload.get("https://api.openai.com/profile") or {}
    email = (profile.get("email") or payload.get("email") or id_payload.get("email") or raw.get("email") or "").strip()
    if not email:
        return None, "Codex auth.json token did not expose an email"

    exp = ""
    if payload.get("exp"):
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat()
    account_id = tokens.get("account_id") or auth.get("chatgpt_account_id") or ""
    plan = auth.get("chatgpt_plan_type") or ""
    provider_specific = {}
    if account_id:
        provider_specific["chatgptAccountId"] = account_id
    if plan:
        provider_specific["chatgptPlanType"] = plan

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "id_token": id_token,
        "expires": exp,
        "lastUsedAt": raw.get("last_refresh") or now_iso(),
        "account_id": account_id,
        "email": email,
        "name": email,
        "providerSpecificData": provider_specific,
        "provider": PROVIDER,
        "authType": "oauth",
    }, None


def _cliproxy_safe_filename(value):
    value = (value or "account").strip().lower()
    value = re.sub(r"[^a-z0-9@._+-]+", "-", value)
    return value.strip("-") or "account"


def _cliproxy_existing_auths():
    auth_dir = cliproxy_auth_dir()
    out = {}
    if not auth_dir or not os.path.isdir(auth_dir):
        return out
    for name in os.listdir(auth_dir):
        if not name.lower().startswith("codex-") or not name.lower().endswith(".json"):
            continue
        path = os.path.join(auth_dir, name)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            email = (data.get("email") or "").lower().strip()
            if email:
                out[email] = {"path": path, "data": data}
        except Exception:
            continue
    return out


def _cliproxy_auth_records():
    auth_dir = cliproxy_auth_dir()
    records = []
    if not auth_dir or not os.path.isdir(auth_dir):
        return records
    for name in sorted(os.listdir(auth_dir)):
        if not name.lower().startswith("codex-") or not name.lower().endswith(".json"):
            continue
        path = os.path.join(auth_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            records.append({
                "email": "",
                "file": name,
                "path": path,
                "disabled": False,
                "expired": "",
                "lastRefresh": "",
                "modifiedAt": datetime.fromtimestamp(os.path.getmtime(path)).astimezone().isoformat(timespec="seconds"),
                "tokenStatus": {"hasAccessToken": False, "hasRefreshToken": False, "accessStatus": "unreadable", "accessSecondsLeft": None},
                "error": str(e),
            })
            continue
        ts = token_summary({
            "accessToken": data.get("access_token"),
            "refreshToken": data.get("refresh_token"),
            "expiresAt": data.get("expired"),
        })
        records.append({
            "email": (data.get("email") or "").lower().strip(),
            "file": name,
            "path": path,
            "disabled": bool(data.get("disabled")),
            "expired": data.get("expired") or "",
            "lastRefresh": data.get("last_refresh") or "",
            "modifiedAt": datetime.fromtimestamp(os.path.getmtime(path)).astimezone().isoformat(timespec="seconds"),
            "tokenStatus": ts,
            "error": "",
        })
    return records


def _cliproxy_auth_connections():
    conns = []
    for item in _cliproxy_existing_auths().values():
        data = item.get("data") or {}
        email = (data.get("email") or "").strip()
        if not email:
            continue
        conns.append({
            "email": email,
            "name": email,
            "access_token": data.get("access_token") or "",
            "refresh_token": data.get("refresh_token") or "",
            "id_token": data.get("id_token") or "",
            "expires": data.get("expired") or "",
            "lastUsedAt": data.get("last_refresh") or now_iso(),
            "account_id": data.get("account_id") or "",
            "provider": PROVIDER,
            "authType": "oauth",
        })
    return conns


def _refresh_source_key(conn):
    email = (conn.get("email") or conn.get("name") or "").lower().strip()
    if email:
        return email
    payload = decode_jwt_payload(_token_field(conn, "accessToken", "access_token"))
    profile = payload.get("https://api.openai.com/profile") or {}
    return (profile.get("email") or payload.get("email") or "").lower().strip()


def _refresh_sources(include_9router=False):
    sources = {}

    def add(source, conn):
        key = _refresh_source_key(conn)
        refresh_token = _token_field(conn, "refreshToken", "refresh_token")
        if key and refresh_token and key not in sources:
            sources[key] = {"source": source, "data": conn}

    if include_9router:
        for row in get_connections(include_secrets=True):
            data = dict(row.get("data") or {})
            data["email"] = row.get("email") or row.get("name") or ""
            add("9router", data)

    for conn in _cliproxy_auth_connections():
        add("cliproxy", conn)

    conn, err = codex_auth_connection()
    if conn and not err:
        add("codex-auth", conn)

    return sources


def refresh_preview(connections):
    router_sources = _refresh_sources(include_9router=True)
    local_sources = _refresh_sources(include_9router=False)
    rows = []
    for conn in connections:
        key = _refresh_source_key(conn)
        raw_refresh = _nested(conn, "refreshToken", "") or _nested(conn, "refresh_token", "")
        refresh_token, rejected_jwe = _clean_refresh_token(raw_refresh)
        source = "input" if refresh_token else ""
        if not source and key in router_sources:
            source = router_sources[key]["source"]
        if not source and key in local_sources:
            source = local_sources[key]["source"]
        rows.append({
            "email": conn.get("email") or conn.get("name") or key,
            "hasInputRefresh": bool(refresh_token),
            "rejectedSessionToken": rejected_jwe,
            "willHaveRefresh": bool(source),
            "source": source or "",
        })
    return rows


def _router_email_set():
    return set(
        (c.get("email") or c.get("name") or "").lower().strip()
        for c in get_connections(include_secrets=False)
        if (c.get("email") or c.get("name"))
    )


def cliproxy_accounts(include_paths=False):
    router_emails = _router_email_set()
    rows = []
    for rec in _cliproxy_auth_records():
        email = rec.get("email") or ""
        row = dict(rec)
        row["in9router"] = bool(email and email in router_emails)
        row["stale"] = bool(email and email not in router_emails)
        if not include_paths:
            row.pop("path", None)
        rows.append(row)
    return rows


def quarantine_stale_cliproxy_auths():
    auth_dir = cliproxy_auth_dir()
    if not auth_dir or not os.path.isdir(auth_dir):
        return {"ok": False, "moved": 0, "items": [], "error": "CLIProxy auth-dir not found"}
    stale = [a for a in cliproxy_accounts(include_paths=True) if a.get("stale") and a.get("path")]
    if not stale:
        return {"ok": True, "moved": 0, "items": [], "backup": None, "quarantineDir": ""}

    backup = backup_cliproxy_auths()
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    dest = os.path.join(BACKUP_ROOT, "cliproxy-stale-auths.quarantine-{}".format(ts))
    os.makedirs(dest, exist_ok=True)

    moved = []
    errors = []
    for item in stale:
        src = item["path"]
        name = os.path.basename(src)
        target = os.path.join(dest, name)
        try:
            shutil.move(src, target)
            moved.append({"email": item.get("email"), "file": name})
        except Exception as e:
            errors.append("{}: {}".format(name, str(e)))
    return {
        "ok": not errors,
        "moved": len(moved),
        "items": moved,
        "errors": errors,
        "backup": backup,
        "quarantineDir": dest,
    }


def _cliproxy_plan(conn, existing_data, payload):
    psd = _provider_specific(conn)
    plan = (
        psd.get("chatgptPlanType")
        or (existing_data or {}).get("plan")
        or (payload.get("https://api.openai.com/auth") or {}).get("chatgpt_plan_type")
        or "plus"
    )
    plan = str(plan).lower().strip()
    if plan not in ("plus", "team", "pro", "free", "enterprise"):
        return "plus"
    return plan


def _cliproxy_time(value, fallback=None):
    value = value or fallback or now_iso()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone().isoformat(timespec="seconds")
    except Exception:
        return str(value)


def _build_cliproxy_auth(conn, existing_data=None):
    existing_data = existing_data or {}
    access_token = _nested(conn, "accessToken", "") or _nested(conn, "access_token", "") or existing_data.get("access_token", "")
    refresh_token = _nested(conn, "refreshToken", "") or _nested(conn, "refresh_token", "") or existing_data.get("refresh_token", "")
    id_token = _nested(conn, "idToken", "") or _nested(conn, "id_token", "") or existing_data.get("id_token", "")
    payload = decode_jwt_payload(access_token)
    auth = payload.get("https://api.openai.com/auth") or {}
    profile = payload.get("https://api.openai.com/profile") or {}
    email = (
        conn.get("email")
        or conn.get("name")
        or existing_data.get("email")
        or profile.get("email")
        or payload.get("email")
        or ""
    ).strip()
    account_id = (
        _provider_specific(conn).get("chatgptAccountId")
        or auth.get("chatgpt_account_id")
        or conn.get("account_id")
        or existing_data.get("account_id")
        or ""
    )
    exp = _nested(conn, "expiresAt", "") or _nested(conn, "expires", "") or existing_data.get("expired", "")
    if not exp and payload.get("exp"):
        exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc).isoformat()
    plan = _cliproxy_plan(conn, existing_data, payload)
    return {
        "access_token": access_token,
        "account_id": account_id,
        "disabled": False,
        "email": email,
        "expired": _cliproxy_time(exp),
        "id_token": id_token,
        "last_refresh": _cliproxy_time(_nested(conn, "lastUsedAt", "") or existing_data.get("last_refresh", now_iso())),
        "refresh_token": refresh_token,
        "type": "codex",
    }, plan


def cliproxy_status():
    root = find_cliproxy_root()
    auth_dir = cliproxy_auth_dir()
    rows = cliproxy_accounts()
    expired = 0
    missing_refresh = 0
    stale = 0
    for item in rows:
        ts = item.get("tokenStatus") or {}
        if not ts.get("hasRefreshToken"):
            missing_refresh += 1
        if ts.get("accessStatus") == "expired":
            expired += 1
        if item.get("stale"):
            stale += 1
    return {
        "ok": bool(root and auth_dir and os.path.isdir(auth_dir)),
        "root": root or "",
        "authDir": auth_dir or "",
        "count": len(rows),
        "expiredAccess": expired,
        "missingRefresh": missing_refresh,
        "stale": stale,
        "accounts": rows,
    }


def import_cliproxy_connections(connections):
    auth_dir = cliproxy_auth_dir()
    if not auth_dir:
        return {"ok": False, "inserted": 0, "updated": 0, "errors": ["CLIProxyAPI folder not found"]}
    os.makedirs(auth_dir, exist_ok=True)
    backup = backup_cliproxy_auths()
    existing = _cliproxy_existing_auths()
    inserted = 0
    updated = 0
    missing_refresh = 0
    errors = []
    details = []

    for conn in connections:
        email_key = (conn.get("email") or conn.get("name") or "").lower().strip()
        old = existing.get(email_key) if email_key else None
        try:
            data, plan = _build_cliproxy_auth(conn, old["data"] if old else {})
            email = (data.get("email") or "").lower().strip()
            if not email:
                errors.append("Missing email/name; skipped one cliproxy auth")
                continue
            if not data.get("access_token"):
                errors.append("{}: missing access token".format(email))
                continue
            if not data.get("refresh_token"):
                missing_refresh += 1

            if old:
                path = old["path"]
                updated += 1
                action = "updated"
            else:
                name = "codex-{}-{}.json".format(_cliproxy_safe_filename(email), _cliproxy_safe_filename(plan))
                path = os.path.join(auth_dir, name)
                inserted += 1
                action = "inserted"

            with open(path, "w", encoding="utf-8", newline="\n") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
                f.write("\n")
            existing[email] = {"path": path, "data": data}
            details.append({"email": email, "file": os.path.basename(path), "action": action, "hasRefreshToken": bool(data.get("refresh_token"))})
        except Exception as e:
            errors.append("{}: {}".format(email_key or "unknown", str(e)))

    return {
        "ok": not errors,
        "inserted": inserted,
        "updated": updated,
        "errors": errors,
        "backup": backup,
        "authDir": auth_dir,
        "missingRefresh": missing_refresh,
        "details": details,
    }


def _find_top_level_end(lines):
    for i, line in enumerate(lines):
        if line.strip().startswith("["):
            return i
    return len(lines)


def _find_section(lines, name):
    header = "[{}]".format(name)
    start = None
    for i, line in enumerate(lines):
        if line.strip() == header:
            start = i + 1
            break
    if start is None:
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += "\n"
        lines.extend(["\n", header + "\n"])
        start = len(lines)
    end = len(lines)
    for j in range(start, len(lines)):
        if lines[j].strip().startswith("["):
            end = j
            break
    return start, end


def _set_toml_key(lines, start, end, key, value):
    pattern = re.compile(r"^\s*{}\s*=".format(re.escape(key)))
    replacement = '{} = "{}"'.format(key, value)
    for i in range(start, end):
        if pattern.match(lines[i]):
            newline = "\r\n" if lines[i].endswith("\r\n") else ("\n" if lines[i].endswith("\n") else "")
            new_line = replacement + newline
            if lines[i] != new_line:
                lines[i] = new_line
                return True
            return False
    lines.insert(end, replacement + "\n")
    return True


def repair_codex_config():
    if not os.path.exists(CODEX_CONFIG_PATH):
        return {"ok": False, "changed": False, "error": "Codex config.toml not found", "path": CODEX_CONFIG_PATH}
    with open(CODEX_CONFIG_PATH, "r", encoding="utf-8") as f:
        original = f.read()
    lines = original.splitlines(True)
    changed = False

    top_end = _find_top_level_end(lines)
    changed = _set_toml_key(lines, 0, top_end, "model", "gpt-5.5") or changed
    top_end = _find_top_level_end(lines)
    changed = _set_toml_key(lines, 0, top_end, "model_provider", "router9") or changed

    for profile, provider in (("profiles.router9", "router9"), ("profiles.cliproxy", "cliproxy")):
        start, end = _find_section(lines, profile)
        changed = _set_toml_key(lines, start, end, "model_provider", provider) or changed
        start, end = _find_section(lines, profile)
        changed = _set_toml_key(lines, start, end, "model", "gpt-5.5") or changed

    if not changed:
        return {"ok": True, "changed": False, "path": CODEX_CONFIG_PATH, "backup": None}
    backup = backup_path(CODEX_CONFIG_PATH, "codex-config.toml")
    with open(CODEX_CONFIG_PATH, "w", encoding="utf-8", newline="") as f:
        f.write("".join(lines))
    return {"ok": True, "changed": True, "path": CODEX_CONFIG_PATH, "backup": backup}


def get_codex_config_status():
    status = {"path": CODEX_CONFIG_PATH, "exists": os.path.exists(CODEX_CONFIG_PATH)}
    if not status["exists"]:
        return status
    try:
        with open(CODEX_CONFIG_PATH, "r", encoding="utf-8") as f:
            text = f.read()
        top = text.split("\n[", 1)[0]
        for key in ("model", "model_provider"):
            m = re.search(r"(?m)^\s*{}\s*=\s*\"([^\"]+)\"".format(re.escape(key)), top)
            status[key] = m.group(1) if m else None
        status["router9Ready"] = status.get("model") == "gpt-5.5" and status.get("model_provider") in ("router9", "cliproxy")
    except Exception as e:
        status["error"] = str(e)
    return status


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=SCRIPT_DIR, **kwargs)

    def log_message(self, fmt, *args):
        pass

    def _origin_allowed(self):
        origin = self.headers.get("Origin")
        if not origin:
            return True
        try:
            u = urlparse(origin)
            return u.scheme in ("http", "https") and u.hostname in ("localhost", "127.0.0.1", "::1") and u.port == PORT
        except Exception:
            return False

    def _json(self, data, status=200):
        if not self._origin_allowed():
            status = 403
            data = {"error": "Forbidden origin"}
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        origin = self.headers.get("Origin")
        if origin and self._origin_allowed():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Content-Length", len(body))
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
            pass

    def do_OPTIONS(self):
        if not self._origin_allowed():
            self.send_response(403)
            self.end_headers()
            return
        self.send_response(204)
        origin = self.headers.get("Origin")
        if origin:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length)
        return json.loads(body or b"{}")

    def do_GET(self):
        parsed = urlparse(self.path)
        p = parsed.path
        q = parse_qs(parsed.query)
        if p == "/api/health":
            aliases = get_model_aliases()
            self._json({
                "ok": True,
                "sqlite": bool(SQLITE_PATH and os.path.exists(SQLITE_PATH)),
                "path": SQLITE_PATH or "",
                "aliases": aliases,
                "desiredAliases": desired_model_aliases(),
                "codexConfig": get_codex_config_status(),
                "codexAuth": codex_auth_status(),
                "cliproxy": cliproxy_status(),
            })
            return
        if p == "/api/connections":
            include_secrets = q.get("secrets", ["0"])[0] == "1"
            c = get_connections(include_secrets=include_secrets)
            self._json({"connections": c, "count": len(c), "secrets": include_secrets})
            return
        if p == "/api/export":
            include_secrets = q.get("secrets", ["1"])[0] == "1"
            self._json(export_codex_payload(include_secrets=include_secrets))
            return
        if p == "/api/cliproxy/status":
            self._json(cliproxy_status())
            return
        if p == "/api/cliproxy/accounts":
            self._json({"accounts": cliproxy_accounts(), "status": cliproxy_status()})
            return
        if p == "/" or p == "/index.html":
            self.path = "/index.html"
        super().do_GET()

    def do_POST(self):
        p = urlparse(self.path).path
        if p == "/api/import":
            try:
                data = self._read_json_body()
                conns = data.get("connections", [])
                if not conns:
                    self._json({"error": "No connections"}, 400)
                    return
                ins, upd, errs, token_report, alias_report = import_connections(conns)
                self._json({
                    "inserted": ins,
                    "updated": upd,
                    "replaced": upd,
                    "errors": errs,
                    "total": ins + upd,
                    "tokenSummary": token_report,
                    "aliasRepair": alias_report,
                })
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if p == "/api/repair":
            try:
                data = self._read_json_body()
                backup_sqlite()
                alias_report = ensure_model_aliases()
                config_report = repair_codex_config() if data.get("codexConfig", True) else {"ok": True, "changed": False}
                self._json({"ok": True, "aliasRepair": alias_report, "codexConfig": config_report})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if p == "/api/dedupe-connections":
            try:
                self._json(dedupe_connections())
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if p == "/api/import-cliproxy":
            try:
                data = self._read_json_body()
                conns = data.get("connections", [])
                if not conns:
                    self._json({"error": "No connections"}, 400)
                    return
                self._json(import_cliproxy_connections(conns))
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if p == "/api/refresh-preview":
            try:
                data = self._read_json_body()
                self._json({"items": refresh_preview(data.get("connections", []))})
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if p == "/api/import-from-cliproxy":
            try:
                conns = _cliproxy_auth_connections()
                if not conns:
                    self._json({"error": "No CLIProxy Codex auth files found"}, 400)
                    return
                ins, upd, errs, token_report, alias_report = import_connections(conns)
                self._json({
                    "ok": not errs,
                    "inserted": ins,
                    "updated": upd,
                    "replaced": upd,
                    "errors": errs,
                    "total": ins + upd,
                    "tokenSummary": token_report,
                    "aliasRepair": alias_report,
                })
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if p == "/api/import-codex-auth":
            try:
                conn, err = codex_auth_connection()
                if err:
                    self._json({"error": err}, 400)
                    return
                ins, upd, errs, token_report, alias_report = import_connections([conn])
                self._json({
                    "ok": not errs,
                    "inserted": ins,
                    "updated": upd,
                    "replaced": upd,
                    "errors": errs,
                    "total": ins + upd,
                    "tokenSummary": token_report,
                    "aliasRepair": alias_report,
                })
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if p == "/api/sync-cliproxy-from-9router":
            try:
                self._json(import_cliproxy_connections(export_codex_payload(include_secrets=True).get("providerConnections", [])))
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        if p == "/api/cliproxy/quarantine-stale":
            try:
                self._json(quarantine_stale_cliproxy_auths())
            except Exception as e:
                self._json({"error": str(e)}, 500)
            return
        self._json({"error": "Not found"}, 404)

    def do_DELETE(self):
        p = urlparse(self.path).path
        if p.startswith("/api/connections/"):
            cid = p.split("/")[-1]
            self._json({"deleted": delete_connection(cid)})
            return
        self._json({"error": "Not found"}, 404)


def main():
    print("=" * 50)
    print("  9router Import Tool")
    print("=" * 50)
    if SQLITE_PATH:
        print("  Database: {}".format(SQLITE_PATH))
    else:
        print("  [!] Database not found!")
        print("  Install and run 9router first.")
    print("  URL: http://localhost:{}".format(PORT))
    print("=" * 50)
    print("  Press Ctrl+C to stop")
    print()

    ThreadingHTTPServer.allow_reuse_address = True
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)

    def open_browser():
        import time
        time.sleep(0.8)
        webbrowser.open("http://localhost:{}".format(PORT))

    threading.Thread(target=open_browser, daemon=True).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
        server.server_close()


if __name__ == "__main__":
    main()
