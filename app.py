#!/usr/bin/env python3
"""Foco no Estudo — rastreador de tempo de estudos.

Servidor HTTP, API JSON e persistência SQLite em um único arquivo,
usando apenas a biblioteca padrão do Python.
"""
import hashlib
import hmac
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import threading
import time
from datetime import datetime, timedelta, timezone
from http import cookies as http_cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.environ.get("APP_DB_PATH", DATA_DIR / "estudos.sqlite"))
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
CHECKPOINT_INTERVAL = int(os.environ.get("CHECKPOINT_INTERVAL", "300"))  # segundos

SERVER_TZ = datetime.now().astimezone().tzinfo or timezone.utc
UTC = timezone.utc

PBKDF2_ITERATIONS = 200_000
TOKEN_TTL_DAYS = 30
SESSION_COOKIE = "session"

PERIODS = {"today", "week", "month", "total"}

DEFAULT_PROJECT_NAME = "Meu projeto de estudos"
DEFAULT_DAILY_GOAL = 360       # minutos (6h)
DEFAULT_TOTAL_GOAL = 36_000    # minutos (600h)
DEFAULT_SUBJECTS = [
    ("Português", "#2f80ed"),
    ("Direito Constitucional", "#27ae60"),
    ("Raciocínio Lógico", "#f2994a"),
    ("Informática", "#9b51e0"),
]

# ---------------------------------------------------------------------------
# Tempo e fuso horário
# ---------------------------------------------------------------------------


def now_utc():
    return datetime.now(UTC).replace(microsecond=0)


def iso_utc(dt):
    return dt.astimezone(UTC).replace(microsecond=0).isoformat()


def parse_dt(value, tz):
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SERVER_TZ)
    return parsed.astimezone(tz)


def request_timezone(headers):
    """Resolve o fuso do cliente a partir dos headers enviados pelo frontend."""
    zone_name = (headers.get("X-Client-Time-Zone") or "").strip()
    if zone_name:
        try:
            return ZoneInfo(zone_name)
        except ZoneInfoNotFoundError:
            pass
    offset = (headers.get("X-Client-Timezone-Offset") or "").strip()
    if offset:
        try:
            return timezone(timedelta(minutes=-int(offset)))
        except ValueError:
            pass
    return SERVER_TZ


def period_bounds(period, tz):
    """Início e fim (exclusivo) do período no fuso dado; (None, None) = sem limite."""
    day_start = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "today":
        return day_start, day_start + timedelta(days=1)
    if period == "week":
        start = day_start - timedelta(days=day_start.weekday())
        return start, start + timedelta(days=7)
    if period == "month":
        start = day_start.replace(day=1)
        next_month = start.replace(year=start.year + 1, month=1) if start.month == 12 \
            else start.replace(month=start.month + 1)
        return start, next_month
    return None, None

# ---------------------------------------------------------------------------
# Banco de dados
# ---------------------------------------------------------------------------


