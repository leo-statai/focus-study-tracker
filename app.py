#!/usr/bin/env python3
import json
import mimetypes
import os
import sqlite3
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = Path(os.environ.get("APP_DATA_DIR", BASE_DIR / "data"))
DB_PATH = Path(os.environ.get("APP_DB_PATH", DATA_DIR / "estudos.sqlite"))
HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "8000"))
LOCAL_TZ = datetime.now().astimezone().tzinfo or timezone.utc


def now_local():
    return datetime.now(LOCAL_TZ).replace(microsecond=0)


def parse_dt(value):
    if not value:
        return None
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=LOCAL_TZ)
    return parsed.astimezone(LOCAL_TZ)


def iso(dt):
    return dt.astimezone(LOCAL_TZ).replace(microsecond=0).isoformat()


def today_bounds():
    start = now_local().replace(hour=0, minute=0, second=0)
    return start, start + timedelta(days=1)


def period_bounds(period):
    current = now_local()
    day_start = current.replace(hour=0, minute=0, second=0)
    if period == "today":
        return day_start, day_start + timedelta(days=1)
    if period == "week":
        start = day_start - timedelta(days=day_start.weekday())
        return start, start + timedelta(days=7)
    if period == "month":
        start = day_start.replace(day=1)
        if start.month == 12:
            end = start.replace(year=start.year + 1, month=1)
        else:
            end = start.replace(month=start.month + 1)
        return start, end
    return None, None


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
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                daily_goal_minutes INTEGER NOT NULL DEFAULT 360,
                total_goal_minutes INTEGER NOT NULL DEFAULT 36000,
                active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
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
        project = conn.execute("SELECT id FROM projects WHERE active = 1 LIMIT 1").fetchone()
        if not project:
            created = iso(now_local())
            cur = conn.execute(
                """
                INSERT INTO projects (name, daily_goal_minutes, total_goal_minutes, created_at)
                VALUES (?, ?, ?, ?)
                """,
                ("Meu projeto de estudos", 360, 36000, created),
            )
            project_id = cur.lastrowid
            defaults = [
                ("Português", "#2f80ed"),
                ("Direito Constitucional", "#27ae60"),
                ("Raciocínio Lógico", "#f2994a"),
                ("Informática", "#9b51e0"),
            ]
            conn.executemany(
                """
                INSERT INTO subjects (project_id, name, color, created_at)
                VALUES (?, ?, ?, ?)
                """,
                [(project_id, name, color, created) for name, color in defaults],
            )


def active_project(conn):
    project = conn.execute("SELECT * FROM projects WHERE active = 1 ORDER BY id LIMIT 1").fetchone()
    if not project:
        raise RuntimeError("Projeto ativo não encontrado")
    return project


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


def close_active_session(conn, project_id, end_time=None):
    session = active_session(conn, project_id)
    if not session:
        return None
    end_time = end_time or now_local()
    started = parse_dt(session["started_at"])
    if end_time < started:
        end_time = started
    conn.execute(
        "UPDATE study_sessions SET ended_at = ? WHERE id = ?",
        (iso(end_time), session["id"]),
    )
    return session


def session_segments(rows, start_bound=None, end_bound=None):
    current = now_local()
    segments = []
    for row in rows:
        started = parse_dt(row["started_at"])
        ended = parse_dt(row["ended_at"]) or current
        if end_bound and started >= end_bound:
            continue
        if start_bound and ended <= start_bound:
            continue
        segment_start = max(started, start_bound) if start_bound else started
        segment_end = min(ended, end_bound) if end_bound else ended
        cursor = segment_start
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


def report_data(conn, project_id, period):
    start, end = period_bounds(period)
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
    segments = session_segments(rows, start, end)
    by_subject = {}
    by_day = {}
    total_seconds = 0
    for item in segments:
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

    if period in {"today", "week", "month"}:
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


