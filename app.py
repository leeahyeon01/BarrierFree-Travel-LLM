"""
♿ 무장애 여행지 추천 AI — Streamlit 웹앱 (프론트엔드 전용)
백엔드: FastAPI (BACKEND_URL 환경변수 또는 st.secrets["BACKEND_URL"])
"""

import os
import re
import streamlit as st
import requests
from dotenv import load_dotenv

load_dotenv()

# ── 백엔드 URL ────────────────────────────────────────────────────────────────
def _backend_url() -> str:
    try:
        return st.secrets["BACKEND_URL"]
    except Exception:
        return os.getenv("BACKEND_URL", "http://localhost:8000")

BACKEND_URL = _backend_url()

# ── 지역/카테고리 목록 (백엔드와 동기화) ──────────────────────────────────────
AREAS = [
    "서울", "인천", "대전", "대구", "광주", "부산", "울산", "세종",
    "경기", "강원", "충북", "충남", "전북", "전남", "경북", "경남", "제주",
]
CATEGORIES = ["관광지", "문화시설", "축제", "숙박", "음식점"]

# ── 페이지 설정 ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="트래블리 — 무장애 여행 AI",
    page_icon="♿",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
[data-testid="stAppViewContainer"] { background: #F8F9FB; }
[data-testid="stSidebar"] { background: #1E293B; }
[data-testid="stSidebar"] * { color: #E2E8F0 !important; }
.header-box {
    background: linear-gradient(135deg, #2563EB 0%, #1E40AF 100%);
    border-radius: 16px; padding: 32px 36px; margin-bottom: 24px; color: white;
}
.header-box h1 { font-size: 2rem; font-weight: 800; margin: 0 0 6px; }
.header-box p  { font-size: 1rem; opacity: .85; margin: 0; }
.bubble-user {
    background: #2563EB; color: white;
    border-radius: 18px 18px 4px 18px;
    padding: 12px 18px; margin: 8px 0 8px auto;
    max-width: 72%; width: fit-content;
    font-size: .95rem; line-height: 1.6;
}
.bubble-bot {
    background: white; color: #1E293B;
    border-radius: 18px 18px 18px 4px;
    padding: 12px 18px; margin: 8px auto 8px 0;
    max-width: 82%; width: fit-content;
    font-size: .95rem; line-height: 1.6;
    border: 1px solid #E2E8F0;
    box-shadow: 0 2px 8px rgba(0,0,0,.06);
}
.bubble-bot pre {
    background: #F1F5F9; border-radius: 8px;
    padding: 10px 14px; font-size: .85rem;
    white-space: pre-wrap; word-break: break-word;
}
.tool-badge {
    display: inline-block; background: #F0FDF4;
    border: 1px solid #BBF7D0; color: #166534;
    border-radius: 20px; padding: 3px 12px;
    font-size: .78rem; margin: 4px 0;
}
.stButton > button {
    border-radius: 20px; border: 1.5px solid #2563EB;
    color: #2563EB; background: white;
    font-size: .85rem; padding: 4px 14px; transition: all .2s;
}
.stButton > button:hover { background: #2563EB; color: white; }
[data-testid="stChatInputTextArea"] textarea {
    border-radius: 12px !important;
    border: 1.5px solid #CBD5E1 !important;
    font-size: .95rem !important;
}
.sidebar-section {
    font-size: .75rem; font-weight: 700; letter-spacing: .08em;
    text-transform: uppercase; color: #94A3B8 !important; margin: 20px 0 8px;
}
</style>
""", unsafe_allow_html=True)


# ── 세션 상태 초기화 ──────────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []   # system 프롬프트 제외 — 백엔드가 주입

if "display_messages" not in st.session_state:
    st.session_state.display_messages = []


# ── 사이드바 ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ♿ 트래블리")
    st.markdown("무장애 여행 전문 AI 어시스턴트")
    st.divider()

    st.markdown('<p class="sidebar-section">지역 선택</p>', unsafe_allow_html=True)
    selected_area = st.selectbox("지역", AREAS, label_visibility="collapsed")

    st.markdown('<p class="sidebar-section">카테고리</p>', unsafe_allow_html=True)
    selected_category = st.selectbox("카테고리", CATEGORIES, label_visibility="collapsed")

    if st.button("🔍 장소 검색", use_container_width=True):
        st.session_state["quick_input"] = f"{selected_area} {selected_category} 추천해줘"

    st.divider()

    st.markdown('<p class="sidebar-section">빠른 질문</p>', unsafe_allow_html=True)
    for q in [
        "서울 관광지 추천해줘",
        "제주 무장애 숙박 찾아줘",
        "부산 음식점 알려줘",
        "강남역 엘리베이터 상태 알려줘",
        "서울 장애인 콜택시 번호 알려줘",
    ]:
        if st.button(q, use_container_width=True, key=f"quick_{q}"):
            st.session_state["quick_input"] = q

    st.divider()

    if st.button("🗑 대화 초기화", use_container_width=True):
        st.session_state.messages = []
        st.session_state.display_messages = []
        st.rerun()

    st.markdown('<p class="sidebar-section">연결 상태</p>', unsafe_allow_html=True)
    try:
        r = requests.get(f"{BACKEND_URL}/health", timeout=3)
        api_ok = r.status_code == 200
    except Exception:
        api_ok = False
    st.markdown(f"{'🟢' if api_ok else '🔴'} 백엔드 서버  `{BACKEND_URL}`")


# ── 메인 영역 ─────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-box">
  <h1>♿ 무장애 여행지 추천 AI</h1>
  <p>한국관광공사 공식 데이터 · 네이버 리뷰 기반 접근성 검증 · 실시간 교통 안내</p>
</div>
""", unsafe_allow_html=True)

if not st.session_state.display_messages:
    st.markdown(f"""
<div class="bubble-bot">
안녕하세요! 무장애 여행 전문 챗봇 <strong>트래블리</strong>입니다 ♿<br><br>
다음 서비스를 제공합니다.<br>
&nbsp;&nbsp;1️⃣ &nbsp;지역별 무장애 관광지·숙박·음식점·문화시설 추천<br>
&nbsp;&nbsp;2️⃣ &nbsp;목적지까지 장애인 맞춤 경로 안내<br>
&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;(저상버스 · 엘리베이터 · 리프트 · 장애인 콜택시)<br>
&nbsp;&nbsp;3️⃣ &nbsp;네이버 리뷰 기반 접근성 자동 검증<br><br>
<strong>지원 지역:</strong> {', '.join(AREAS)}<br><br>
어떤 도움이 필요하신가요?
</div>
""", unsafe_allow_html=True)


# ── 렌더 헬퍼 ────────────────────────────────────────────────────────────────
def _render_validation(data: dict):
    risk = data.get("overall_risk", "❓")
    risk_color = {"🔴": "#FEE2E2", "🟡": "#FEF9C3", "🟢": "#DCFCE7"}.get(risk[:2], "#F1F5F9")

    dc = data.get("data_collected", {})
    naver_flag = "🟢 수집됨" if dc.get("naver_available") else "🟡 미설정(지식 기반 추론)"

    st.markdown(f"""
<div style="background:{risk_color};border-radius:12px;padding:16px 20px;margin:8px 0;border:1px solid #E2E8F0;">
<strong>♿ 실시간 접근성 검증</strong> &nbsp;|&nbsp; 종합 위험도: <strong>{risk}</strong><br>
<small>📊 블로그 {dc.get('blog_posts',0)}건 · 지식iN {dc.get('kin_posts',0)}건 · 네이버 {naver_flag}</small>
</div>""", unsafe_allow_html=True)

    gpt = data.get("gpt_inference", {})
    metrics = gpt.get("metrics", {})

    METRIC_LABELS = {
        "table_height":        ("테이블 높이",    "≥70cm"),
        "aisle_width":         ("통로 폭",        "≥80cm"),
        "entrance_step":       ("입구 단차",       "0cm"),
        "elevator":            ("엘리베이터",      "—"),
        "accessible_parking":  ("장애인 주차",     "—"),
        "accessible_restroom": ("장애인 화장실",   "—"),
    }

    if metrics:
        rows = []
        for key, (label, std) in METRIC_LABELS.items():
            m = metrics.get(key, {})
            status = m.get("status", "❓")
            est_cm = m.get("estimated_cm") or m.get("table_height_cm_est")
            val = f"~{est_cm}cm" if est_cm else (
                "있음" if m.get("available") or m.get("operational") else
                "없음" if m.get("available") is False else "추론 중"
            )
            ev = (m.get("evidence") or ["—"])[0][:60]
            rows.append(f"| {status} {label} | {val} | {std} | {ev} |")
        st.markdown("| 항목 | 추정값 | 기준 | 근거 |\n|---|---|---|---|\n" + "\n".join(rows))

    warnings = data.get("warnings", [])
    if warnings:
        with st.expander(f"⚠ 접근 경고 신호 {len(warnings)}건", expanded=True):
            for w in warnings:
                sev_color = "#FEE2E2" if "🔴" in w["severity"] else "#FEF9C3"
                st.markdown(
                    f'<div style="background:{sev_color};border-radius:8px;padding:8px 12px;margin:4px 0;">'
                    f'<strong>{w["severity"]}</strong> · {w["category"]}<br>'
                    f'<small>키워드: <code>{w["keyword"]}</code> · {w.get("excerpt","")[:100]}</small></div>',
                    unsafe_allow_html=True,
                )
    else:
        st.success("✅ 접근 경고 신호 없음")

    positives = data.get("positive_signals", [])
    if positives:
        st.markdown("**✅ 접근 긍정 신호:** " + " · ".join(positives))

    sources = data.get("top_sources", [])
    if sources:
        with st.expander("🔗 참고 리뷰 출처"):
            for s in sources:
                title = s.get("title", "제목 없음")
                link  = s.get("link", "")
                date  = s.get("date", "")
                st.markdown(f"- [{title}]({link}) {date}" if link else f"- {title} {date}")

    vision = data.get("vision_analysis", {})
    if vision and not vision.get("error"):
        with st.expander("👁 Vision 사진 분석"):
            ent  = vision.get("entrance", {})
            intr = vision.get("interior", {})
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**입구** — 단차: {'있음 🔴' if ent.get('step_detected') else '없음 🟢'}  \n"
                            f"경사로: {'있음 🟢' if ent.get('ramp_detected') else '없음'}  \n"
                            f"문 유형: {ent.get('door_type','미확인')}")
            with col2:
                st.markdown(f"**내부** — 테이블: {intr.get('table_type','미확인')}  \n"
                            f"높이 추정: {intr.get('table_height_cm_est') or '미확인'}cm  \n"
                            f"통로폭 추정: {intr.get('aisle_width_cm_est') or '미확인'}cm")
            obs = vision.get("obstacles", [])
            if obs:
                st.warning("장애물: " + ", ".join(obs))


def _render_bot_content(content: str):
    content = re.sub(
        r'!\[([^\]]*)\]\((https?://[^\s\)]+)\)',
        r'<img src="\2" alt="\1" style="max-width:100%;border-radius:8px;margin:6px 0;display:block;">',
        content,
    )
    content = re.sub(
        r'\[([^\]]+)\]\((https?://[^\s\)]+)\)',
        r'<a href="\2" target="_blank" style="color:#2563EB;">\1</a>',
        content,
    )
    content = content.replace("\n", "<br>")
    st.markdown(f'<div class="bubble-bot">{content}</div>', unsafe_allow_html=True)


def _render_images(urls: list, name: str):
    if not urls:
        return
    imgs_html = "".join(
        f'<img src="{url}" style="width:100%;border-radius:8px;object-fit:cover;max-height:200px;" '
        f'onerror="this.style.display=\'none\'">'
        for url in urls[:3]
    )
    cols_style = f"grid-template-columns:repeat({min(len(urls),3)},1fr)"
    st.markdown(
        f'<div style="margin:8px 0 4px;font-size:.82rem;color:#64748B;">📸 <strong>{name}</strong> 시설 사진</div>'
        f'<div style="display:grid;{cols_style};gap:8px;margin-bottom:8px;">{imgs_html}</div>',
        unsafe_allow_html=True,
    )


# 대화 기록 렌더링
for dm in st.session_state.display_messages:
    role = dm["role"]
    if role == "user":
        st.markdown(f'<div class="bubble-user">{dm["content"]}</div>', unsafe_allow_html=True)
    elif role == "tool":
        st.markdown(f'<div class="tool-badge">⚙ {dm.get("label","도구 실행")} 완료</div>', unsafe_allow_html=True)
    elif role == "images":
        _render_images(dm.get("urls", []), dm.get("name", ""))
    elif role == "validation":
        _render_validation(dm["data"])
    else:
        _render_bot_content(dm["content"])


# ── AI 응답 처리 ──────────────────────────────────────────────────────────────
def run_ai(user_text: str):
    st.session_state.display_messages.append({"role": "user", "content": user_text})

    with st.spinner("트래블리가 답변을 준비하고 있습니다..."):
        try:
            resp = requests.post(
                f"{BACKEND_URL}/api/chat",
                json={"messages": st.session_state.messages, "user_message": user_text},
                timeout=120,
            )
            resp.raise_for_status()
            data = resp.json()
        except requests.exceptions.ConnectionError:
            st.error(f"백엔드 서버에 연결할 수 없습니다. ({BACKEND_URL})")
            st.session_state.display_messages.pop()
            return
        except Exception as e:
            st.error(f"오류: {e}")
            st.session_state.display_messages.pop()
            return

    # 업데이트된 메시지 히스토리 저장 (system 제외, 백엔드가 반환)
    st.session_state.messages = data["messages"]

    # 도구 이벤트 → display_messages
    for evt in data.get("tool_events", []):
        st.session_state.display_messages.append({
            "role":  "tool",
            "label": evt["label"],
        })
        evt_data = evt.get("data", {})

        if evt["name"] == "get_detail":
            imgs = evt_data.get("images", [])
            if imgs:
                st.session_state.display_messages.append({
                    "role": "images",
                    "name": evt_data.get("이름", ""),
                    "urls": imgs,
                })

        elif evt["name"] == "validate_accessibility" and "error" not in evt_data:
            st.session_state.display_messages.append({
                "role": "validation",
                "data": evt_data,
            })

    # 최종 텍스트 응답
    reply = data.get("reply", "")
    if reply:
        st.session_state.display_messages.append({"role": "bot", "content": reply})

    st.rerun()


# ── 채팅 입력 ─────────────────────────────────────────────────────────────────
if "quick_input" in st.session_state:
    prompt = st.session_state.pop("quick_input")
    run_ai(prompt)

if prompt := st.chat_input("여행지나 경로에 대해 물어보세요... (예: 서울 관광지 추천해줘)"):
    run_ai(prompt)
