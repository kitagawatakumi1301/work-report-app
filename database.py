"""
database.py
-----------
データベース操作モジュール。

接続先の自動判定:
  - Streamlit Secrets に DATABASE_URL が設定されている場合 → PostgreSQL (Supabase)
  - 設定がない場合 → ローカルのSQLite (data/work_report.db)
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


# ─────────────────────────────────────────
# DB接続モードの自動判定
# ─────────────────────────────────────────

def _detect_db_mode():
    """
    Streamlit SecretsまたはDATABASE_URL環境変数を確認し、
    接続モードとURLを返す。
    """
    # Streamlit Secrets から取得を試みる
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL", None)
        if url:
            return "postgres", url
    except Exception:
        pass
    # 環境変数から取得
    url = os.environ.get("DATABASE_URL")
    if url:
        return "postgres", url
    # フォールバック: SQLite
    return "sqlite", None


_DB_MODE, _POSTGRES_URL = _detect_db_mode()

# SQLite設定（ローカル開発用）
_DB_DIR = Path(__file__).parent / "data"
_DB_PATH = _DB_DIR / "work_report.db"

# SQLプレースホルダー（SQLite: ?, PostgreSQL: %s）
PH = "?" if _DB_MODE == "sqlite" else "%s"


# ─────────────────────────────────────────
# 接続・ユーティリティ
# ─────────────────────────────────────────

def get_connection():
    """DBへの接続を取得する（DB種別を自動判定）"""
    if _DB_MODE == "postgres":
        import psycopg2
        conn = psycopg2.connect(_POSTGRES_URL)
        return conn
    else:
        _DB_DIR.mkdir(exist_ok=True)
        conn = sqlite3.connect(str(_DB_PATH))
        conn.row_factory = sqlite3.Row
        return conn


def _fetchall(cursor) -> list:
    """カーソルから全行を辞書リストとして返す（DB種別非依存）"""
    if _DB_MODE == "postgres":
        cols = [desc[0] for desc in cursor.description]
        return [dict(zip(cols, row)) for row in cursor.fetchall()]
    else:
        return [dict(row) for row in cursor.fetchall()]


def _fetchone(cursor):
    """カーソルから1行を辞書として返す（DB種別非依存）"""
    if _DB_MODE == "postgres":
        row = cursor.fetchone()
        if row is None:
            return None
        cols = [desc[0] for desc in cursor.description]
        return dict(zip(cols, row))
    else:
        row = cursor.fetchone()
        return dict(row) if row else None


def _q(sql: str) -> str:
    """SQLite用の?プレースホルダーをPostgreSQL用の%sに変換する"""
    if _DB_MODE == "postgres":
        return sql.replace("?", "%s")
    return sql


# ─────────────────────────────────────────
# DB初期化
# ─────────────────────────────────────────

def initialize_db():
    """
    データベースとテーブルを初期化する。
    テーブルが存在しない場合のみ作成する（既存データは保持）。
    """
    conn = get_connection()
    cursor = conn.cursor()

    if _DB_MODE == "postgres":
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_reports (
                id           SERIAL PRIMARY KEY,
                work_date    TEXT NOT NULL,
                worker_name  TEXT NOT NULL,
                team         TEXT NOT NULL,
                process_id   TEXT NOT NULL,
                process_name TEXT NOT NULL,
                process_type TEXT NOT NULL,
                start_time   TEXT NOT NULL,
                end_time     TEXT NOT NULL,
                hours        REAL NOT NULL,
                work_place   TEXT NOT NULL,
                note         TEXT,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL,
                deleted      INTEGER DEFAULT 0
            )
        """)
    else:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS work_reports (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                work_date    TEXT NOT NULL,
                worker_name  TEXT NOT NULL,
                team         TEXT NOT NULL,
                process_id   TEXT NOT NULL,
                process_name TEXT NOT NULL,
                process_type TEXT NOT NULL,
                start_time   TEXT NOT NULL,
                end_time     TEXT NOT NULL,
                hours        REAL NOT NULL,
                work_place   TEXT NOT NULL,
                note         TEXT,
                created_at   TEXT NOT NULL,
                updated_at   TEXT NOT NULL,
                deleted      INTEGER DEFAULT 0
            )
        """)

    conn.commit()
    conn.close()


# ─────────────────────────────────────────
# CRUD操作
# ─────────────────────────────────────────

def insert_report(data: dict) -> int:
    """
    新しい作業日報をDBに挿入する。

    Returns:
        挿入したレコードのid
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cursor = conn.cursor()

    if _DB_MODE == "postgres":
        cursor.execute("""
            INSERT INTO work_reports (
                work_date, worker_name, team,
                process_id, process_name, process_type,
                start_time, end_time, hours,
                work_place, note,
                created_at, updated_at, deleted
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 0)
            RETURNING id
        """, (
            data["work_date"], data["worker_name"], data["team"],
            data["process_id"], data["process_name"], data["process_type"],
            data["start_time"], data["end_time"], data["hours"],
            data["work_place"], data.get("note", ""),
            now, now
        ))
        new_id = cursor.fetchone()[0]
    else:
        cursor.execute("""
            INSERT INTO work_reports (
                work_date, worker_name, team,
                process_id, process_name, process_type,
                start_time, end_time, hours,
                work_place, note,
                created_at, updated_at, deleted
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)
        """, (
            data["work_date"], data["worker_name"], data["team"],
            data["process_id"], data["process_name"], data["process_type"],
            data["start_time"], data["end_time"], data["hours"],
            data["work_place"], data.get("note", ""),
            now, now
        ))
        new_id = cursor.lastrowid

    conn.commit()
    conn.close()
    return new_id


