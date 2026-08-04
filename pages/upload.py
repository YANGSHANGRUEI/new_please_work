import sys
from pathlib import Path
import os

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
from datetime import datetime

from utils.answers_store import (
    GRADE_OPTIONS,
    MIN_ANSWER_CHARS,
    MIN_ANSWER_HINT,
    find_similar_upload,
    format_label,
    load_answers,
    save_answers,
    user_has_combo_upload,
)
from utils.session import restore_login
from utils.taxonomy import (
    build_year_value,
    list_academic_years,
    list_exam_periods,
    list_fields,
    list_semesters,
    list_subjects,
    list_teachers,
    load_taxonomy,
)
from utils.user_store import add_tokens
from utils.openai_client import check_ai_generated
from utils.openai_client import find_embedding_duplicate
from utils.openai_client import check_relevance
from utils.openai_client import resolve_openai_api_key

st.title("上傳作答")

restore_login(st)

if not st.session_state.get("logged_in"):
    st.warning("請先登入才能上傳")
    st.stop()

taxonomy = load_taxonomy()
fields = list_fields(taxonomy)
if not fields:
    st.error("題庫目錄尚未設定")
    st.stop()

field = st.selectbox("法領域", fields)
subjects = list_subjects(field, taxonomy)
if not subjects:
    st.warning("此法領域尚無科目")
    st.stop()
subject = st.selectbox("科目", subjects)

teachers = list_teachers(field, subject, taxonomy)
if not teachers:
    st.warning("此科目尚無老師")
    st.stop()
teacher = st.selectbox("老師", teachers)

academic_years = list_academic_years(field, subject, teacher, taxonomy)
if not academic_years:
    st.warning("此老師尚無學年資料")
    st.stop()
academic_year = st.selectbox("學年", academic_years)

semesters = list_semesters(field, subject, teacher, academic_year, taxonomy)
if not semesters:
    st.warning("此學年尚無學期資料")
    st.stop()
semester = st.selectbox("學期", semesters)

exam_periods = list_exam_periods(
    field, subject, teacher, academic_year, semester, taxonomy
)
if not exam_periods:
    st.warning("此學期尚無期中/期末資料")
    st.stop()
exam_period = st.selectbox("期中/期末", exam_periods)

year = build_year_value(academic_year, semester, exam_period)

score = st.number_input("本卷分數", min_value=0, max_value=100, step=1)
grade = st.selectbox("期末等第", GRADE_OPTIONS)
score_value = str(int(score))

answer_text = st.text_area("請貼上你的作答", height=200)
char_count = len(answer_text.strip())
st.caption(f"目前 {char_count} 字（至少 {MIN_ANSWER_HINT}）")

if st.button("提交"):
    normalized_answer = answer_text.strip()
    base_warning = "您的輸入行為不符合誠信原則，請自重。"

    if normalized_answer == "":
        st.warning("請輸入作答")
    elif char_count < MIN_ANSWER_CHARS:
        st.warning(f"作答至少 {MIN_ANSWER_HINT}，目前只有 {char_count} 字")
    else:
        openai_api_key = resolve_openai_api_key()
        relevance = check_relevance(normalized_answer, api_key=openai_api_key)
        if "error" in relevance:
            st.error(f"內容判定失敗：{relevance['error']}")
            st.stop()
        if not relevance.get("is_answer"):
            st.warning(f"{base_warning}（原因：無關內容）")
            st.stop()

        ai_generated = check_ai_generated(normalized_answer, api_key=openai_api_key)
        if "error" in ai_generated:
            st.error(f"AI 生成判定失敗：{ai_generated['error']}")
            st.stop()
        if ai_generated.get("is_ai_generated"):
            st.warning(f"{base_warning}（原因：疑似 AI 生成）")
            st.stop()

        existing = load_answers()

        # 使用 embeddings 與現有答案比對，以偵測貼上或幾乎相同的內容
        emb_dup = find_embedding_duplicate(normalized_answer, existing, api_key=openai_api_key, threshold=0.92)
        if isinstance(emb_dup, dict) and emb_dup.get("error"):
            # 審查非關鍵錯誤，僅記 log 並繼續
            st.caption(f"(注意) 嵌入比對失敗：{emb_dup['error']}")
        elif emb_dup:
            dup_ans = emb_dup.get("answer")
            sim = emb_dup.get("score")
            dup_label = format_label(dup_ans) if isinstance(dup_ans, dict) else "未分類"
            st.warning(
                f"作答內容與平台上既有內容高度相似（相似度 {sim:.2f}，{dup_label}），請勿重複提交。"
            )
            st.stop()
        user_id = st.session_state["user_id"]
        if user_has_combo_upload(
            user_id, field, subject, teacher, year, score_value, grade, existing
        ):
            st.warning(f"{base_warning}（原因：同分類已上傳過作答）")
        else:
            similar = find_similar_upload(normalized_answer, existing)
            if similar:
                st.warning(f"{base_warning}（原因：內容與既有作答過於相似）")
            else:
                existing.append(
                    {
                        "field": field,
                        "subject": subject,
                        "teacher": teacher,
                        "year": year,
                        "score": score_value,
                        "grade": grade,
                        "answer_text": normalized_answer,
                        "upload_time": datetime.now().isoformat(),
                        "uploader_id": user_id,
                    }
                )
                try:
                    save_answers(existing)
                except Exception as e:
                    st.error(f"寫入試算表失敗：{e}")
                    st.stop()

                username = st.session_state["username"]
                new_balance = add_tokens(username, 3)
                if new_balance is None:
                    st.error("找不到使用者，請重新登入")
                    st.stop()
                st.success(
                    f"上傳成功！{field}｜{subject}｜{teacher}｜{year}｜"
                    f"{score_value}分｜等第{grade}，"
                    f"獲得 3 代幣，目前餘額：{new_balance}"
                )
