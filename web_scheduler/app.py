#!/usr/bin/env python3
"""
CronMaster — Lightweight Web Cron & Automation Scheduler
=========================================================
Zero-dependency web dashboard and background scheduler engine.
Provides a modern REST API, SQLite run history, live log viewer,
and on/off switches for scheduled jobs.
"""

import os
import sys
import json
import time
import sqlite3
import subprocess
import threading
import re
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
import urllib.parse
import mimetypes

# Configuration
PORT = int(os.environ.get("PORT", 5000))
HOST = os.environ.get("HOST", "0.0.0.0")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(BASE_DIR)
DB_PATH = os.path.join(BASE_DIR, "scheduler.db")
STATIC_DIR = os.path.join(BASE_DIR, "static")

def get_config_path():
    candidates = [
        os.path.join(PROJECT_ROOT, "config.json"),
        os.path.join(BASE_DIR, "config.json"),
        os.path.join(os.getcwd(), "config.json"),
        "config.json"
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return os.path.join(PROJECT_ROOT, "config.json")

# Threading HTTP Server
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


# ==========================================
# 1. DATABASE & INITIAL SEEDING
# ==========================================

def get_db():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
    CREATE TABLE IF NOT EXISTS jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        description TEXT,
        command TEXT NOT NULL,
        working_dir TEXT,
        cron_expression TEXT NOT NULL,
        enabled INTEGER DEFAULT 1,
        timeout_seconds INTEGER DEFAULT 300,
        last_run_at TEXT,
        last_status TEXT,
        last_duration REAL,
        next_run_at TEXT,
        created_at TEXT,
        updated_at TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS run_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id INTEGER NOT NULL,
        job_name TEXT NOT NULL,
        trigger_type TEXT NOT NULL, -- 'scheduled' or 'manual'
        started_at TEXT NOT NULL,
        ended_at TEXT,
        duration_seconds REAL,
        status TEXT NOT NULL,       -- 'running', 'success', 'failed', 'timeout'
        exit_code INTEGER,
        output TEXT,
        FOREIGN KEY (job_id) REFERENCES jobs(id) ON DELETE CASCADE
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT
    )
    """)

    # Check if jobs table is empty. If so, seed with BuildingLink Badminton Booking
    c.execute("SELECT COUNT(*) FROM jobs")
    count = c.fetchone()[0]
    if count == 0:
        now_iso = datetime.now().isoformat()
        python_cmd = "python3" if sys.platform != "win32" else "py"
        next_run = calculate_next_cron_run("0 0 * * *", datetime.now())
        next_run_iso = next_run.isoformat() if next_run else None

        c.execute("""
        INSERT INTO jobs (
            name, description, command, working_dir, cron_expression,
            enabled, timeout_seconds, next_run_at, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "BuildingLink Badminton Auto-Booker",
            "Automatically logs into BuildingLink at 12:00 AM midnight and books Badminton court for the next day according to preferred times.",
            f"{python_cmd} buildinglink_bot.py",
            PROJECT_ROOT,
            "0 0 * * *",
            1,
            300,
            next_run_iso,
            now_iso,
            now_iso
        ))
        print("[+] Seeded default job: BuildingLink Badminton Auto-Booker")

    conn.commit()
    conn.close()


# ==========================================
# 2. CRON EXPRESSION PARSER & EVALUATOR
# ==========================================

def match_cron_field(val, pattern, min_val, max_val):
    for part in pattern.split(','):
        part = part.strip()
        if part == '*':
            return True
        if '/' in part:
            sub, step = part.split('/')
            start = min_val if sub == '*' else int(sub)
            if (val - start) % int(step) == 0 and val >= start:
                return True
        elif '-' in part:
            start, end = map(int, part.split('-'))
            if start <= val <= end:
                return True
        elif part.isdigit() and int(part) == val:
            return True
    return False

