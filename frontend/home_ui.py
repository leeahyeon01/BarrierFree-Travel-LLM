import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import tour_api
import naver_validator

st.set_page_config(page_title="트래블리 - 무장애 여행", page_icon="♿", layout="centered")

# ── 지역 데이터 ───────────────────────────────────────────────────────────────
# 시 → 구 목록 (구 선택은 표시용, API는 시 단위 호출)
REGIONS = {
    "서울":  ["강남/역삼/삼성", "신사/청담/압구정", "서초/교대/사당", "잠실/송파/강동",
              "을지로/명동/중구/동대문", "서울역/이태원/용산", "종로/인사동",
              "홍대/합정/마포/서대문", "여의도", "영등포역", "구로/신도림/금천",
              "김포공항/염창/강서", "건대입구/성수/왕십리", "성북/강북/노원/도봉"],
    "부산":  ["해운대/센텀", "광안리/수영", "서면/부산진", "남포동/중구", "기장/정관", "사하/하단", "동래/온천장"],
    "제주":  ["제주시내", "서귀포/중문", "함덕/조천", "성산/우도", "한림/협재", "모슬포/대정"],
    "경기":  ["수원", "성남/분당", "고양/일산", "용인", "안양/과천", "평택/안성", "광주/하남"],
    "인천":  ["인천공항", "송도/연수", "부평/계산", "강화도"],
    "강원":  ["강릉/속초", "춘천", "평창/횡성", "동해/삼척", "양양/고성"],
    "경상":  ["경주", "안동", "통영/거제", "진주", "대구 도심", "포항"],
    "전라":  ["전주", "여수", "순천", "광주 도심", "남원"],
    "충청":  ["대전 도심", "천안/아산", "청주", "공주/부여", "태안/서산"],
}

CATEGORIES = [
    ("🏛️", "관광지"), ("🎭", "문화시설"), ("🎉", "축제"), ("🛏️", "숙박"), ("🍽️", "음식점"),
]

PAGE_SIZE = 6  # 한 페이지에 보여줄 장소 수