def get_reports_by_worker(worker_name: str) -> list:
    """
    指定した作業者の日報一覧を取得する（論理削除済みは除く）。
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(_q("""
        SELECT * FROM work_reports
        WHERE worker_name = ? AND deleted = 0
        ORDER BY work_date DESC, start_time DESC
    """), (worker_name,))
    rows = _fetchall(cursor)
    conn.close()
    return rows


def get_all_reports() -> list:
    """
    全作業者の日報一覧を取得する（論理削除済みは除く）。
    管理者画面用。
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT * FROM work_reports
        WHERE deleted = 0
        ORDER BY work_date DESC, worker_name, start_time
    """)
    rows = _fetchall(cursor)
    conn.close()
    return rows


def get_report_by_id(report_id: int) -> dict | None:
    """
    IDで日報を1件取得する。
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(_q("""
        SELECT * FROM work_reports
        WHERE id = ? AND deleted = 0
    """), (report_id,))
    row = _fetchone(cursor)
    conn.close()
    return row


def update_report(report_id: int, data: dict) -> bool:
    """
    日報を更新する。updated_atを現在時刻に更新する。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(_q("""
        UPDATE work_reports SET
            work_date    = ?,
            team         = ?,
            process_id   = ?,
            process_name = ?,
            process_type = ?,
            start_time   = ?,
            end_time     = ?,
            hours        = ?,
            work_place   = ?,
            note         = ?,
            updated_at   = ?
        WHERE id = ? AND deleted = 0
    """), (
        data["work_date"], data["team"],
        data["process_id"], data["process_name"], data["process_type"],
        data["start_time"], data["end_time"], data["hours"],
        data["work_place"], data.get("note", ""),
        now, report_id
    ))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


def delete_report(report_id: int) -> bool:
    """
    日報を論理削除する（deleted = 1 に更新）。
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(_q("""
        UPDATE work_reports
        SET deleted = 1, updated_at = ?
        WHERE id = ? AND deleted = 0
    """), (now, report_id))
    conn.commit()
    success = cursor.rowcount > 0
    conn.close()
    return success


def _time_to_minutes(value: str) -> int:
    hour, minute = map(int, value.split(":"))
    return hour * 60 + minute


def _date_candidates(work_date: str) -> list:
    base = datetime.strptime(work_date, "%Y-%m-%d").date()
    return [
        (base - timedelta(days=1)).strftime("%Y-%m-%d"),
        base.strftime("%Y-%m-%d"),
        (base + timedelta(days=1)).strftime("%Y-%m-%d"),
    ]


def _interval_minutes(row: dict, base_date: str) -> tuple:
    base = datetime.strptime(base_date, "%Y-%m-%d").date()
    row_date = datetime.strptime(row["work_date"], "%Y-%m-%d").date()
    day_offset = (row_date - base).days * 24 * 60
    start = day_offset + _time_to_minutes(row["start_time"])
    end = day_offset + _time_to_minutes(row["end_time"])
    if end <= start:
        end += 24 * 60
    return start, end