def state_data(conn):
    project = active_project(conn)
    project_id = project["id"]
    subjects = conn.execute(
        "SELECT * FROM subjects WHERE project_id = ? ORDER BY active DESC, name ASC",
        (project_id,),
    ).fetchall()
    running = active_session(conn, project_id)
    today = report_data(conn, project_id, "today")
    total = report_data(conn, project_id, "total")
    return {
        "project": dict(project),
        "subjects": [dict(row) for row in subjects],
        "running_session": dict(running) if running else None,
        "today": today,
        "total": total,
    }


def read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or "0")
    if not length:
        return {}
    body = handler.rfile.read(length).decode("utf-8")
    return json.loads(body) if body else {}


class AppHandler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    def send_json(self, payload, status=200):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def send_error_json(self, message, status=400):
        self.send_json({"error": message}, status)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/state":
            with connect() as conn:
                self.send_json(state_data(conn))
            return
        if parsed.path == "/api/reports":
            period = parse_qs(parsed.query).get("period", ["today"])[0]
            if period not in {"today", "week", "month", "total"}:
                self.send_error_json("Período inválido", 400)
                return
            with connect() as conn:
                project = active_project(conn)
                self.send_json(report_data(conn, project["id"], period))
            return
        self.serve_static(parsed.path)

    def do_POST(self):
        parsed = urlparse(self.path)
        try:
            payload = read_json(self)
            if parsed.path == "/api/project":
                self.update_project(payload)
            elif parsed.path == "/api/subjects":
                self.create_subject(payload)
            elif parsed.path.startswith("/api/subjects/"):
                self.update_subject(parsed.path, payload)
            elif parsed.path == "/api/timer/start":
                self.start_timer(payload)
            elif parsed.path == "/api/timer/pause":
                self.pause_timer()
            elif parsed.path == "/api/timer/switch":
                self.switch_timer(payload)
            elif parsed.path == "/api/reset":
                self.reset_app()
            else:
                self.send_error_json("Rota não encontrada", 404)
        except json.JSONDecodeError:
            self.send_error_json("JSON inválido", 400)
        except ValueError as exc:
            self.send_error_json(str(exc), 400)
        except Exception as exc:
            self.send_error_json(f"Erro interno: {exc}", 500)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        try:
            if parsed.path.startswith("/api/subjects/"):
                self.delete_subject(parsed.path)
            else:
                self.send_error_json("Rota não encontrada", 404)
        except ValueError as exc:
            self.send_error_json(str(exc), 400)
        except Exception as exc:
            self.send_error_json(f"Erro interno: {exc}", 500)

    def update_project(self, payload):
        name = str(payload.get("name", "")).strip()
        daily_goal_minutes = int(payload.get("daily_goal_minutes", 0))
        total_goal_minutes = int(payload.get("total_goal_minutes", 0))
        if not name:
            raise ValueError("Informe o nome do projeto")
        if daily_goal_minutes <= 0 or total_goal_minutes <= 0:
            raise ValueError("As metas precisam ser maiores que zero")
        with connect() as conn:
            project = active_project(conn)
            conn.execute(
                """
                UPDATE projects
                SET name = ?, daily_goal_minutes = ?, total_goal_minutes = ?
                WHERE id = ?
                """,
                (name, daily_goal_minutes, total_goal_minutes, project["id"]),
            )
            self.send_json(state_data(conn))

    def create_subject(self, payload):
        name = str(payload.get("name", "")).strip()
        color = str(payload.get("color", "#2f80ed")).strip()[:16]
        if not name:
            raise ValueError("Informe o nome da disciplina")
        with connect() as conn:
            project = active_project(conn)
            cur = conn.execute(
                """
                INSERT INTO subjects (project_id, name, color, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (project["id"], name, color, iso(now_local())),
            )
            self.send_json({"subject_id": cur.lastrowid, "state": state_data(conn)}, 201)

    def update_subject(self, path, payload):
        subject_id = int(path.rstrip("/").split("/")[-1])
        name = str(payload.get("name", "")).strip()
        color = str(payload.get("color", "#2f80ed")).strip()[:16]
        active = 1 if payload.get("active", True) else 0
        if not name:
            raise ValueError("Informe o nome da disciplina")
        with connect() as conn:
            project = active_project(conn)
            conn.execute(
                """
                UPDATE subjects
                SET name = ?, color = ?, active = ?
                WHERE id = ? AND project_id = ?
                """,
                (name, color, active, subject_id, project["id"]),
            )
            self.send_json(state_data(conn))

    def delete_subject(self, path):
        subject_id = int(path.rstrip("/").split("/")[-1])
        with connect() as conn:
            project = active_project(conn)
            subject = conn.execute(
                "SELECT id FROM subjects WHERE id = ? AND project_id = ?",
                (subject_id, project["id"]),
            ).fetchone()
            if not subject:
                raise ValueError("Disciplina não encontrada")
            close_active_session(conn, project["id"])
            conn.execute("DELETE FROM study_sessions WHERE subject_id = ? AND project_id = ?", (subject_id, project["id"]))
            conn.execute("DELETE FROM subjects WHERE id = ? AND project_id = ?", (subject_id, project["id"]))
            self.send_json(state_data(conn))

    def reset_app(self):
        if DB_PATH.exists():
            DB_PATH.unlink()
        init_db()
        with connect() as conn:
            self.send_json(state_data(conn))

    def start_timer(self, payload):
        subject_id = int(payload.get("subject_id") or 0)
        if subject_id <= 0:
            raise ValueError("Selecione uma disciplina para iniciar")
        with connect() as conn:
            project = active_project(conn)
            subject = conn.execute(
                "SELECT id FROM subjects WHERE id = ? AND project_id = ? AND active = 1",
                (subject_id, project["id"]),
            ).fetchone()
            if not subject:
                raise ValueError("Disciplina inválida")
            if not active_session(conn, project["id"]):
                conn.execute(
                    """
                    INSERT INTO study_sessions (project_id, subject_id, started_at)
                    VALUES (?, ?, ?)
                    """,
                    (project["id"], subject_id, iso(now_local())),
                )
            self.send_json(state_data(conn))

    def pause_timer(self):
        with connect() as conn:
            project = active_project(conn)
            close_active_session(conn, project["id"])
            self.send_json(state_data(conn))

    def switch_timer(self, payload):
        subject_id = int(payload.get("subject_id") or 0)
        if subject_id <= 0:
            raise ValueError("Selecione uma disciplina")
        with connect() as conn:
            project = active_project(conn)
            subject = conn.execute(
                "SELECT id FROM subjects WHERE id = ? AND project_id = ? AND active = 1",
                (subject_id, project["id"]),
            ).fetchone()
            if not subject:
                raise ValueError("Disciplina inválida")
            running = active_session(conn, project["id"])
            if running and running["subject_id"] != subject_id:
                timestamp = now_local()
                close_active_session(conn, project["id"], timestamp)
                conn.execute(
                    """
                    INSERT INTO study_sessions (project_id, subject_id, started_at)
                    VALUES (?, ?, ?)
                    """,
                    (project["id"], subject_id, iso(timestamp)),
                )
            self.send_json(state_data(conn))

    def serve_static(self, path):
        if path in {"", "/"}:
            path = "/index.html"
        safe_path = Path(path.lstrip("/"))
        file_path = (STATIC_DIR / safe_path).resolve()
        if not str(file_path).startswith(str(STATIC_DIR.resolve())) or not file_path.exists():
            self.send_response(404)
            self.end_headers()
            return
        content_type = mimetypes.guess_type(file_path.name)[0] or "application/octet-stream"
        data = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), AppHandler)
    print(f"Servidor iniciado em http://{HOST}:{PORT}")
    print(f"Banco de dados: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