# ── 세션 상태 초기화 ─────────────────────────────────────────────────────────
defaults = {
    "view":             "home",   # "home" | "list" | "detail"
    "modal_open":       False,
    "active_si":        "서울",
    "selected_si":      None,
    "selected_gu":      None,
    "selected_category":None,
    "place_list":       [],
    "page":             0,
    "selected_place":   None,
    "place_detail":     None,
    "accessibility":    None,
    "recents":          [],
    "random_category":  None,
    "random_places":    [],
    "banner_festivals": [],
    "banner_idx":       0,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── 전역 CSS ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.block-container { max-width: 560px !important; padding: 1.2rem 1rem 3rem !important; }
header { visibility: hidden; }

/* 기본 버튼 */
div.stButton > button {
    border-radius: 10px; border: 1px solid #e0e0e0;
    background: white; color: #333; font-size: 13px;
    padding: 0.45rem 0.8rem; transition: all 0.15s;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
}
div.stButton > button:hover { border-color: #4A90E2; color: #4A90E2; }

/* 카테고리 버튼 */
.cat-btn > button {
    border-radius: 50px !important; border: 2px solid #eee !important;
    background: #f7f7f7 !important; font-size: 22px !important;
    width: 56px !important; height: 56px !important; padding: 0 !important;
}
.cat-btn.active > button {
    border-color: #4A90E2 !important; background: #EBF4FF !important;
}

/* 지역 사이드바 */
.region-sidebar-btn > button {
    border-radius: 0 !important; border: none !important;
    border-right: 3px solid transparent !important; box-shadow: none !important;
    background: #f8f8f8 !important; color: #999 !important;
    width: 100%; text-align: center; padding: 0.65rem 0 !important; font-size: 13px !important;
}
.region-sidebar-btn.active > button {
    background: white !important; color: #111 !important;
    font-weight: 700 !important; border-right: 3px solid #4A90E2 !important;
}

/* 장소 카드 */
.place-card {
    border-radius: 14px; overflow: hidden; background: white;
    box-shadow: 0 2px 10px rgba(0,0,0,0.09); cursor: pointer;
    transition: transform 0.15s, box-shadow 0.15s;
}
.place-card:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.13); }
.place-card img { width: 100%; aspect-ratio: 4/3; object-fit: cover; display: block; }
.place-card-body { padding: 8px 10px 10px; }
.place-card-name { font-size: 13px; font-weight: 700; color: #111; margin: 0 0 3px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.place-card-addr { font-size: 11px; color: #888; margin: 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

/* 접근성 카드 */
.access-card { border-radius: 14px; padding: 16px 18px; background: #f9fafb;
    border: 1px solid #e8ecf0; margin-bottom: 12px; }
.access-badge-green { background: #d1fae5; color: #065f46; padding: 3px 10px;
    border-radius: 999px; font-size: 12px; font-weight: 700; display: inline-block; }
.access-badge-yellow { background: #fef9c3; color: #854d0e; padding: 3px 10px;
    border-radius: 999px; font-size: 12px; font-weight: 700; display: inline-block; }
.access-badge-red { background: #fee2e2; color: #991b1b; padding: 3px 10px;
    border-radius: 999px; font-size: 12px; font-weight: 700; display: inline-block; }
.metric-row { display: flex; justify-content: space-between; align-items: center;
    padding: 6px 0; border-bottom: 1px solid #eef0f3; font-size: 13px; }
.metric-row:last-child { border-bottom: none; }

/* 빵 부스러기 */
.breadcrumb { font-size: 12px; color: #888; margin-bottom: 14px; }
.breadcrumb span { color: #4A90E2; font-weight: 600; }

/* 구분선 */
.divider { height: 8px; background: #f2f2f2; margin: 12px -1rem; border: none; }

/* 칩 */
.chip-wrap > button {
    border-radius: 999px !important; background: #f0f0f0 !important;
    font-size: 12px !important; padding: 2px 10px !important;
    border: none !important; color: #555 !important; box-shadow: none !important;
}
</style>
""", unsafe_allow_html=True)


# ── 캐시 데이터 로딩 ──────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def cached_search(si: str, category: str) -> list[dict]:
    return tour_api.search_places(si, category, num_of_rows=20)

@st.cache_data(ttl=600, show_spinner=False)
def cached_detail(content_id: str) -> dict:
    return tour_api.get_detail(content_id)

@st.cache_data(ttl=1800, show_spinner=False)
def cached_accessibility(name: str, address: str) -> dict:
    return naver_validator.validate_accessibility(name, address)


# ── 접근성 요약 문장 생성 ─────────────────────────────────────────────────────
def accessibility_summary(result: dict, name: str) -> str:
    risk = result.get("overall_risk", "")
    metrics = result.get("gpt_inference", {}).get("metrics", {})
    warnings = result.get("warnings", [])
    positives = result.get("positive_signals", [])

    entrance = metrics.get("entrance_step", {})
    elevator = metrics.get("elevator", {})
    restroom = metrics.get("accessible_restroom", {})

    parts = []

    if entrance.get("has_step") is False:
        parts.append("입구에 단차가 없어 접근성이 양호합니다")
    elif entrance.get("has_step") is True:
        h = entrance.get("estimated_height_cm")
        ramp = entrance.get("has_ramp_alternative")
        if ramp:
            parts.append("입구에 단차가 있으나 경사로가 마련되어 있습니다")
        else:
            parts.append(f"입구에 단차({'약 ' + str(h) + 'cm ' if h else ''}있음)가 확인됩니다")

    if elevator.get("available") is True:
        parts.append("엘리베이터 이용 가능")
    elif elevator.get("available") is False:
        parts.append("엘리베이터 없음")

    if restroom.get("available") is True:
        parts.append("장애인 화장실 완비")

    if warnings:
        parts.append(f"주의사항 {len(warnings)}건 발견")
    elif positives:
        parts.append("긍정적 접근성 신호 다수 확인")

    if parts:
        summary = name + "은 " + ", ".join(parts[:2]) + "합니다."
    elif "🟢" in risk:
        summary = f"{name}은 접근성이 전반적으로 양호한 것으로 보입니다."
    elif "🔴" in risk:
        summary = f"{name}은 일부 접근성 개선이 필요한 것으로 보입니다."
    else:
        summary = f"{name}의 접근성 정보를 분석했습니다."

    return summary


# ── 지역 선택 모달 ────────────────────────────────────────────────────────────
@st.dialog("지역 선택", width="large")
def region_modal():
    left, right = st.columns([1, 2.5])

    with left:
        st.markdown('<div style="background:#f8f8f8;border-right:1px solid #eee;padding:4px 0;min-height:400px">', unsafe_allow_html=True)
        for si in REGIONS:
            is_active = st.session_state.active_si == si
            css = "region-sidebar-btn active" if is_active else "region-sidebar-btn"
            st.markdown(f'<div class="{css}">', unsafe_allow_html=True)
            if st.button(si, key=f"modal_si_{si}"):
                st.session_state.active_si = si
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

    with right:
        si = st.session_state.active_si
        col_t, col_all = st.columns([3, 1])
        with col_t:
            st.markdown(f"**{si}**")
        with col_all:
            if st.button("전체 ›", key="modal_all"):
                st.session_state.selected_si = si
                st.session_state.selected_gu = f"{si} 전체"
                if si not in st.session_state.recents:
                    st.session_state.recents.insert(0, si)
                st.session_state.selected_category = None
                st.session_state.view = "home"
                st.rerun()
        st.markdown('<div style="border-top:1px solid #eee;margin:4px 0 8px"></div>', unsafe_allow_html=True)
        for gu in REGIONS[si]:
            if st.button(gu, key=f"modal_gu_{gu}", use_container_width=True):
                st.session_state.selected_si = si
                st.session_state.selected_gu = gu
                label = f"{si} {gu}"
                if label not in st.session_state.recents:
                    st.session_state.recents.insert(0, label)
                    st.session_state.recents = st.session_state.recents[:4]
                st.session_state.selected_category = None
                st.session_state.view = "home"
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  뷰: 상세 페이지
# ══════════════════════════════════════════════════════════════════════════════
def render_detail():
    place = st.session_state.selected_place
    detail = st.session_state.place_detail
    si = st.session_state.selected_si or ""
    gu = st.session_state.selected_gu or ""
    cat = st.session_state.selected_category or ""

    # 뒤로가기
    if st.button("← 목록으로"):
        st.session_state.view = "list"
        st.rerun()

    # 빵 부스러기
    st.markdown(
        f'<div class="breadcrumb">{si} › <span>{gu}</span> › {cat} › <span>{place.get("이름","")}</span></div>',
        unsafe_allow_html=True,
    )

    name = detail.get("이름") or place.get("이름", "")
    addr = detail.get("주소") or place.get("주소", "")
    images = detail.get("images", [])
    overview = detail.get("개요", "")
    tel = detail.get("전화번호", "")

    # 대표 이미지
    if images:
        st.image(images[0], use_container_width=True)
        if len(images) > 1:
            st.image(images[1], use_container_width=True)

    # 기본 정보
    st.markdown(f"### {name}")
    if addr:
        st.markdown(f"📍 {addr}")
    if tel and tel != "정보 없음":
        st.markdown(f"📞 {tel}")

    # 개요
    if overview and overview != "정보 없음":
        with st.expander("장소 소개", expanded=True):
            st.write(overview)

    st.markdown('<hr class="divider"/>', unsafe_allow_html=True)

    # 실시간 접근성 검증
    st.markdown("#### ♿ 실시간 접근성 검증")
    st.caption("네이버 블로그·지식iN 리뷰 기반 자동 분석")

    if st.session_state.accessibility is None:
        with st.spinner("네이버 리뷰 분석 중..."):
            st.session_state.accessibility = cached_accessibility(name, addr)
        st.rerun()

    acc = st.session_state.accessibility
    risk = acc.get("overall_risk", "❓")
    summary = accessibility_summary(acc, name)
    metrics = acc.get("gpt_inference", {}).get("metrics", {})
    data_info = acc.get("data_collected", {})

    # 배지 색상
    if "🟢" in risk:
        badge_css = "access-badge-green"
    elif "🔴" in risk:
        badge_css = "access-badge-red"
    else:
        badge_css = "access-badge-yellow"

    st.markdown(f"""
    <div class="access-card">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
            <span class="{badge_css}">{risk}</span>
            <span style="font-size:11px;color:#aaa">블로그 {data_info.get('blog_posts',0)}건 · 지식iN {data_info.get('kin_posts',0)}건 분석</span>
        </div>
        <p style="font-size:14px;color:#333;margin:0 0 14px;line-height:1.6">💬 {summary}</p>
    """, unsafe_allow_html=True)

    # 항목별 수치
    METRIC_LABELS = {
        "entrance_step":      ("🚪", "입구 단차"),
        "elevator":           ("🛗", "엘리베이터"),
        "accessible_restroom":("🚻", "장애인 화장실"),
        "accessible_parking": ("🅿️", "장애인 주차"),
        "aisle_width":        ("↔️", "통로 폭"),
    }
    rows_html = ""
    for key, (icon, label) in METRIC_LABELS.items():
        m = metrics.get(key, {})
        status = m.get("status", "❓")
        val_parts = []
        if key == "entrance_step":
            val_parts.append("단차 없음" if m.get("has_step") is False else ("단차 있음" if m.get("has_step") else "미확인"))
            if m.get("has_ramp_alternative"):
                val_parts.append("경사로 있음")
        elif key == "elevator":
            val_parts.append("있음" if m.get("available") else ("없음" if m.get("available") is False else "미확인"))
        elif key in ("accessible_restroom", "accessible_parking"):
            val_parts.append("있음" if m.get("available") else ("없음" if m.get("available") is False else "미확인"))
        elif key == "aisle_width":
            cm = m.get("estimated_cm")
            val_parts.append(f"약 {cm}cm" if cm else "미확인")
        val_text = ", ".join(val_parts) if val_parts else "분석 중"
        rows_html += f"""
        <div class="metric-row">
            <span>{icon} {label}</span>
            <span style="color:#555">{val_text} <span style="font-size:15px">{status}</span></span>
        </div>"""

    st.markdown(rows_html + "</div>", unsafe_allow_html=True)

    # 경고
    warnings = acc.get("warnings", [])
    if warnings:
        with st.expander(f"⚠️ 주의사항 {len(warnings)}건"):
            for w in warnings[:3]:
                sev = w.get("severity", "")
                cat_w = w.get("category", "")
                quotes = w.get("quotes", [])
                quote_text = f' — "{quotes[0]}"' if quotes else ""
                st.markdown(f"- {sev} **{cat_w}**{quote_text}")

    st.markdown('<hr class="divider"/>', unsafe_allow_html=True)

    # CTA: 가는 법
    st.markdown("#### 🗺 이 장소에 가고 싶으신가요?")
    st.info(f"**{name}**까지 가는 법을 알려드릴까요?\n\n출발지를 챗봇에 입력하시면 저상버스·엘리베이터·장애인 콜택시 정보를 안내해드립니다.")
    kakao_url = f"https://map.kakao.com/?q={name}"
    st.markdown(f'<a href="{kakao_url}" target="_blank"><button style="background:#FEE500;border:none;border-radius:10px;padding:8px 20px;font-weight:700;font-size:13px;cursor:pointer">🗺 카카오맵에서 길찾기</button></a>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  뷰: 목록 페이지
# ══════════════════════════════════════════════════════════════════════════════
def render_list():
    si = st.session_state.selected_si or ""
    gu = st.session_state.selected_gu or ""
    cat = st.session_state.selected_category or ""

    # 뒤로가기
    if st.button("← 지역 선택"):
        st.session_state.view = "home"
        st.session_state.selected_category = None
        st.rerun()

    # 빵 부스러기
    st.markdown(
        f'<div class="breadcrumb">{si} › <span>{gu}</span> › <span>{cat}</span></div>',
        unsafe_allow_html=True,
    )

    places = st.session_state.place_list
    total = len(places)
    page = st.session_state.page
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page_places = places[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    if not page_places:
        st.warning(f"{si} {gu} 지역에서 무장애 {cat} 정보를 찾지 못했습니다.")
        return

    st.markdown(f'<p style="font-size:13px;color:#888;margin-bottom:12px">총 {total}개 · {page+1}/{total_pages} 페이지</p>', unsafe_allow_html=True)

    # 3열 카드 그리드
    rows = [page_places[i:i+3] for i in range(0, len(page_places), 3)]
    for row in rows:
        cols = st.columns(3)
        for j, place in enumerate(row):
            with cols[j]:
                img = place.get("image", "")
                name = place.get("이름", "")
                addr = place.get("주소", "")
                addr_short = addr[:14] + "…" if len(addr) > 14 else addr

                # 카드 클릭 버튼 (이미지 위 투명 오버레이 방식 대신 버튼 하나)
                if img:
                    st.markdown(f"""
                    <div class="place-card">
                        <img src="{img}" alt="{name}"/>
                        <div class="place-card-body">
                            <p class="place-card-name">{name}</p>
                            <p class="place-card-addr">📍 {addr_short}</p>
                        </div>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="place-card" style="padding:28px 10px;text-align:center;min-height:90px">
                        <p class="place-card-name">{name}</p>
                        <p class="place-card-addr">📍 {addr_short}</p>
                    </div>""", unsafe_allow_html=True)

                if st.button("자세히 보기", key=f"detail_{place.get('content_id','')}_{j}_{page}", use_container_width=True):
                    with st.spinner(f"{name} 정보 불러오는 중..."):
                        detail = cached_detail(place["content_id"])
                    st.session_state.selected_place = place
                    st.session_state.place_detail = detail
                    st.session_state.accessibility = None
                    st.session_state.view = "detail"
                    st.rerun()

    # 페이지네이션
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    p_cols = st.columns([1, 3, 1])
    with p_cols[0]:
        if page > 0:
            if st.button("◀ 이전", use_container_width=True):
                st.session_state.page -= 1
                st.rerun()
    with p_cols[1]:
        dots = " · ".join(
            f"**{i+1}**" if i == page else str(i+1)
            for i in range(total_pages)
        )
        st.markdown(f'<p style="text-align:center;font-size:13px;padding-top:6px">{dots}</p>', unsafe_allow_html=True)
    with p_cols[2]:
        if page < total_pages - 1:
            if st.button("다음 ▶", use_container_width=True):
                st.session_state.page += 1
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  뷰: 홈 페이지
# ══════════════════════════════════════════════════════════════════════════════
def render_home():
    # ── 헤더 ────────────────────────────────────────────────────────────────
    st.markdown('<h2 style="text-align:center;font-size:20px;font-weight:800;margin-bottom:18px">♿ 무장애 여행지 추천</h2>', unsafe_allow_html=True)

    # ── 지역 선택 버튼 ───────────────────────────────────────────────────────
    s_col, n_col = st.columns([5, 1])
    si = st.session_state.selected_si
    gu = st.session_state.selected_gu
    area_label = f"{si} {gu}" if si and gu else "지역선택"

    with s_col:
        if st.button(f"📍  {area_label}  ›", key="open_modal", use_container_width=True):
            region_modal()
    with n_col:
        st.button("✈️\n내주변", key="nearby", use_container_width=True)

    # ── 최근 선택 지역 ────────────────────────────────────────────────────────
    if st.session_state.recents:
        st.markdown('<p style="font-size:12px;color:#aaa;margin:10px 0 6px">최근 선택 지역</p>', unsafe_allow_html=True)
        chip_cols = st.columns(len(st.session_state.recents))
        for i, r in enumerate(st.session_state.recents):
            with chip_cols[i]:
                st.markdown('<div class="chip-wrap">', unsafe_allow_html=True)
                if st.button(f"{r} ×", key=f"chip_{i}"):
                    st.session_state.recents.pop(i)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    # ── 지역 선택 후 카테고리 표시 ────────────────────────────────────────────
    if st.session_state.selected_si:
        st.markdown('<hr class="divider"/>', unsafe_allow_html=True)
        si = st.session_state.selected_si
        gu = st.session_state.selected_gu
        st.markdown(
            f'<p style="font-size:14px;font-weight:700;margin:6px 0 12px">📌 {si} {gu} — 카테고리를 선택하세요</p>',
            unsafe_allow_html=True,
        )
        cat_cols = st.columns(5)
        for i, (emoji, label) in enumerate(CATEGORIES):
            with cat_cols[i]:
                is_active = st.session_state.selected_category == label
                css = "cat-btn active" if is_active else "cat-btn"
                st.markdown(f'<div class="{css}">', unsafe_allow_html=True)
                if st.button(emoji, key=f"cat_{label}"):
                    with st.spinner(f"{label} 정보 불러오는 중..."):
                        results = cached_search(si, label)
                    st.session_state.selected_category = label
                    st.session_state.place_list = results
                    st.session_state.page = 0
                    st.session_state.view = "list"
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
                color = "#4A90E2" if is_active else "#555"
                weight = "700" if is_active else "400"
                st.markdown(
                    f'<p style="text-align:center;font-size:11px;margin:-2px 0 10px;color:{color};font-weight:{weight}">{label}</p>',
                    unsafe_allow_html=True,
                )
    else:
        # ── 지역 미선택 시: 전국 랜덤 카테고리 탐색 ──────────────────────────
        st.markdown('<hr class="divider"/>', unsafe_allow_html=True)
        st.markdown('<p style="font-size:14px;font-weight:700;margin:6px 0 12px">🔍 카테고리로 둘러보기</p>', unsafe_allow_html=True)

        rnd_cols = st.columns(5)
        for i, (emoji, label) in enumerate(CATEGORIES):
            with rnd_cols[i]:
                is_active = st.session_state.get("random_category") == label
                css = "cat-btn active" if is_active else "cat-btn"
                st.markdown(f'<div class="{css}">', unsafe_allow_html=True)
                if st.button(emoji, key=f"rnd_cat_{label}"):
                    with st.spinner(f"전국 {label} 불러오는 중..."):
                        st.session_state.random_category = label
                        st.session_state.random_places = tour_api.search_random_places(label, count=6)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
                color = "#4A90E2" if is_active else "#555"
                weight = "700" if is_active else "400"
                st.markdown(
                    f'<p style="text-align:center;font-size:11px;margin:-2px 0 10px;color:{color};font-weight:{weight}">{label}</p>',
                    unsafe_allow_html=True,
                )

        # 랜덤 결과 카드
        rnd_places = st.session_state.get("random_places", [])
        if rnd_places:
            rnd_cat = st.session_state.get("random_category", "")
            st.markdown(f'<p style="font-size:13px;color:#888;margin:4px 0 10px">♿ 전국 무장애 {rnd_cat} 추천</p>', unsafe_allow_html=True)
            rows = [rnd_places[i:i+3] for i in range(0, len(rnd_places), 3)]
            for row in rows:
                cols = st.columns(3)
                for j, place in enumerate(row):
                    with cols[j]:
                        img = place.get("image", "")
                        name = place.get("이름", "")
                        addr = place.get("주소", "")
                        addr_short = addr[:14] + "…" if len(addr) > 14 else addr
                        if img:
                            st.markdown(f"""
                            <div class="place-card">
                                <img src="{img}" alt="{name}"/>
                                <div class="place-card-body">
                                    <p class="place-card-name">{name}</p>
                                    <p class="place-card-addr">📍 {addr_short}</p>
                                </div>
                            </div>""", unsafe_allow_html=True)
                        else:
                            st.markdown(f"""
                            <div class="place-card" style="padding:28px 10px;text-align:center;min-height:90px">
                                <p class="place-card-name">{name}</p>
                                <p class="place-card-addr">📍 {addr_short}</p>
                            </div>""", unsafe_allow_html=True)
                        if st.button("자세히 보기", key=f"rnd_detail_{place.get('content_id','')}_{j}", use_container_width=True):
                            with st.spinner(f"{name} 정보 불러오는 중..."):
                                detail = cached_detail(place["content_id"])
                            st.session_state.selected_place = place
                            st.session_state.place_detail = detail
                            st.session_state.accessibility = None
                            st.session_state.view = "detail"
                            st.rerun()

    # ── 배너 (무장애 축제) ────────────────────────────────────────────────────
    st.markdown('<hr class="divider"/>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:14px;font-weight:700;margin:6px 0 10px">🎉 무장애 축제</p>', unsafe_allow_html=True)

    if not st.session_state.banner_festivals:
        with st.spinner("축제 정보 불러오는 중..."):
            import random
            areas = list(tour_api.AREA_MAP.keys())
            random.shuffle(areas)
            festivals = []
            for area in areas:
                if len(festivals) >= 3:
                    break
                res = tour_api.search_places(area, "축제", num_of_rows=20)
                festivals.extend([f for f in res if f.get("image")])
            random.shuffle(festivals)
            st.session_state.banner_festivals = festivals[:3]

    banners = st.session_state.banner_festivals
    idx = st.session_state.banner_idx

    if banners:
        visible = banners[idx : idx + 2]
        b_cols = st.columns(len(visible))
        for j, b in enumerate(visible):
            with b_cols[j]:
                img = b.get("image", "")
                name = b.get("이름", "무장애 축제")
                addr = b.get("주소", "")
                if img:
                    st.markdown(f"""
                    <div style="border-radius:16px;overflow:hidden;position:relative;aspect-ratio:3/2;background:#222">
                        <img src="{img}" style="width:100%;height:100%;object-fit:cover;opacity:0.78"/>
                        <div style="position:absolute;top:8px;left:8px;background:rgba(0,0,0,0.35);
                             color:white;font-size:10px;font-weight:700;padding:2px 8px;border-radius:4px">🎉 무장애 축제</div>
                        <div style="position:absolute;bottom:0;left:0;right:0;
                             background:linear-gradient(transparent,rgba(0,0,0,0.7));padding:18px 12px 10px">
                            <p style="color:white;font-size:13px;font-weight:700;margin:0;
                               white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{name}</p>
                            <p style="color:rgba(255,255,255,0.8);font-size:10px;margin:2px 0 0">{addr[:20]}</p>
                        </div>
                    </div>""", unsafe_allow_html=True)

        arr_l, _, arr_r = st.columns([1, 6, 1])
        with arr_l:
            if idx > 0 and st.button("‹", key="prev_b"):
                st.session_state.banner_idx -= 1
                st.rerun()
        with arr_r:
            if idx < len(banners) - 2 and st.button("›", key="next_b"):
                st.session_state.banner_idx += 1
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
#  라우터
# ══════════════════════════════════════════════════════════════════════════════
view = st.session_state.view

if view == "detail":
    render_detail()
elif view == "list":
    render_list()
else:
    render_home()
