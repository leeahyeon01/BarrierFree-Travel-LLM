from __future__ import annotations
import os
import sys
import json
import requests
import streamlit as st

st.set_page_config(page_title="배리어프리 MultiAgent", page_icon="♿", layout="wide")

API_URL = os.getenv("API_URL", "http://localhost:8000")


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────

def _call_api(user_input: str) -> dict:
    try:
        resp = requests.post(f"{API_URL}/chat", json={"message": user_input}, timeout=180)
        resp.raise_for_status()
        return resp.json()
    except requests.exceptions.ConnectionError:
        st.warning("⚠️ API 서버에 연결할 수 없어 로컬 모듈을 직접 호출합니다.")
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from backend.orchestrator import OrchestratorAgent
        result = OrchestratorAgent().run(user_input)
        return {
            "reply": result.reply,
            "complete": result.complete,
            "itinerary": result.itinerary,
            "validation_result": result.validation_result,
        }


def _fetch_itineraries() -> list:
    try:
        resp = requests.get(f"{API_URL}/itineraries", timeout=5)
        return resp.json().get("itineraries", []) if resp.status_code == 200 else []
    except Exception:
        return []


def _render_itinerary_cards(itinerary: dict) -> None:
    """일정을 카드 형식으로 렌더링합니다."""
    if not itinerary:
        return

    dest = itinerary.get("destination", "")
    dur = itinerary.get("duration_days", "?")
    needs = ", ".join(itinerary.get("accessibility_needs", []))

    st.markdown(f"### 🗺️ {dest} {dur}일 무장애 여행")
    if needs:
        st.markdown(f"*접근성 조건: {needs}*")

    days = itinerary.get("days", [])
    for day in days:
        day_num = day.get("day", "?")
        total_h = day.get("total_hours", 0)
        with st.expander(f"📅 {day_num}일차  ·  총 {total_h}시간", expanded=True):
            sessions = day.get("sessions", [])
            cols = st.columns(max(len(sessions), 1))
            for i, session in enumerate(sessions):
                with cols[i % len(cols)]:
                    status = session.get("validation_status", "✅")
                    place = session.get("place", "")
                    sess_label = session.get("session", "")
                    hours = session.get("duration_hours", 0)
                    notes = session.get("accessibility_notes", "")

                    color = "#2ecc40" if "✅" in status else "#ff4136"
                    st.markdown(
                        f"""<div style="border:1px solid {color}; border-radius:8px; padding:12px; margin:4px">
                        <b>{status} {sess_label}</b><br>
                        <span style="font-size:1.1em">{place}</span><br>
                        <small>⏱ {hours}시간</small><br>
                        <small style="color:#555">{notes}</small>
                        </div>""",
                        unsafe_allow_html=True,
                    )


# ── 사이드바: 저장된 일정 ──────────────────────────────────────────────────────

with st.sidebar:
    st.header("📋 저장된 일정")
    if st.button("새로고침"):
        st.cache_data.clear()

    items = _fetch_itineraries()
    if not items:
        st.caption("저장된 일정이 없습니다.")
    for item in items:
        dest = item.get("destination", "?")
        dur = item.get("duration_days", "?")
        iid = item.get("id", "")
        created = (item.get("created_at") or "")[:10]

        with st.container():
            st.markdown(f"**{dest}** ({dur}일)  \n<small>{created}</small>", unsafe_allow_html=True)
            col1, col2 = st.columns(2)
            with col1:
                try:
                    dl = requests.get(f"{API_URL}/itineraries/{iid}/download", timeout=5)
                    if dl.status_code == 200:
                        st.download_button(
                            "⬇ 다운로드",
                            data=dl.content,
                            file_name=f"itinerary_{iid[:8]}.json",
                            mime="application/json",
                            key=f"dl_{iid}",
                        )
                except Exception:
                    pass
            with col2:
                if st.button("🗑", key=f"del_{iid}", help="삭제"):
                    try:
                        requests.delete(f"{API_URL}/itineraries/{iid}", timeout=5)
                        st.rerun()
                    except Exception:
                        pass
            st.divider()


# ── 메인: 채팅 ────────────────────────────────────────────────────────────────

st.title("♿ 무장애 여행 기획 — MultiAgent")

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "안녕하세요! 여행 목적지와 접근성 조건(예: 휠체어, 단차 없는 곳)을 말씀해주세요."}
    ]
if "last_data" not in st.session_state:
    st.session_state.last_data = None

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

user_input = st.chat_input("예: 제주도 2박 3일 휠체어 여행 계획해줘")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("에이전트들이 협력하여 최적의 코스를 탐색·검증 중입니다..."):
            data = _call_api(user_input)
            st.session_state.last_data = data

        reply = data.get("reply", "")
        itinerary = data.get("itinerary")
        validation_result = data.get("validation_result") or {}

        # 🔴 접근성 경고 배너
        flagged = validation_result.get("flagged_places", [])
        if flagged:
            st.error(f"🔴 접근성 경고: {len(flagged)}개 장소가 접근성 미달로 제외되었습니다.")
            with st.expander("제외된 장소 상세"):
                for f in flagged:
                    issues = ", ".join(f.get("issues", ["접근성 미달"]))
                    st.markdown(f"- **{f.get('place_name', '?')}**: {issues}")

        # 텍스트 답변
        st.markdown(reply)

        # 일정 카드뷰
        if itinerary:
            _render_itinerary_cards(itinerary)

            # JSON 뷰 토글
            with st.expander("📄 JSON 보기"):
                st.json(itinerary)

            # 인라인 다운로드 버튼
            st.download_button(
                "⬇ 이 일정 다운로드 (JSON)",
                data=json.dumps(itinerary, ensure_ascii=False, indent=2),
                file_name=f"itinerary_{itinerary.get('destination', '여행')}_{(itinerary.get('id') or '')[:8]}.json",
                mime="application/json",
            )

        st.session_state.messages.append({"role": "assistant", "content": reply})