def calculate_next_cron_run(cron_str, start_dt=None):
    """
    Computes the next datetime matching standard 5-part cron:
    minute (0-59), hour (0-23), day_of_month (1-31), month (1-12), day_of_week (0-6 Sun-Sat)
    """
    try:
        parts = cron_str.strip().split()
        if len(parts) != 5:
            return None
        min_p, hour_p, dom_p, mon_p, dow_p = parts

        dt = (start_dt or datetime.now()).replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(60 * 24 * 366):
            if not match_cron_field(dt.month, mon_p, 1, 12):
                dt = (dt.replace(day=1, hour=0, minute=0) + timedelta(days=32)).replace(day=1)
                continue

            dow = (dt.weekday() + 1) % 7 # 0=Sunday, 1=Monday, ..., 6=Saturday
            if not match_cron_field(dt.day, dom_p, 1, 31) or not match_cron_field(dow, dow_p, 0, 6):
                dt = dt.replace(hour=0, minute=0) + timedelta(days=1)
                continue

            if not match_cron_field(dt.hour, hour_p, 0, 23):
                dt = dt.replace(minute=0) + timedelta(hours=1)
                continue

            if match_cron_field(dt.minute, min_p, 0, 59):
                return dt

            dt += timedelta(minutes=1)
    except Exception as e:
        print(f"[!] Error calculating cron '{cron_str}': {e}")
    return None

def human_readable_cron(cron_str):
    parts = cron_str.strip().split()
    if len(parts) != 5:
        return cron_str
    m, h, dom, mon, dow = parts
    if cron_str == "0 0 * * *":
        return "Every day at 12:00 AM (Midnight)"
    if cron_str == "0 12 * * *":
        return "Every day at 12:00 PM (Noon)"
    if m.isdigit() and h.isdigit() and dom == "*" and mon == "*" and dow == "*":
        h_int = int(h)
        ampm = "AM" if h_int < 12 else "PM"
        h12 = h_int % 12 or 12
        return f"Every day at {h12}:{int(m):02d} {ampm}"
    if m.isdigit() and h == "*" and dom == "*" and mon == "*" and dow == "*":
        return f"Every hour at minute {m}"
    if m.startswith("*/") and h == "*" and dom == "*" and mon == "*" and dow == "*":
        return f"Every {m[2:]} minutes"
    if m == "0" and h.isdigit() and dow == "1-5":
        h_int = int(h)
        ampm = "AM" if h_int < 12 else "PM"
        h12 = h_int % 12 or 12
        return f"Monday to Friday at {h12}:00 {ampm}"
    return f"Cron: {cron_str}"


# ==========================================
# 3. JOB EXECUTION ENGINE
# ==========================================

active_executions = {} # job_id -> thread

def execute_job(job_id, trigger_type="scheduled"):
    """Executes a job, logs output, and records run history in SQLite."""
    conn = get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
    job = c.fetchone()
    if not job:
        conn.close()
        return

    job_name = job["name"]
    command = job["command"]
    working_dir = job["working_dir"] or PROJECT_ROOT
    timeout = job["timeout_seconds"] or 300
    start_time = datetime.now()
    started_at_iso = start_time.isoformat()

    # Create running history entry
    c.execute("""
    INSERT INTO run_history (job_id, job_name, trigger_type, started_at, status, output)
    VALUES (?, ?, ?, ?, 'running', 'Execution started...')
    """, (job_id, job_name, trigger_type, started_at_iso))
    history_id = c.lastrowid

    # Update job's last_status
    c.execute("UPDATE jobs SET last_status = 'running', last_run_at = ? WHERE id = ?", (started_at_iso, job_id))
    conn.commit()
    conn.close()

    print(f"[*] [{datetime.now().strftime('%H:%M:%S')}] Started Job #{job_id}: '{job_name}' ({trigger_type})")

    status = "failed"
    exit_code = -1
    output = ""

    try:
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=working_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1
        )

        try:
            out, _ = proc.communicate(timeout=timeout)
            output = out or ""
            exit_code = proc.returncode
            status = "success" if exit_code == 0 else "failed"
        except subprocess.TimeoutExpired:
            proc.kill()
            out, _ = proc.communicate()
            output = (out or "") + f"\n\n[ERROR] Execution timed out after {timeout} seconds."
            status = "timeout"
            exit_code = 124

    except Exception as e:
        output = f"[CRITICAL ERROR] Failed to spawn process: {e}"
        status = "failed"
        exit_code = -1

    end_time = datetime.now()
    duration = round((end_time - start_time).total_seconds(), 2)
    ended_at_iso = end_time.isoformat()

    conn = get_db()
    c = conn.cursor()
    c.execute("""
    UPDATE run_history
    SET ended_at = ?, duration_seconds = ?, status = ?, exit_code = ?, output = ?
    WHERE id = ?
    """, (ended_at_iso, duration, status, exit_code, output, history_id))

    next_run_iso = None
    if job["cron_expression"]:
        next_dt = calculate_next_cron_run(job["cron_expression"], end_time)
        next_run_iso = next_dt.isoformat() if next_dt else None

    c.execute("""
    UPDATE jobs
    SET last_status = ?, last_duration = ?, next_run_at = ?
    WHERE id = ?
    """, (status, duration, next_run_iso, job_id))

    conn.commit()
    conn.close()

    print(f"[+] [{datetime.now().strftime('%H:%M:%S')}] Finished Job #{job_id}: '{job_name}' -> {status} ({duration}s)")