def connect():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_salt TEXT NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS auth_tokens (
                token_hash TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                daily_goal_minutes INTEGER NOT NULL DEFAULT 360,
                total_goal_minutes INTEGER NOT NULL DEFAULT 36000,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                user_id INTEGER REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS subjects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                color TEXT NOT NULL,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL,
                FOREIGN KEY (project_id) REFERENCES projects(id)
            );

            CREATE TABLE IF NOT EXISTS study_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id INTEGER NOT NULL,
                subject_id INTEGER NOT NULL,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                note TEXT,
                FOREIGN KEY (project_id) REFERENCES projects(id),
                FOREIGN KEY (subject_id) REFERENCES subjects(id)
            );
            """
        )
        # Migração de bancos criados antes do suporte multiusuário.
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(projects)")}
        if "user_id" not in columns:
            conn.execute("ALTER TABLE projects ADD COLUMN user_id INTEGER REFERENCES users(id)")

# ---------------------------------------------------------------------------
# Senhas e sessões de login
# ---------------------------------------------------------------------------


def hash_password(password, salt_hex=None):
    salt_hex = salt_hex or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), PBKDF2_ITERATIONS
    ).hex()
    return salt_hex, digest


def verify_password(user, password):
    _, digest = hash_password(password, user["password_salt"])
    return hmac.compare_digest(digest, user["password_hash"])


def token_hash(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def session_token(headers):
    header = headers.get("Cookie")
    if not header:
        return None
    cookie = http_cookies.SimpleCookie()
    try:
        cookie.load(header)
    except http_cookies.CookieError:
        return None
    morsel = cookie.get(SESSION_COOKIE)
    return morsel.value if morsel and morsel.value else None


def user_from_cookie(conn, headers):
    token = session_token(headers)
    if not token:
        return None
    return conn.execute(
        """
        SELECT u.* FROM auth_tokens t
        JOIN users u ON u.id = t.user_id
        WHERE t.token_hash = ? AND t.expires_at > ?
        """,
        (token_hash(token), iso_utc(now_utc())),
    ).fetchone()


def issue_session_cookie(conn, user_id):
    token = secrets.token_urlsafe(32)
    created = now_utc()
    conn.execute(
        "INSERT INTO auth_tokens (token_hash, user_id, created_at, expires_at) VALUES (?, ?, ?, ?)",
        (token_hash(token), user_id, iso_utc(created), iso_utc(created + timedelta(days=TOKEN_TTL_DAYS))),
    )
    return f"{SESSION_COOKIE}={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={TOKEN_TTL_DAYS * 86400}"


def clear_session_cookie():
    return f"{SESSION_COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0"

# ---------------------------------------------------------------------------
# Projetos, disciplinas e sessões de estudo
# ---------------------------------------------------------------------------


def create_project(conn, user_id, name, daily_goal_minutes, total_goal_minutes):
    created = iso_utc(now_utc())
    cur = conn.execute(
        """
        INSERT INTO projects (name, daily_goal_minutes, total_goal_minutes, active, user_id, created_at)
        VALUES (?, ?, ?, 0, ?, ?)
        """,
        (name, daily_goal_minutes, total_goal_minutes, user_id, created),
    )
    project_id = cur.lastrowid
    conn.executemany(
        "INSERT INTO subjects (project_id, name, color, created_at) VALUES (?, ?, ?, ?)",
        [(project_id, subject, color, created) for subject, color in DEFAULT_SUBJECTS],
    )
    return project_id


def activate_project(conn, user_id, project_id):
    """Torna o projeto o ativo do usuário, pausando qualquer timer em andamento."""
    for row in conn.execute("SELECT id FROM projects WHERE user_id = ? AND active = 1", (user_id,)):
        close_active_session(conn, row["id"])
    conn.execute("UPDATE projects SET active = 0 WHERE user_id = ?", (user_id,))
    conn.execute("UPDATE projects SET active = 1 WHERE id = ? AND user_id = ?", (project_id, user_id))


def active_project(conn, user_id):
    """Projeto ativo do usuário; elege ou cria um se necessário."""
    project = conn.execute(
        "SELECT * FROM projects WHERE user_id = ? AND active = 1 ORDER BY id LIMIT 1", (user_id,)
    ).fetchone()
    if project:
        return project
    project = conn.execute(
        "SELECT * FROM projects WHERE user_id = ? ORDER BY id LIMIT 1", (user_id,)
    ).fetchone()
    if not project:
        project_id = create_project(
            conn, user_id, DEFAULT_PROJECT_NAME, DEFAULT_DAILY_GOAL, DEFAULT_TOTAL_GOAL
        )
        project = conn.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()
    conn.execute("UPDATE projects SET active = 1 WHERE id = ?", (project["id"],))
    return project


def owned_active_subject(conn, project_id, subject_id):
    if subject_id <= 0:
        raise ValueError("Selecione uma disciplina")
    subject = conn.execute(
        "SELECT id FROM subjects WHERE id = ? AND project_id = ? AND active = 1",
        (subject_id, project_id),
    ).fetchone()
    if not subject:
        raise ValueError("Disciplina inválida")
    return subject


def active_session(conn, project_id):
    return conn.execute(
        """
        SELECT ss.*, s.name AS subject_name, s.color AS subject_color
        FROM study_sessions ss
        JOIN subjects s ON s.id = ss.subject_id
        WHERE ss.project_id = ? AND ss.ended_at IS NULL
        ORDER BY ss.started_at DESC
        LIMIT 1
        """,
        (project_id,),
    ).fetchone()


def session_logical_start(conn, session):
    # Percorre a cadeia de checkpoints para trás (o ended_at de cada trecho é o
    # started_at do seguinte) até o início real da sessão lógica atual.
    row = conn.execute(
        """
        WITH RECURSIVE chain(id, started_at, ended_at, subject_id, project_id) AS (
            SELECT id, started_at, ended_at, subject_id, project_id
            FROM study_sessions WHERE id = ?
            UNION ALL
            SELECT ss.id, ss.started_at, ss.ended_at, ss.subject_id, ss.project_id
            FROM study_sessions ss
            JOIN chain c ON ss.ended_at = c.started_at
                AND ss.project_id = c.project_id
                AND ss.subject_id = c.subject_id
        )
        SELECT MIN(started_at) AS logical_started_at FROM chain
        """,
        (session["id"],),
    ).fetchone()
    return row["logical_started_at"] if row and row["logical_started_at"] else session["started_at"]


def close_active_session(conn, project_id, end_time=None):
    session = active_session(conn, project_id)
    if not session:
        return None
    end_time = end_time or now_utc()
    started = parse_dt(session["started_at"], UTC)
    if end_time < started:
        end_time = started
    conn.execute(
        "UPDATE study_sessions SET ended_at = ? WHERE id = ?",
        (iso_utc(end_time), session["id"]),
    )
    return session


def session_segments(rows, start_bound, end_bound, tz):
    """Quebra as sessões em segmentos diários dentro do período, no fuso dado."""
    current = datetime.now(tz).replace(microsecond=0)
    segments = []
    for row in rows:
        started = parse_dt(row["started_at"], tz)
        ended = parse_dt(row["ended_at"], tz) or current
        if end_bound and started >= end_bound:
            continue
        if start_bound and ended <= start_bound:
            continue
        cursor = max(started, start_bound) if start_bound else started
        segment_end = min(ended, end_bound) if end_bound else ended
        while cursor < segment_end:
            next_midnight = cursor.replace(hour=0, minute=0, second=0) + timedelta(days=1)
            chunk_end = min(segment_end, next_midnight)
            seconds = max(0, int((chunk_end - cursor).total_seconds()))
            if seconds:
                segments.append(
                    {
                        "date": cursor.date().isoformat(),
                        "subject_id": row["subject_id"],
                        "subject_name": row["subject_name"],
                        "subject_color": row["subject_color"],
                        "seconds": seconds,
                    }
                )
            cursor = chunk_end
    return segments


def report_data(conn, project_id, period, tz):
    start, end = period_bounds(period, tz)
    rows = conn.execute(
        """
        SELECT ss.*, s.name AS subject_name, s.color AS subject_color
        FROM study_sessions ss
        JOIN subjects s ON s.id = ss.subject_id
        WHERE ss.project_id = ?
        ORDER BY ss.started_at ASC
        """,
        (project_id,),
    ).fetchall()

    by_subject = {}
    by_day = {}
    total_seconds = 0
    for item in session_segments(rows, start, end, tz):
        total_seconds += item["seconds"]
        by_day[item["date"]] = by_day.get(item["date"], 0) + item["seconds"]
        subject = by_subject.setdefault(
            item["subject_id"],
            {
                "subject_id": item["subject_id"],
                "name": item["subject_name"],
                "color": item["subject_color"],
                "seconds": 0,
            },
        )
        subject["seconds"] += item["seconds"]

    if start and end:
        cursor = start
        while cursor < end:
            by_day.setdefault(cursor.date().isoformat(), 0)
            cursor += timedelta(days=1)

    return {
        "period": period,
        "start": start.date().isoformat() if start else None,
        "end": end.date().isoformat() if end else None,
        "total_seconds": total_seconds,
        "by_subject": sorted(by_subject.values(), key=lambda value: value["seconds"], reverse=True),
        "by_day": [{"date": date, "seconds": seconds} for date, seconds in sorted(by_day.items())],
    }


def state_data(conn, user, tz):
    """Estado completo do app para o usuário: projetos, disciplinas, timer e resumos."""
    project = active_project(conn, user["id"])
    project_id = project["id"]
    projects = conn.execute(
        "SELECT id, name, active FROM projects WHERE user_id = ? ORDER BY created_at ASC, id ASC",
        (user["id"],),
    ).fetchall()
    subjects = conn.execute(
        "SELECT * FROM subjects WHERE project_id = ? ORDER BY active DESC, name ASC",
        (project_id,),
    ).fetchall()
    running = active_session(conn, project_id)
    running_dict = dict(running) if running else None
    if running_dict:
        running_dict["logical_started_at"] = session_logical_start(conn, running)
    return {
        "user": {"email": user["email"]},
        "project": dict(project),
        "projects": [dict(row) for row in projects],
        "subjects": [dict(row) for row in subjects],
        "running_session": running_dict,
        "today": report_data(conn, project_id, "today", tz),
        "total": report_data(conn, project_id, "total", tz),
        "timezone": getattr(tz, "key", None) or str(tz),
    }

# ---------------------------------------------------------------------------
# Rotas da API
# ---------------------------------------------------------------------------
# Cada handler recebe um Request e devolve o payload JSON — ou uma tupla
# (payload, status) / (payload, status, headers). Erros de validação são
# levantados como ValueError e viram respostas 400.

API_ROUTES = []


def route(method, pattern, auth=True):
    def register(func):
        API_ROUTES.append((method, re.compile(f"^{pattern}/?$"), auth, func))
        return func
    return register


class Request:
    """Contexto de uma chamada de API."""

    def __init__(self, conn, user, payload, params, query, tz, headers):
        self.conn = conn
        self.user = user
        self.payload = payload
        self.params = params
        self.query = query
        self.tz = tz
        self.headers = headers

    def text(self, key, message):
        value = str(self.payload.get(key, "")).strip()
        if not value:
            raise ValueError(message)
        return value

    def goal(self, key, default=None):
        minutes = int(self.payload.get(key) or default or 0)
        if minutes <= 0:
            raise ValueError("As metas precisam ser maiores que zero")
        return minutes

    def project(self):
        return active_project(self.conn, self.user["id"])

    def state(self):
        return state_data(self.conn, self.user, self.tz)


# --- Autenticação ---

@route("POST", r"/api/auth/register", auth=False)
def api_register(req):
    email = str(req.payload.get("email", "")).strip().lower()
    password = str(req.payload.get("password", ""))
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise ValueError("Informe um e-mail válido")
    if len(password) < 6:
        raise ValueError("A senha precisa ter ao menos 6 caracteres")
    if req.conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone():
        raise ValueError("E-mail já cadastrado")

    salt, digest = hash_password(password)
    cur = req.conn.execute(
        "INSERT INTO users (email, password_salt, password_hash, created_at) VALUES (?, ?, ?, ?)",
        (email, salt, digest, iso_utc(now_utc())),
    )
    user_id = cur.lastrowid
    # O primeiro usuário cadastrado adota projetos criados antes da autenticação existir.
    if req.conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 1:
        req.conn.execute("UPDATE projects SET user_id = ? WHERE user_id IS NULL", (user_id,))
    req.user = req.conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    cookie = issue_session_cookie(req.conn, user_id)
    return req.state(), 201, {"Set-Cookie": cookie}


@route("POST", r"/api/auth/login", auth=False)
def api_login(req):
    email = str(req.payload.get("email", "")).strip().lower()
    password = str(req.payload.get("password", ""))
    user = req.conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if not user or not verify_password(user, password):
        raise ValueError("E-mail ou senha incorretos")
    req.user = user
    cookie = issue_session_cookie(req.conn, user["id"])
    return req.state(), 200, {"Set-Cookie": cookie}


@route("POST", r"/api/auth/logout", auth=False)
def api_logout(req):
    token = session_token(req.headers)
    if token:
        req.conn.execute("DELETE FROM auth_tokens WHERE token_hash = ?", (token_hash(token),))
    return {"ok": True}, 200, {"Set-Cookie": clear_session_cookie()}


# --- Estado e relatórios ---

@route("GET", r"/api/state")
def api_state(req):
    return req.state()


@route("GET", r"/api/reports")
def api_reports(req):
    period = req.query.get("period", ["today"])[0]
    if period not in PERIODS:
        raise ValueError("Período inválido")
    return report_data(req.conn, req.project()["id"], period, req.tz)


# --- Projetos ---

@route("POST", r"/api/project")
def api_update_project(req):
    name = req.text("name", "Informe o nome do projeto")
    daily = req.goal("daily_goal_minutes")
    total = req.goal("total_goal_minutes")
    req.conn.execute(
        "UPDATE projects SET name = ?, daily_goal_minutes = ?, total_goal_minutes = ? WHERE id = ?",
        (name, daily, total, req.project()["id"]),
    )
    return req.state()


@route("POST", r"/api/projects")
def api_create_project(req):
    name = req.text("name", "Informe o nome do projeto")
    daily = req.goal("daily_goal_minutes", DEFAULT_DAILY_GOAL)
    total = req.goal("total_goal_minutes", DEFAULT_TOTAL_GOAL)
    project_id = create_project(req.conn, req.user["id"], name, daily, total)
    activate_project(req.conn, req.user["id"], project_id)
    return req.state(), 201


@route("POST", r"/api/projects/(?P<project_id>\d+)/activate")
def api_activate_project(req):
    project_id = int(req.params["project_id"])
    owned = req.conn.execute(
        "SELECT id FROM projects WHERE id = ? AND user_id = ?", (project_id, req.user["id"])
    ).fetchone()
    if not owned:
        raise ValueError("Projeto não encontrado")
    activate_project(req.conn, req.user["id"], project_id)
    return req.state()


@route("DELETE", r"/api/projects/(?P<project_id>\d+)")
def api_delete_project(req):
    project_id = int(req.params["project_id"])
    owned = req.conn.execute(
        "SELECT * FROM projects WHERE id = ? AND user_id = ?", (project_id, req.user["id"])
    ).fetchone()
    if not owned:
        raise ValueError("Projeto não encontrado")
    total = req.conn.execute(
        "SELECT COUNT(*) AS n FROM projects WHERE user_id = ?", (req.user["id"],)
    ).fetchone()["n"]
    if total <= 1:
        raise ValueError("Você precisa manter ao menos um projeto")
    req.conn.execute("DELETE FROM study_sessions WHERE project_id = ?", (project_id,))
    req.conn.execute("DELETE FROM subjects WHERE project_id = ?", (project_id,))
    req.conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
    if owned["active"]:
        remaining = req.conn.execute(
            "SELECT id FROM projects WHERE user_id = ? ORDER BY id LIMIT 1", (req.user["id"],)
        ).fetchone()
        if remaining:
            activate_project(req.conn, req.user["id"], remaining["id"])
    return req.state()


@route("POST", r"/api/reset")
def api_reset(req):
    # Zera o histórico do projeto ativo; disciplinas e metas são mantidas.
    req.conn.execute("DELETE FROM study_sessions WHERE project_id = ?", (req.project()["id"],))
    return req.state()


# --- Disciplinas ---

@route("POST", r"/api/subjects")
def api_create_subject(req):
    name = req.text("name", "Informe o nome da disciplina")
    color = str(req.payload.get("color", "#2f80ed")).strip()[:16]
    cur = req.conn.execute(
        "INSERT INTO subjects (project_id, name, color, created_at) VALUES (?, ?, ?, ?)",
        (req.project()["id"], name, color, iso_utc(now_utc())),
    )
    return {"subject_id": cur.lastrowid, "state": req.state()}, 201


@route("POST", r"/api/subjects/(?P<subject_id>\d+)")
def api_update_subject(req):
    subject_id = int(req.params["subject_id"])
    name = req.text("name", "Informe o nome da disciplina")
    color = str(req.payload.get("color", "#2f80ed")).strip()[:16]
    active = 1 if req.payload.get("active", True) else 0
    req.conn.execute(
        "UPDATE subjects SET name = ?, color = ?, active = ? WHERE id = ? AND project_id = ?",
        (name, color, active, subject_id, req.project()["id"]),
    )
    return req.state()


@route("DELETE", r"/api/subjects/(?P<subject_id>\d+)")
def api_delete_subject(req):
    subject_id = int(req.params["subject_id"])
    project_id = req.project()["id"]
    subject = req.conn.execute(
        "SELECT id FROM subjects WHERE id = ? AND project_id = ?", (subject_id, project_id)
    ).fetchone()
    if not subject:
        raise ValueError("Disciplina não encontrada")
    close_active_session(req.conn, project_id)
    req.conn.execute(
        "DELETE FROM study_sessions WHERE subject_id = ? AND project_id = ?", (subject_id, project_id)
    )
    req.conn.execute(
        "DELETE FROM subjects WHERE id = ? AND project_id = ?", (subject_id, project_id)
    )
    return req.state()


# --- Timer ---

@route("POST", r"/api/timer/start")
def api_timer_start(req):
    project_id = req.project()["id"]
    subject_id = int(req.payload.get("subject_id") or 0)
    owned_active_subject(req.conn, project_id, subject_id)
    if not active_session(req.conn, project_id):
        req.conn.execute(
            "INSERT INTO study_sessions (project_id, subject_id, started_at) VALUES (?, ?, ?)",
            (project_id, subject_id, iso_utc(now_utc())),
        )
    return req.state()


@route("POST", r"/api/timer/pause")
def api_timer_pause(req):
    close_active_session(req.conn, req.project()["id"])
    return req.state()


@route("POST", r"/api/timer/switch")
def api_timer_switch(req):
    project_id = req.project()["id"]
    subject_id = int(req.payload.get("subject_id") or 0)
    owned_active_subject(req.conn, project_id, subject_id)
    running = active_session(req.conn, project_id)
    if running and running["subject_id"] != subject_id:
        timestamp = now_utc()
        close_active_session(req.conn, project_id, timestamp)
        req.conn.execute(
            "INSERT INTO study_sessions (project_id, subject_id, started_at) VALUES (?, ?, ?)",
            (project_id, subject_id, iso_utc(timestamp)),
        )
    return req.state()

# ---------------------------------------------------------------------------
# Servidor HTTP
# ---------------------------------------------------------------------------


def read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if not length:
        return {}
    body = handler.rfile.read(length).decode("utf-8")
    return json.loads(body) if body else {}


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def send_json(self, payload, status=200, extra_headers=None):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        for key, value in (extra_headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(encoded)

    def send_error_json(self, message, status=400):
        self.send_json({"error": message}, status)

    def redirect(self, location):
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def dispatch_api(self, method):
        """Resolve a rota de API; devolve False se nenhuma corresponder."""
        parsed = urlparse(self.path)
        for route_method, pattern, requires_auth, handler in API_ROUTES:
            if route_method != method:
                continue
            match = pattern.match(parsed.path)
            if not match:
                continue
            try:
                payload = read_json(self) if method == "POST" else {}
                with connect() as conn:
                    user = user_from_cookie(conn, self.headers)
                    if requires_auth and not user:
                        self.send_error_json("Não autenticado", 401)
                        return True
                    request = Request(
                        conn, user, payload, match.groupdict(),
                        parse_qs(parsed.query), request_timezone(self.headers), self.headers,
                    )
                    result = handler(request)
                body, status, headers = result, 200, None
                if isinstance(result, tuple):
                    body = result[0]
                    status = result[1] if len(result) > 1 else 200
                    headers = result[2] if len(result) > 2 else None
                self.send_json(body, status, headers)
            except json.JSONDecodeError:
                self.send_error_json("JSON inválido", 400)
            except ValueError as exc:
                self.send_error_json(str(exc), 400)
            except Exception as exc:
                self.send_error_json(f"Erro interno: {exc}", 500)
            return True
        return False

    def do_GET(self):
        path = urlparse(self.path).path
        if path.startswith("/api/"):
            if not self.dispatch_api("GET"):
                self.send_error_json("Rota não encontrada", 404)
            return
        self.serve_page(path)

    def do_POST(self):
        if not self.dispatch_api("POST"):
            self.send_error_json("Rota não encontrada", 404)

    def do_DELETE(self):
        if not self.dispatch_api("DELETE"):
            self.send_error_json("Rota não encontrada", 404)

    def serve_page(self, path):
        # "/" é a landing pública; "/app" é o aplicativo, que exige login.
        if path in {"/", "/app", "/index.html"}:
            with connect() as conn:
                authenticated = user_from_cookie(conn, self.headers) is not None
            if path == "/":
                if authenticated:
                    self.redirect("/app")
                else:
                    self.serve_static("/landing.html")
            elif authenticated:
                self.serve_static("/index.html")
            else:
                self.redirect("/")
            return
        self.serve_static(path)

    def serve_static(self, path):
        file_path = (STATIC_DIR / path.lstrip("/")).resolve()
        if not file_path.is_relative_to(STATIC_DIR.resolve()) or not file_path.is_file():
            self.send_response(404)
            self.end_headers()
            return
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

# ---------------------------------------------------------------------------
# Manutenção em segundo plano
# ---------------------------------------------------------------------------


def recover_orphaned_sessions():
    # Sessões com ended_at NULL deixadas por uma queda anterior. Fecha em
    # started_at (duração zero) para que tempo parado nunca conte como estudo.
    with connect() as conn:
        rows = conn.execute("SELECT id FROM study_sessions WHERE ended_at IS NULL").fetchall()
        for row in rows:
            conn.execute("UPDATE study_sessions SET ended_at = started_at WHERE id = ?", (row["id"],))
        if rows:
            print(
                f"[startup] {len(rows)} sessão(ões) interrompida(s) encerrada(s) "
                f"(máx. {CHECKPOINT_INTERVAL // 60} min perdidos)."
            )


def purge_expired_tokens():
    with connect() as conn:
        conn.execute("DELETE FROM auth_tokens WHERE expires_at <= ?", (iso_utc(now_utc()),))


def checkpoint_loop():
    # Rotaciona as sessões ativas a cada CHECKPOINT_INTERVAL segundos para que a
    # sessão aberta no banco cubra no máximo esse intervalo. Em caso de queda,
    # perde-se no máximo o último trecho; todo o resto já está fechado.
    while True:
        time.sleep(CHECKPOINT_INTERVAL)
        try:
            with connect() as conn:
                sessions = conn.execute(
                    "SELECT id, project_id, subject_id FROM study_sessions WHERE ended_at IS NULL"
                ).fetchall()
                for session in sessions:
                    stamp = iso_utc(now_utc())
                    conn.execute(
                        "UPDATE study_sessions SET ended_at = ? WHERE id = ?", (stamp, session["id"])
                    )
                    conn.execute(
                        "INSERT INTO study_sessions (project_id, subject_id, started_at) VALUES (?, ?, ?)",
                        (session["project_id"], session["subject_id"], stamp),
                    )
        except Exception as exc:
            print(f"[checkpoint] Erro: {exc}")


def main():
    init_db()
    recover_orphaned_sessions()
    purge_expired_tokens()
    threading.Thread(target=checkpoint_loop, daemon=True).start()
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Servidor iniciado em http://{HOST}:{PORT}")
    print(f"Banco de dados: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
