import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import requests

QUESTIONS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "questions.json"
)


def combo_key(field: str, subject: str, teacher: str, year: str) -> str:
    return f"{field}::{subject}::{teacher}::{year}"


def _parse_simple_toml(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}

    values: dict[str, str] = {}
    try:
        content = path.read_text(encoding="utf-8")
    except Exception:
        return {}

    for raw_line in content.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        if value.startswith(('"', "'")) and value.endswith(('"', "'")) and len(value) >= 2:
            value = value[1:-1]
        values[key] = value
    return values


def _get_local_secrets() -> dict[str, str]:
    candidates = [
        Path.cwd() / ".streamlit" / "secrets.toml",
        Path.cwd() / "secrets.toml",
        Path(__file__).resolve().parents[1] / ".streamlit" / "secrets.toml",
        Path(__file__).resolve().parents[1] / "secrets.toml",
    ]
    for candidate in candidates:
        data = _parse_simple_toml(candidate)
        if data:
            return data
    return {}


def _get_supabase_config():
    try:
        import streamlit as st
    except Exception:
        st = None

    local_secrets = _get_local_secrets()

    def normalize(value):
        if value is None:
            return None
        if isinstance(value, str):
            value = value.strip()
            if not value:
                return None
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1].strip()
            return value
        return str(value)

    def read_secret(name: str):
        if st is not None:
            try:
                value = st.secrets.get(name)
            except Exception:
                value = None
            if value is not None:
                return normalize(value)
        value = local_secrets.get(name)
        return normalize(value)

    def read_value(*names):
        for name in names:
            value = normalize(os.getenv(name))
            if value:
                return value
            value = read_secret(name)
            if value:
                return value
        return None

    url = read_value("SUPABASE_URL")
    key = read_value("SUPABASE_ANON_KEY", "SUPABASE_SERVICE_ROLE_KEY")
    table = read_value("SUPABASE_QUESTIONS_TABLE") or "questions"

    if isinstance(url, str):
        url = url.strip().rstrip("/")
        if url.endswith("/rest/v1"):
            url = url[:-len("/rest/v1")]
    return url, key, table


def _format_supabase_error(response, fallback: str = "") -> str:
    if response is None:
        return fallback or "Supabase 請求失敗"
    try:
        body = response.text
    except Exception:
        body = ""
    if response.status_code == 401:
        return "Supabase 驗證失敗：請確認 anon key 或 service role key 是否正確，且 RLS 政策是否允許讀取。"
    if response.status_code == 403:
        return "Supabase 權限不足：請確認 RLS 政策或使用 service role key。"
    if response.status_code == 404:
        return "Supabase 找不到指定表格：請確認 SUPABASE_QUESTIONS_TABLE 是否正確。"
    return f"Supabase 讀取失敗（HTTP {response.status_code}）：{body or fallback}".strip()


def _load_from_supabase():
    url, key, table = _get_supabase_config()
    if not url or not key:
        return {}, "Supabase 未設定：請在 Secrets 或環境變數中填入 SUPABASE_URL、SUPABASE_ANON_KEY 與 SUPABASE_QUESTIONS_TABLE。"

    try:
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        base_url = url.rstrip("/")
        if not base_url.endswith("/rest/v1"):
            base_url = f"{base_url}/rest/v1"
        response = requests.get(
            f"{base_url}/{table}?select=field,subject,teacher,year,question_text,question_link,upload_time,uploader_id",
            headers=headers,
            timeout=10,
        )
        if response.status_code != 200:
            return {}, _format_supabase_error(response)
        rows = response.json() or []
    except Exception as exc:
        return {}, f"Supabase 連線異常：{exc}"

    questions: dict[str, dict[str, Any]] = {}
    for row in rows:
        field = row.get("field") or row.get("Field") or row.get("law_field") or row.get("category") or ""
        subject = row.get("subject") or row.get("Subject") or row.get("law_subject") or ""
        teacher = row.get("teacher") or row.get("Teacher") or row.get("law_teacher") or ""
        year = (
            row.get("year")
            or row.get("Year")
            or row.get("academic_year")
            or row.get("exam_year")
            or ""
        )
        semester = row.get("semester") or row.get("Semester") or row.get("term") or ""
        time_value = row.get("time") or row.get("Time") or row.get("exam_period") or row.get("period") or ""

        if not (field and subject and teacher and year):
            continue

        # 兼容你現在的欄位結構：year + semester + time 會被組合成網站所需的 year 值
        if semester or time_value:
            if year and semester and time_value:
                year = f"{year}-{semester}-{time_value}"
            elif year and semester:
                year = f"{year}-{semester}"
            elif year and time_value:
                year = f"{year}-{time_value}"

        combo = combo_key(field, subject, teacher, year)
        questions[combo] = {
            "question_text": (
                row.get("question_text")
                or row.get("question")
                or row.get("title")
                or row.get("questionTitle")
                or row.get("QuestionText")
                or row.get("content")
                or row.get("description")
                or ""
            ),
            "question_link": (
                row.get("question_link")
                or row.get("link")
                or row.get("url")
                or row.get("URL")
                or row.get("question_url")
                or row.get("questionUrl")
                or row.get("questionLink")
                or row.get("QuestionURL")
                or ""
            ),
            "upload_time": row.get("upload_time") or row.get("created_at") or "",
            "uploader_id": row.get("uploader_id") or row.get("created_by") or "",
        }
    return questions, None


def load_questions() -> dict:
    questions, _ = _load_from_supabase()
    return questions


def load_questions_with_status():
    questions, error = _load_from_supabase()
    if questions or error is None:
        return questions, error

    if os.path.exists(QUESTIONS_FILE):
        with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
            return json.load(f), error
    return {}, error


def get_question(field: str, subject: str, teacher: str, year: str):
    questions, _ = load_questions_with_status()
    return questions.get(combo_key(field, subject, teacher, year))


def save_question(
    field: str,
    subject: str,
    teacher: str,
    year: str,
    question_text: str,
    uploader_id: str,
) -> None:
    questions = load_questions()
    questions[combo_key(field, subject, teacher, year)] = {
        "question_text": question_text,
        "upload_time": datetime.now().isoformat(),
        "uploader_id": uploader_id,
    }
    os.makedirs(os.path.dirname(QUESTIONS_FILE), exist_ok=True)
    with open(QUESTIONS_FILE, "w", encoding="utf-8") as f:
        json.dump(questions, f, ensure_ascii=False, indent=2)
