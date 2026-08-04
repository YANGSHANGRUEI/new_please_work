import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st

from utils.answers_store import format_label, is_unlocked, load_answers, make_unlock_id, normalize_meta
from utils.questions_store import get_question
from utils.session import restore_login
from utils.users_store import load_users
from utils.taxonomy import (
    build_year_value,
    list_academic_years,
    list_exam_periods,
    list_fields,
    list_semesters,
    list_subjects,
    list_teachers,
    load_taxonomy,
    parse_year_parts,
)
from utils.user_store import unlock_with_cost

st.title("瀏覽題庫")

restore_login(st)

if not st.session_state.get("logged_in"):
    st.warning("請先登入才能瀏覽")
    st.stop()

users = load_users()

username = st.session_state["username"]
balance = users[username]["tokens"]
st.metric("我的代幣", balance)

taxonomy = load_taxonomy()


def matches_filter(
    ans: dict,
    field_filter: str,
    subject_filter: str,
    teacher_filter: str,
    academic_year_filter: str,
    semester_filter: str,
    exam_period_filter: str,
) -> bool:
    field, subject, teacher, year = normalize_meta(ans)
    if field_filter != "全部" and field != field_filter:
        return False
    if subject_filter != "全部" and subject != subject_filter:
        return False
    if teacher_filter != "全部" and teacher != teacher_filter:
        return False
    ay, sem, exam = parse_year_parts(year)
    if academic_year_filter != "全部" and ay != academic_year_filter:
        return False
    if semester_filter != "全部" and sem != semester_filter:
        return False
    if exam_period_filter != "全部" and exam != exam_period_filter:
        return False
    return True


st.subheader("題庫瀏覽")
col1, col2, col3 = st.columns(3)
col4, col5, col6 = st.columns(3)

with col1:
    field_filter = st.selectbox("法領域", ["全部"] + list_fields(taxonomy))

with col2:
    subject_options = (
        ["全部"] + list_subjects(field_filter, taxonomy)
        if field_filter != "全部"
        else ["全部"]
    )
    subject_filter = st.selectbox("科目", subject_options)

with col3:
    teacher_options = (
        ["全部"] + list_teachers(field_filter, subject_filter, taxonomy)
        if field_filter != "全部" and subject_filter != "全部"
        else ["全部"]
    )
    teacher_filter = st.selectbox("老師", teacher_options)

with col4:
    year_options = (
        ["全部"]
        + list_academic_years(field_filter, subject_filter, teacher_filter, taxonomy)
        if field_filter != "全部"
        and subject_filter != "全部"
        and teacher_filter != "全部"
        else ["全部"]
    )
    academic_year_filter = st.selectbox("學年", year_options)

with col5:
    semester_options = (
        ["全部"]
        + list_semesters(
            field_filter, subject_filter, teacher_filter, academic_year_filter, taxonomy
        )
        if field_filter != "全部"
        and subject_filter != "全部"
        and teacher_filter != "全部"
        and academic_year_filter != "全部"
        else ["全部"]
    )
    semester_filter = st.selectbox("學期", semester_options)

with col6:
    exam_options = (
        ["全部"]
        + list_exam_periods(
            field_filter,
            subject_filter,
            teacher_filter,
            academic_year_filter,
            semester_filter,
            taxonomy,
        )
        if field_filter != "全部"
        and subject_filter != "全部"
        and teacher_filter != "全部"
        and academic_year_filter != "全部"
        and semester_filter != "全部"
        else ["全部"]
    )
    exam_period_filter = st.selectbox("期中/期末", exam_options)

filters = (
    field_filter,
    subject_filter,
    teacher_filter,
    academic_year_filter,
    semester_filter,
    exam_period_filter,
)
all_filters_selected = all(value != "全部" for value in filters)

if not all_filters_selected:
    st.info("請完整選擇法領域、科目、老師、學年、學期、期中/期末後，才會顯示題目與作答")
    st.stop()

answers = load_answers()

year_value = build_year_value(
    academic_year_filter, semester_filter, exam_period_filter
)

st.markdown("---")
st.subheader("題目（公開）")
question = get_question(
    field_filter, subject_filter, teacher_filter, year_value
)
if question:
    if question.get("question_text"):
        st.markdown(question["question_text"])
    if question.get("question_link"):
        st.link_button("開啟題目連結", question["question_link"])
else:
    st.caption("此分類尚無題目")

st.markdown("---")
st.subheader("作答")

filtered = [
    ans
    for ans in answers
    if matches_filter(
        ans,
        field_filter,
        subject_filter,
        teacher_filter,
        academic_year_filter,
        semester_filter,
        exam_period_filter,
    )
]

st.write(f"目前分類共有 {len(filtered)} 筆作答")

if not filtered:
    st.info("此分類尚無作答")
    st.stop()

for i, ans in enumerate(filtered, 1):
    unlock_id = make_unlock_id(ans)
    st.markdown(f"**#{i} {format_label(ans)}**")

    if ans.get("uploader_id") == "legacy_anonymous":
        st.caption("歷史匿名資料（不開放）")
        st.markdown("---")
        continue

    if is_unlocked(ans, users[username]["unlocked"]):
        st.write(ans["answer_text"])
    else:
        st.write("作答內容已鎖定，需 1 代幣解鎖")
        if st.button("1 代幣解鎖", key=f"unlock_{ans['upload_time']}_{i}"):
            ok, _ = unlock_with_cost(username, unlock_id, cost=1)
            if not ok:
                st.error("代幣不足")
            else:
                st.rerun()
    st.markdown("---")
