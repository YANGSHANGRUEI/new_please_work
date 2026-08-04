import json
import os
from datetime import datetime
from typing import Any

import requests

QUESTIONS_FILE = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "data", "questions.json"
)


def combo_key(field: str, subject: str, teacher: str, year: str) -> str:
    return f"{field}::{subject}::{teacher}::{year}"


def _get_supabase_config():
    try:
        import streamlit as st
    except Exception:
        st = None

    url = os.getenv("SUPABASE_URL") or (st.secrets.get("SUPABASE_URL") if st else None)
    key = (
        os.getenv("SUPABASE_ANON_KEY")
        or os.getenv("SUPABASE_SERVICE_ROLE_KEY")
        or (st.secrets.get("SUPABASE_ANON_KEY") if st else None)
        or (st.secrets.get("SUPABASE_SERVICE_ROLE_KEY") if st else None)
    )
    table = os.getenv("SUPABASE_QUESTIONS_TABLE") or (st.secrets.get("SUPABASE_QUESTIONS_TABLE") if st else None) or "questions"
    return url, key, table


def _load_from_supabase() -> dict[str, dict[str, Any]]:
    url, key, table = _get_supabase_config()
    if not url or not key:
        return {}

    try:
        headers = {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        response = requests.get(
            f"{url}/rest/v1/{table}?select=field,subject,teacher,year,question_text,question_link,upload_time,uploader_id",
            headers=headers,
            timeout=10,
        )
        if response.status_code != 200:
            return {}
        rows = response.json() or []
    except Exception:
        return {}

    questions: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not all(key_name in row for key_name in ("field", "subject", "teacher", "year")):
            continue
        combo = combo_key(row["field"], row["subject"], row["teacher"], row["year"])
        questions[combo] = {
            "question_text": row.get("question_text") or row.get("title") or "",
            "question_link": row.get("question_link") or row.get("link") or row.get("url") or "",
            "upload_time": row.get("upload_time") or "",
            "uploader_id": row.get("uploader_id") or "",
        }
    return questions


def load_questions() -> dict:
    supabase_questions = _load_from_supabase()
    if supabase_questions:
        return supabase_questions

    if not os.path.exists(QUESTIONS_FILE):
        return {}
    with open(QUESTIONS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def get_question(field: str, subject: str, teacher: str, year: str):
    questions = load_questions()
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