# ==========================================
# 4. BACKGROUND SCHEDULER THREAD
# ==========================================

def scheduler_loop():
    """Background daemon checking every 1 second for due jobs."""
    print("[*] CronMaster Background Scheduler initialized.")
    while True:
        try:
            now = datetime.now()
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT id, name, cron_expression, enabled, next_run_at FROM jobs WHERE enabled = 1")
            jobs = c.fetchall()

            for job in jobs:
                job_id = job["id"]
                next_run_str = job["next_run_at"]

                if not next_run_str and job["cron_expression"]:
                    next_dt = calculate_next_cron_run(job["cron_expression"], now)
                    if next_dt:
                        c.execute("UPDATE jobs SET next_run_at = ? WHERE id = ?", (next_dt.isoformat(), job_id))
                        conn.commit()
                    continue

                if next_run_str:
                    next_run_dt = datetime.fromisoformat(next_run_str)
                    if now >= next_run_dt:
                        if job_id not in active_executions or not active_executions[job_id].is_alive():
                            t = threading.Thread(target=execute_job, args=(job_id, "scheduled"), daemon=True)
                            active_executions[job_id] = t
                            t.start()

                            next_dt = calculate_next_cron_run(job["cron_expression"], now)
                            next_iso = next_dt.isoformat() if next_dt else None
                            c.execute("UPDATE jobs SET next_run_at = ? WHERE id = ?", (next_iso, job_id))
                            conn.commit()

            conn.close()
        except Exception as e:
            print(f"[!] Scheduler error: {e}")

        time.sleep(1)


# ==========================================
# 5. HTTP REST API HANDLER
# ==========================================

class SchedulerAPIHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        if self.path.startswith("/api/"):
            super().log_message(format, *args)

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.end_headers()

    def read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length > 0:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        return {}

    # --- GET Requests ---
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        # 1. System Info
        if path == "/api/system":
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM jobs WHERE enabled = 1")
            active_jobs = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM jobs")
            total_jobs = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM run_history")
            total_runs = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM run_history WHERE status = 'success'")
            success_runs = c.fetchone()[0]
            c.execute("SELECT next_run_at FROM jobs WHERE enabled = 1 AND next_run_at IS NOT NULL ORDER BY next_run_at ASC LIMIT 1")
            next_row = c.fetchone()
            next_overall_run = next_row[0] if next_row else None
            conn.close()

            success_rate = round((success_runs / total_runs * 100), 1) if total_runs > 0 else 100.0

            return self.send_json({
                "server_time": datetime.now().isoformat(),
                "active_jobs": active_jobs,
                "total_jobs": total_jobs,
                "total_runs": total_runs,
                "success_rate": success_rate,
                "next_scheduled_run": next_overall_run,
                "os": sys.platform,
                "python_version": sys.version.split()[0]
            })

        # 2. List Jobs
        if path == "/api/jobs":
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM jobs ORDER BY id ASC")
            jobs = [dict(row) for row in c.fetchall()]
            for j in jobs:
                j["human_schedule"] = human_readable_cron(j["cron_expression"])
            conn.close()
            return self.send_json(jobs)

        # 3. Get Single Job
        m_job = re.match(r"^/api/jobs/(\d+)$", path)
        if m_job:
            job_id = int(m_job.group(1))
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM jobs WHERE id = ?", (job_id,))
            row = c.fetchone()
            conn.close()
            if not row:
                return self.send_json({"error": "Job not found"}, 404)
            data = dict(row)
            data["human_schedule"] = human_readable_cron(data["cron_expression"])
            return self.send_json(data)

        # 4. Run History (filtered or global)
        if path == "/api/history":
            limit = int(qs.get("limit", [50])[0])
            offset = int(qs.get("offset", [0])[0])
            job_id = qs.get("job_id", [None])[0]
            status_filter = qs.get("status", [None])[0]

            query = "SELECT id, job_id, job_name, trigger_type, started_at, ended_at, duration_seconds, status, exit_code FROM run_history"
            params = []
            conditions = []
            if job_id:
                conditions.append("job_id = ?")
                params.append(job_id)
            if status_filter and status_filter != "all":
                conditions.append("status = ?")
                params.append(status_filter)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY id DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])

            conn = get_db()
            c = conn.cursor()
            c.execute(query, tuple(params))
            items = [dict(row) for row in c.fetchall()]
            conn.close()
            return self.send_json(items)

        # 5. Get Single Run Detail with Full Output Log
        m_hist = re.match(r"^/api/history/(\d+)$", path)
        if m_hist:
            hist_id = int(m_hist.group(1))
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT * FROM run_history WHERE id = ?", (hist_id,))
            row = c.fetchone()
            conn.close()
            if not row:
                return self.send_json({"error": "History entry not found"}, 404)
            return self.send_json(dict(row))

        # 6. Read BuildingLink Config
        if path == "/api/buildinglink/config":
            cfg_path = get_config_path()
            if os.path.exists(cfg_path):
                try:
                    with open(cfg_path, "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                    return self.send_json(cfg)
                except Exception as e:
                    return self.send_json({"error": str(e)}, 500)
            
            # Return safe default template if config doesn't exist
            default_cfg = {
                "username": "nbyadarahalli",
                "password": "",
                "amenity_id": "ba1bb1f4-980e-400c-8892-30dc37d20473",
                "amenity_name": "Badminton Court",
                "preferred_times": ["19:00", "20:00", "18:00", "21:00", "08:00", "09:00"],
                "days_ahead": 1,
                "description": ""
            }
            return self.send_json(default_cfg)

        # 7. Serve Static Files (SPA)
        return self.serve_static(path)

    # --- POST Requests ---
    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        # 1. Create Job
        if path == "/api/jobs":
            data = self.read_json_body()
            name = data.get("name", "").strip()
            command = data.get("command", "").strip()
            cron_expr = data.get("cron_expression", "0 0 * * *").strip()
            description = data.get("description", "").strip()
            working_dir = data.get("working_dir", "").strip() or PROJECT_ROOT
            timeout = int(data.get("timeout_seconds", 300))
            enabled = 1 if data.get("enabled", True) else 0

            if not name or not command:
                return self.send_json({"error": "Name and command are required"}, 400)

            now_iso = datetime.now().isoformat()
            next_dt = calculate_next_cron_run(cron_expr, datetime.now()) if enabled else None
            next_iso = next_dt.isoformat() if next_dt else None

            conn = get_db()
            c = conn.cursor()
            c.execute("""
            INSERT INTO jobs (name, description, command, working_dir, cron_expression, enabled, timeout_seconds, next_run_at, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, description, command, working_dir, cron_expr, enabled, timeout, next_iso, now_iso, now_iso))
            new_id = c.lastrowid
            conn.commit()
            conn.close()

            return self.send_json({"id": new_id, "message": "Job created successfully"}, 201)

        # 2. Toggle Job (On/Off)
        m_toggle = re.match(r"^/api/jobs/(\d+)/toggle$", path)
        if m_toggle:
            job_id = int(m_toggle.group(1))
            conn = get_db()
            c = conn.cursor()
            c.execute("SELECT enabled, cron_expression FROM jobs WHERE id = ?", (job_id,))
            row = c.fetchone()
            if not row:
                conn.close()
                return self.send_json({"error": "Job not found"}, 404)

            new_state = 0 if row["enabled"] == 1 else 1
            next_iso = None
            if new_state == 1:
                next_dt = calculate_next_cron_run(row["cron_expression"], datetime.now())
                next_iso = next_dt.isoformat() if next_dt else None

            c.execute("UPDATE jobs SET enabled = ?, next_run_at = ?, updated_at = ? WHERE id = ?",
                      (new_state, next_iso, datetime.now().isoformat(), job_id))
            conn.commit()
            conn.close()
            return self.send_json({"id": job_id, "enabled": bool(new_state), "next_run_at": next_iso})

        # 3. Trigger Job Run Now
        m_run = re.match(r"^/api/jobs/(\d+)/run$", path)
        if m_run:
            job_id = int(m_run.group(1))
            t = threading.Thread(target=execute_job, args=(job_id, "manual"), daemon=True)
            t.start()
            return self.send_json({"id": job_id, "message": "Execution started in background"})

        # 4. Save BuildingLink Config
        if path == "/api/buildinglink/config":
            data = self.read_json_body()
            cfg_path = get_config_path()
            try:
                with open(cfg_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                return self.send_json({"message": "BuildingLink configuration updated successfully"})
            except Exception as e:
                return self.send_json({"error": str(e)}, 500)

        # 5. Dedicated BuildingLink Dry-Run Execution
        if path == "/api/buildinglink/dry-run":
            python_cmd = "python3" if sys.platform != "win32" else "py"
            cmd = f"{python_cmd} buildinglink_bot.py --dry-run"
            try:
                proc = subprocess.Popen(
                    cmd,
                    shell=True,
                    cwd=PROJECT_ROOT,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True
                )
                output, _ = proc.communicate(timeout=60)
                return self.send_json({
                    "exit_code": proc.returncode,
                    "output": output
                })
            except Exception as e:
                return self.send_json({"error": str(e)}, 500)

        self.send_json({"error": "Endpoint not found"}, 404)

    # --- PUT Requests ---
    def do_PUT(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        m_job = re.match(r"^/api/jobs/(\d+)$", path)
        if m_job:
            job_id = int(m_job.group(1))
            data = self.read_json_body()

            name = data.get("name", "").strip()
            command = data.get("command", "").strip()
            cron_expr = data.get("cron_expression", "").strip()
            description = data.get("description", "").strip()
            working_dir = data.get("working_dir", "").strip() or PROJECT_ROOT
            timeout = int(data.get("timeout_seconds", 300))
            enabled = 1 if data.get("enabled", True) else 0

            next_dt = calculate_next_cron_run(cron_expr, datetime.now()) if enabled else None
            next_iso = next_dt.isoformat() if next_dt else None

            conn = get_db()
            c = conn.cursor()
            c.execute("""
            UPDATE jobs
            SET name = ?, description = ?, command = ?, working_dir = ?,
                cron_expression = ?, enabled = ?, timeout_seconds = ?,
                next_run_at = ?, updated_at = ?
            WHERE id = ?
            """, (name, description, command, working_dir, cron_expr, enabled, timeout, next_iso, datetime.now().isoformat(), job_id))
            conn.commit()
            conn.close()

            return self.send_json({"id": job_id, "message": "Job updated successfully"})

        self.send_json({"error": "Endpoint not found"}, 404)

    # --- DELETE Requests ---
    def do_DELETE(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        m_job = re.match(r"^/api/jobs/(\d+)$", path)
        if m_job:
            job_id = int(m_job.group(1))
            conn = get_db()
            c = conn.cursor()
            c.execute("DELETE FROM run_history WHERE job_id = ?", (job_id,))
            c.execute("DELETE FROM jobs WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
            return self.send_json({"id": job_id, "message": "Job deleted successfully"})

        self.send_json({"error": "Endpoint not found"}, 404)

    # --- Static File Handler ---
    def serve_static(self, path):
        if path == "/" or path == "":
            path = "/index.html"

        rel_path = path.lstrip("/")
        full_path = os.path.abspath(os.path.join(STATIC_DIR, rel_path))

        if not full_path.startswith(os.path.abspath(STATIC_DIR)):
            self.send_response(403)
            self.end_headers()
            return

        if os.path.exists(full_path) and os.path.isfile(full_path):
            mime, _ = mimetypes.guess_type(full_path)
            mime = mime or "application/octet-stream"
            try:
                with open(full_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(content)))
                self.end_headers()
                self.wfile.write(content)
                return
            except Exception as e:
                self.send_response(500)
                self.end_headers()
                return

        index_file = os.path.join(STATIC_DIR, "index.html")
        if os.path.exists(index_file):
            with open(index_file, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
            return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"404 Not Found")


# ==========================================
# 6. MAIN LAUNCHER
# ==========================================

def run_server():
    init_db()

    scheduler_thread = threading.Thread(target=scheduler_loop, daemon=True)
    scheduler_thread.start()

    server = ThreadedHTTPServer((HOST, PORT), SchedulerAPIHandler)
    print(f"\n=======================================================")
    print(f"  CronMaster Scheduler Web Dashboard is Running!      ")
    print(f"  URL: http://localhost:{PORT}                          ")
    print(f"  Network: http://{HOST}:{PORT}                         ")
    print(f"=======================================================\n")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[*] Shutting down CronMaster server...")
        server.shutdown()


if __name__ == "__main__":
    run_server()