def check_overlap(
    worker_name: str,
    work_date: str,
    start_time: str,
    end_time: str,
    exclude_id: int = None
) -> list:
    """
    時間帯が重複する既存の日報を検索する。
    終了時刻が開始時刻より前の場合は、翌日終了として判定する。
    """
    conn = get_connection()
    cursor = conn.cursor()

    dates = _date_candidates(work_date)
    placeholders = ", ".join(["?"] * len(dates))
    query = _q("""
        SELECT * FROM work_reports
        WHERE worker_name = ?
          AND work_date   IN ({placeholders})
          AND deleted     = 0
    """.format(placeholders=placeholders))
    params = [worker_name] + dates

    if exclude_id is not None:
        query += _q(" AND id != ?")
        params.append(exclude_id)

    cursor.execute(query, params)
    candidates = _fetchall(cursor)
    conn.close()

    new_start, new_end = _interval_minutes(
        {"work_date": work_date, "start_time": start_time, "end_time": end_time},
        work_date,
    )
    return [
        row for row in candidates
        if _interval_minutes(row, work_date)[0] < new_end
        and _interval_minutes(row, work_date)[1] > new_start
    ]


# ─────────────────────────────────────────
# 集計クエリ
# ─────────────────────────────────────────

def get_summary_monthly_user_hours() -> list:
    """【集計A】月別・作業者別 合計作業時間"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            substr(work_date, 1, 7) AS month,
            worker_name,
            SUM(hours) AS total_hours
        FROM work_reports
        WHERE deleted = 0
        GROUP BY substr(work_date, 1, 7), worker_name
        ORDER BY substr(work_date, 1, 7) DESC, worker_name
    """)
    rows = _fetchall(cursor)
    conn.close()
    return rows


def get_summary_monthly_user_process_hours() -> list:
    """【集計B】月別・作業者別・工程ID別 合計作業時間"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            substr(work_date, 1, 7) AS month,
            worker_name,
            process_id,
            process_name,
            SUM(hours) AS total_hours
        FROM work_reports
        WHERE deleted = 0
        GROUP BY substr(work_date, 1, 7), worker_name, process_id, process_name
        ORDER BY substr(work_date, 1, 7) DESC, worker_name, process_id
    """)
    rows = _fetchall(cursor)
    conn.close()
    return rows


def get_summary_e_attendance_days() -> list:
    """【集計C】E工程の出勤日数集計"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            substr(work_date, 1, 7)    AS month,
            worker_name,
            COUNT(DISTINCT work_date)  AS attendance_days
        FROM work_reports
        WHERE deleted = 0
          AND process_type = 'E'
        GROUP BY substr(work_date, 1, 7), worker_name
        ORDER BY substr(work_date, 1, 7) DESC, worker_name
    """)
    rows = _fetchall(cursor)
    conn.close()
    return rows


def get_summary_e_attendance_dates() -> list:
    """【集計C補足】E工程の出勤日一覧"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT
            substr(work_date, 1, 7) AS month,
            worker_name,
            work_date
        FROM work_reports
        WHERE deleted = 0
          AND process_type = 'E'
        ORDER BY substr(work_date, 1, 7) DESC, worker_name, work_date
    """)
    rows = _fetchall(cursor)
    conn.close()
    return rows


def get_summary_fr_hours() -> list:
    """【集計D】FR工程の作業時間集計"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            substr(work_date, 1, 7) AS month,
            worker_name,
            process_id,
            process_name,
            SUM(hours) AS total_hours
        FROM work_reports
        WHERE deleted = 0
          AND process_type = 'FR'
        GROUP BY substr(work_date, 1, 7), worker_name, process_id, process_name
        ORDER BY substr(work_date, 1, 7) DESC, worker_name, process_id
    """)
    rows = _fetchall(cursor)
    conn.close()
    return rows


def get_summary_process_hours() -> list:
    """【集計E】工程ID別 合計時間（月別）"""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT
            substr(work_date, 1, 7) AS month,
            process_id,
            process_name,
            SUM(hours) AS total_hours
        FROM work_reports
        WHERE deleted = 0
        GROUP BY substr(work_date, 1, 7), process_id, process_name
        ORDER BY substr(work_date, 1, 7) DESC, process_id
    """)
    rows = _fetchall(cursor)
    conn.close()
    return rows
