import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import streamlit as st
import tour_api
import naver_validator
import transport_api

st.set_page_config(page_title="트래블리 - 무장애 여행", page_icon="♿", layout="wide")

# ── 지역 데이터 ───────────────────────────────────────────────────────────────
REGIONS = {
    "서울": [], "부산": [], "제주": [], "경기": [],
    "인천": [], "강원": [], "경상": [], "전라": [], "충청": [],
}

CATEGORIES = [
    ("🏛️", "관광지"), ("🎭", "문화시설"), ("🎉", "축제"), ("🛏️", "숙박"), ("🍽️", "음식점"),
]

PAGE_SIZE = 6

# ── 세션 상태 초기화 ─────────────────────────────────────────────────────────
defaults = {
    "view":              "home",
    "selected_si":       None,
    "selected_category": None,
    "place_list":        [],
    "place_list_key":    "",
    "page":              0,
    "selected_place":    None,
    "place_detail":      None,
    "accessibility":     None,
    "recents":           [],
    "random_category":   None,
    "random_places":     [],
    "region_places":     [],
    "region_places_si":  None,
    "banner_festivals":  [],
    "banner_idx":        0,
    "route_result":      None,
    "route_place_id":    None,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

# ── 전역 CSS (반응형) ─────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── 레이아웃 중앙 정렬 & 반응형 너비 ── */
.block-container {
    max-width: 720px !important;
    padding: 1.4rem 1.5rem 4rem !important;
    margin: 0 auto !important;
}
@media (max-width: 768px) {
    .block-container { padding: 1rem 1rem 3.5rem !important; }
}
@media (max-width: 480px) {
    .block-container { padding: 0.8rem 0.75rem 3rem !important; }
}

header { visibility: hidden; }

/* ── 기본 버튼 ── */
div.stButton > button {
    border-radius: 10px; border: 1px solid #e0e0e0;
    background: white; color: #333;
    font-size: clamp(11px, 2vw, 13px);
    padding: 0.5rem 0.8rem;
    transition: all 0.15s;
    box-shadow: 0 1px 3px rgba(0,0,0,0.06);
    min-height: 44px;   /* 터치 타겟 */
    width: 100%;
}
div.stButton > button:hover { border-color: #4A90E2; color: #4A90E2; }

/* ── 카테고리 아이콘 버튼 ── */
.cat-btn > button {
    border-radius: 50% !important; border: 2px solid #eee !important;
    background: #f7f7f7 !important;
    font-size: clamp(18px, 4vw, 22px) !important;
    width: clamp(48px, 10vw, 56px) !important;
    height: clamp(48px, 10vw, 56px) !important;
    min-height: unset !important;
    padding: 0 !important;
}
.cat-btn.active > button {
    border-color: #4A90E2 !important; background: #EBF4FF !important;
}

/* ── 카테고리 칩 (list 뷰) ── */
.chip-pill-row {
    display: flex;
    gap: 8px;
    overflow-x: auto;
    padding: 2px 0 10px;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    -ms-overflow-style: none;
}
.chip-pill-row::-webkit-scrollbar { display: none; }
.chip-pill {
    display: inline-flex;
    align-items: center;
    padding: 7px 16px;
    border-radius: 999px;
    border: 1.5px solid #ddd;
    background: white;
    color: #555;
    font-size: 13px;
    font-weight: 500;
    text-decoration: none !important;
    white-space: nowrap;
    cursor: pointer;
    transition: all 0.15s;
    user-select: none;
}
.chip-pill:hover { border-color: #4A90E2; color: #4A90E2; }
.chip-pill.active {
    background: #4A90E2 !important;
    color: white !important;
    border-color: #4A90E2 !important;
    font-weight: 700 !important;
}

/* ── 지역 모달 버튼 ── */
.region-btn > button {
    border-radius: 12px !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    min-height: 52px !important;
    background: #f7f8fa !important;
    border: 1.5px solid #e8e8e8 !important;
    color: #222 !important;
}
.region-btn > button:hover {
    background: #EBF4FF !important;
    border-color: #4A90E2 !important;
    color: #4A90E2 !important;
}

/* ── 장소 카드 (list 뷰 2열) ── */
.list-card {
    border-radius: 16px; overflow: hidden; background: white;
    box-shadow: 0 2px 14px rgba(0,0,0,0.10); margin-bottom: 4px;
    transition: transform 0.15s, box-shadow 0.15s;
}
.list-card:hover { transform: translateY(-2px); box-shadow: 0 5px 18px rgba(0,0,0,0.14); }
.list-card img { width: 100%; aspect-ratio: 4/3; object-fit: cover; display: block; }
.list-card-body { padding: 10px 12px 12px; }
.list-card-name {
    font-size: clamp(12px, 2.5vw, 14px);
    font-weight: 700; color: #111; margin: 0 0 4px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.list-card-sub {
    font-size: clamp(10px, 2vw, 12px);
    color: #888; margin: 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ── 장소 카드 (home 2열) ── */
.place-card {
    border-radius: 14px; overflow: hidden; background: white;
    box-shadow: 0 2px 10px rgba(0,0,0,0.09);
    transition: transform 0.15s, box-shadow 0.15s;
}
.place-card:hover { transform: translateY(-2px); box-shadow: 0 4px 16px rgba(0,0,0,0.13); }
.place-card img { width: 100%; aspect-ratio: 4/3; object-fit: cover; display: block; }
.place-card-body { padding: 8px 10px 10px; }
.place-card-name {
    font-size: clamp(11px, 2.5vw, 13px);
    font-weight: 700; color: #111; margin: 0 0 3px;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}
.place-card-addr {
    font-size: clamp(10px, 2vw, 11px);
    color: #888; margin: 0;
    white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

/* ── 접근성 카드 ── */
.access-card {
    border-radius: 14px; padding: clamp(12px, 3vw, 16px) clamp(14px, 3vw, 18px);
    background: #f9fafb; border: 1px solid #e8ecf0; margin-bottom: 12px;
}
.access-badge-green { background: #d1fae5; color: #065f46; padding: 3px 10px;
    border-radius: 999px; font-size: 12px; font-weight: 700; display: inline-block; }
.access-badge-yellow { background: #fef9c3; color: #854d0e; padding: 3px 10px;
    border-radius: 999px; font-size: 12px; font-weight: 700; display: inline-block; }
.access-badge-red { background: #fee2e2; color: #991b1b; padding: 3px 10px;
    border-radius: 999px; font-size: 12px; font-weight: 700; display: inline-block; }
.metric-row {
    display: flex; justify-content: space-between; align-items: center;
    padding: 7px 0; border-bottom: 1px solid #eef0f3;
    font-size: clamp(12px, 2.5vw, 13px);
}
.metric-row:last-child { border-bottom: none; }

/* ── 빵 부스러기 ── */
.breadcrumb { font-size: clamp(11px, 2vw, 12px); color: #888; margin-bottom: 14px; }
.breadcrumb span { color: #4A90E2; font-weight: 600; }

/* ── 구분선 ── */
.divider { height: 8px; background: #f2f2f2; margin: 12px -1.5rem; border: none; }
@media (max-width: 480px) { .divider { margin: 10px -0.75rem; } }

/* ── 최근 지역 칩 ── */
.chip-wrap > button {
    border-radius: 999px !important; background: #f0f0f0 !important;
    font-size: 12px !important; padding: 4px 12px !important;
    border: none !important; color: #555 !important;
    box-shadow: none !important; min-height: 34px !important;
}

/* ── 홈 버튼 ── */
.home-btn > button {
    border-radius: 50% !important;
    width: 40px !important; height: 40px !important;
    min-height: 40px !important; padding: 0 !important;
    font-size: 18px !important; border: none !important;
    background: #f5f5f5 !important; box-shadow: none !important;
}
.home-btn > button:hover { background: #e8e8e8 !important; }

/* ── 반응형: 모바일 타이포 ── */
@media (max-width: 480px) {
    h1, h2, h3 { font-size: clamp(15px, 4.5vw, 20px) !important; }
    p, span, div { line-height: 1.55; }
    .list-card-body { padding: 8px 10px 10px !important; }
}
</style>
""", unsafe_allow_html=True)

# ── 쿼리 파라미터로 칩 선택 처리 ─────────────────────────────────────────────
if "cat" in st.query_params:
    _qcat = st.query_params.get("cat", "전체")
    _target = None if _qcat == "전체" else _qcat
    if st.session_state.selected_category != _target:
        st.session_state.selected_category = _target
        st.session_state.page = 0
    del st.query_params["cat"]
    st.rerun()


# ── 캐시 데이터 로딩 ──────────────────────────────────────────────────────────
@st.cache_data(ttl=600, show_spinner=False)
def cached_search(si: str, category: str) -> list[dict]:
    return tour_api.search_places(si, category, num_of_rows=20)

@st.cache_data(ttl=600, show_spinner=False)
def cached_detail(content_id: str) -> dict:
    return tour_api.get_detail(content_id)

@st.cache_data(ttl=1800, show_spinner=False)
def cached_accessibility(name: str, address: str, image_urls: tuple = (),
                         content_id: str = "", category: str = "") -> dict:
    official_info = {}
    if content_id and category:
        content_type_id = tour_api.CONTENT_TYPE_MAP.get(category, "")
        if content_type_id:
            official_info = tour_api.get_accessibility_info(content_id, content_type_id)
    return naver_validator.validate_accessibility(
        name, address, official_info=official_info or None,
        image_urls=list(image_urls), category=category,
    )

@st.cache_data(ttl=300, show_spinner=False)
def cached_naver_festivals() -> list[dict]:
    return naver_validator.search_barrier_free_festivals(area="", display=10)

def _fmt_naver_date(raw: str) -> str:
    """Naver pubDate / postdate → 'YYYY.MM.DD' 형식으로 변환."""
    import re as _re
    if not raw:
        return ""
    if _re.match(r"^\d{8}$", raw):
        return f"{raw[:4]}.{raw[4:6]}.{raw[6:]}"
    _MONTHS = {"Jan":"01","Feb":"02","Mar":"03","Apr":"04","May":"05","Jun":"06",
               "Jul":"07","Aug":"08","Sep":"09","Oct":"10","Nov":"11","Dec":"12"}
    m = _re.search(r"(\d{1,2})\s+(\w{3})\s+(\d{4})", raw)
    if m:
        day, mon, year = m.group(1), m.group(2), m.group(3)
        return f"{year}.{_MONTHS.get(mon, mon)}.{day.zfill(2)}"
    return raw[:10] if len(raw) >= 10 else raw


@st.cache_data(ttl=300, show_spinner=False)
def cached_random_festivals(count: int = 6) -> list[dict]:
    """
    네이버 뉴스·블로그에서 2026년 무장애 축제만 수집하고
    각 기사 URL의 og:image를 포스터로 사용. 병렬 OGP 수집.
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    # 1) 네이버에서 2026년 최신 무장애 축제 기사 수집
    naver_raw = naver_validator.search_barrier_free_festivals(area="", display=20)

    candidates = []
    for item in naver_raw:
        title   = item.get("title", "")
        snippet = item.get("snippet", "")
        date_r  = item.get("date", "")
        link    = item.get("link", "")
        source  = item.get("source", "")
        # 2026 필터 — 제목/스니펫/날짜 중 하나라도 2026 포함
        if "2026" not in title and "2026" not in snippet and "2026" not in date_r:
            continue
        candidates.append({
            "이름":    title,
            "주소":    _fmt_naver_date(date_r),
            "image":   "",
            "link":    link,
            "source":  source,
            "snippet": snippet,
            "content_id": "",
            "카테고리": "축제",
        })
        if len(candidates) >= count * 2:
            break

    # 2026 기사가 없으면 연도 필터 완화
    if not candidates:
        for item in naver_raw:
            link   = item.get("link", "")
            date_r = item.get("date", "")
            candidates.append({
                "이름":    item.get("title", ""),
                "주소":    _fmt_naver_date(date_r),
                "image":   "",
                "link":    link,
                "source":  item.get("source", ""),
                "snippet": item.get("snippet", ""),
                "content_id": "",
                "카테고리": "축제",
            })
            if len(candidates) >= count * 2:
                break

    # 2) 병렬 OGP 이미지 수집
    with ThreadPoolExecutor(max_workers=min(len(candidates), 8)) as executor:
        future_map = {
            executor.submit(naver_validator.fetch_og_image, c["link"]): i
            for i, c in enumerate(candidates) if c["link"]
        }
        for future in as_completed(future_map):
            idx = future_map[future]
            try:
                candidates[idx]["image"] = future.result()
            except Exception:
                pass

    # 3) 이미지 있는 것 우선 정렬 후 count개 반환
    candidates.sort(key=lambda c: 1 if c.get("image") else 0, reverse=True)
    return candidates[:count]

@st.cache_data(ttl=300, show_spinner=False)
def cached_festival_latest(si: str) -> list[dict]:
    """네이버 최신 뉴스 키워드 + 관광공사 현재날짜 필터 하이브리드.
    네이버에서 언급된 축제명을 우선 노출하고, 이미지 있는 항목을 우선 정렬."""
    # 1) 네이버로 지역 최신 축제 이름 수집
    naver_raw = naver_validator.search_barrier_free_festivals(area=si, display=10)
    naver_text = " ".join(r.get("title", "") + " " + r.get("snippet", "") for r in naver_raw)

    # 2) 관광공사 searchFestival2 — 오늘 이후 축제만 (image 포함)
    tour_list = tour_api.search_festivals(area_name=si, num_of_rows=20)
    tour_list = [f for f in tour_list if "error" not in f and "message" not in f]

    # 지역명 매핑 실패 시 전국으로 폴백
    if not tour_list:
        tour_list = tour_api.search_festivals(num_of_rows=20)
        tour_list = [f for f in tour_list if "error" not in f and "message" not in f]

    # 3) 네이버에 언급된 축제를 먼저, 이미지 있는 것 우선
    def sort_key(f):
        in_naver = 1 if f.get("이름", "") and f["이름"] in naver_text else 0
        has_img  = 1 if f.get("image") else 0
        return (in_naver, has_img)

    tour_list.sort(key=sort_key, reverse=True)
    return tour_list[:12]

@st.cache_data(ttl=600, show_spinner=False)
def cached_region_random(si: str) -> list[dict]:
    import random
    all_places = []
    for category in ["관광지", "문화시설", "숙박", "음식점"]:
        places = tour_api.search_places(si, category, num_of_rows=20)
        all_places.extend([p for p in places if p.get("image")][:5])
    random.shuffle(all_places)
    return all_places[:12]


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
        parts.append(
            "입구에 단차가 있으나 경사로가 마련되어 있습니다" if ramp
            else f"입구에 단차({'약 ' + str(h) + 'cm ' if h else ''}있음)가 확인됩니다"
        )
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
        return name + "은 " + ", ".join(parts[:2]) + "합니다."
    if "🟢" in risk:
        return f"{name}은 접근성이 전반적으로 양호한 것으로 보입니다."
    if "🔴" in risk:
        return f"{name}은 일부 접근성 개선이 필요한 것으로 보입니다."
    return f"{name}의 접근성 정보를 분석했습니다."


# ── 지역 선택 모달 ────────────────────────────────────────────────────────────
@st.dialog("지역 선택")
def region_modal():
    st.markdown('<p style="font-size:13px;color:#888;margin-bottom:16px">여행할 지역을 선택하세요</p>', unsafe_allow_html=True)

    def _go(si: str):
        st.session_state.selected_si = si
        if si not in st.session_state.recents:
            st.session_state.recents.insert(0, si)
            st.session_state.recents = st.session_state.recents[:5]
        st.session_state.selected_category = None
        st.session_state.page = 0
        st.session_state.region_places = []
        st.session_state.region_places_si = None
        st.session_state.view = "list"
        # 카테고리 칩 상태 초기화 (새 지역 선택 시 전체로 리셋)
        st.session_state.pop(f"cat_pills_{si}", None)

    cities = list(REGIONS.keys())
    rows = [cities[i:i+3] for i in range(0, len(cities), 3)]
    for row in rows:
        cols = st.columns(3, gap="small")
        for j, si in enumerate(row):
            with cols[j]:
                st.markdown('<div class="region-btn">', unsafe_allow_html=True)
                if st.button(si, key=f"modal_si_{si}", use_container_width=True):
                    _go(si)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)
        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)


# ── 축제 전용 카드 렌더 (네이버 뉴스/블로그 기반) ────────────────────────────
def _render_festival_cards(festivals: list[dict]):
    """Naver 기사 기반 축제 포스터 카드. og:image 있으면 포스터 표시, 없으면 그라디언트 카드."""
    COLORS = ["#4A90E2", "#E2844A", "#4AE28C", "#E24A7A", "#9B4AE2", "#E2C44A"]
    rows = [festivals[i:i+2] for i in range(0, len(festivals), 2)]
    for row_idx, row in enumerate(rows):
        cols = st.columns(2, gap="small")
        for j, item in enumerate(row):
            with cols[j]:
                name    = item.get("이름", item.get("title", "무장애 축제"))
                img     = item.get("image", "")
                date_s  = item.get("주소", "")   # 날짜를 주소 필드에 저장
                link    = item.get("link", "#")
                source  = item.get("source", "")
                snippet = item.get("snippet", "")
                source_label = "📰 뉴스" if source == "news" else "📝 블로그"
                name_short   = name[:28] + "…" if len(name) > 28 else name
                snippet_short = snippet[:45] + "…" if len(snippet) > 45 else snippet
                color = COLORS[(row_idx * 2 + j) % len(COLORS)]

                if img:
                    st.markdown(f"""
                    <a href="{link}" target="_blank" style="text-decoration:none">
                    <div style="border-radius:16px;overflow:hidden;background:white;
                                box-shadow:0 2px 12px rgba(0,0,0,0.09);margin-bottom:4px">
                        <img src="{img}" alt="{name_short}"
                             style="width:100%;height:130px;object-fit:cover;display:block"/>
                        <div style="padding:10px 12px 12px">
                            <span style="background:{color};color:white;font-size:9px;
                                         font-weight:700;padding:2px 6px;border-radius:4px;
                                         display:inline-block;margin-bottom:5px">{source_label}</span>
                            <p style="font-size:clamp(12px,2.5vw,13px);font-weight:700;
                                      margin:0 0 4px;line-height:1.4;color:#222;
                                      display:-webkit-box;-webkit-line-clamp:2;
                                      -webkit-box-orient:vertical;overflow:hidden">{name_short}</p>
                            <span style="font-size:10px;color:#bbb">📅 {date_s}</span>
                        </div>
                    </div>
                    </a>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <a href="{link}" target="_blank" style="text-decoration:none">
                    <div style="border-radius:16px;overflow:hidden;background:white;
                                box-shadow:0 2px 12px rgba(0,0,0,0.09);margin-bottom:4px">
                        <div style="background:{color};padding:18px 14px 14px;min-height:80px;
                                    display:flex;flex-direction:column;justify-content:flex-end">
                            <span style="background:rgba(255,255,255,0.25);color:white;font-size:9px;
                                         font-weight:700;padding:2px 7px;border-radius:4px;
                                         display:inline-block;margin-bottom:6px;width:fit-content">{source_label}</span>
                            <p style="color:white;font-size:clamp(12px,2.5vw,13px);font-weight:700;
                                      margin:0;line-height:1.4;
                                      display:-webkit-box;-webkit-line-clamp:2;
                                      -webkit-box-orient:vertical;overflow:hidden">{name_short}</p>
                        </div>
                        <div style="padding:10px 14px 12px">
                            <p style="font-size:11px;color:#888;margin:0 0 6px;line-height:1.4">{snippet_short}</p>
                            <span style="font-size:10px;color:#bbb">📅 {date_s}</span>
                        </div>
                    </div>
                    </a>""", unsafe_allow_html=True)
        st.markdown('<div style="height:4px"></div>', unsafe_allow_html=True)


# ── 공통: 카드 그리드 렌더 ────────────────────────────────────────────────────
def _render_card_grid(places: list[dict], key_prefix: str, cols: int = 2, compact: bool = False):
    """places 목록을 cols열 카드 그리드로 렌더링. 자세히보기 클릭 시 detail 뷰."""
    rows = [places[i:i+cols] for i in range(0, len(places), cols)]
    img_style = ' style="aspect-ratio:16/9;max-height:140px;width:100%;object-fit:cover;display:block;"' if compact else ""
    for row in rows:
        c = st.columns(cols, gap="small")
        for j, place in enumerate(row):
            with c[j]:
                img  = place.get("image", "")
                name = place.get("이름", "")
                addr = place.get("주소", "")
                addr_short = addr[:16] + "…" if len(addr) > 16 else addr
                card_cls = "list-card" if cols == 2 else "place-card"
                name_cls = "list-card-name" if cols == 2 else "place-card-name"
                sub_cls  = "list-card-sub"  if cols == 2 else "place-card-addr"
                body_cls = "list-card-body" if cols == 2 else "place-card-body"

                if img:
                    st.markdown(f"""
                    <div class="{card_cls}">
                        <img src="{img}" alt="{name}"{img_style}/>
                        <div class="{body_cls}">
                            <p class="{name_cls}">{name}</p>
                            <p class="{sub_cls}">📍 {addr_short}</p>
                        </div>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.markdown(f"""
                    <div class="{card_cls}" style="padding:28px 12px;text-align:center;min-height:100px">
                        <p class="{name_cls}">{name}</p>
                        <p class="{sub_cls}">📍 {addr_short}</p>
                    </div>""", unsafe_allow_html=True)

                if st.button("자세히 보기",
                             key=f"{key_prefix}_{place.get('content_id','')}_{j}",
                             use_container_width=True):
                    with st.spinner(f"{name} 정보 불러오는 중..."):
                        detail = cached_detail(place["content_id"])
                    st.session_state.selected_place  = place
                    st.session_state.place_detail    = detail
                    st.session_state.accessibility   = None
                    st.session_state.view            = "detail"
                    st.rerun()
        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
#  뷰: 상세 페이지
# ══════════════════════════════════════════════════════════════════════════════
def render_detail():
    place  = st.session_state.selected_place
    detail = st.session_state.place_detail
    si  = st.session_state.selected_si or ""
    cat = st.session_state.selected_category or ""

    if st.button("← 목록으로"):
        st.session_state.view = "list"
        st.rerun()

    st.markdown(
        f'<div class="breadcrumb">{si} › <span>{cat}</span> › <span>{place.get("이름","")}</span></div>',
        unsafe_allow_html=True,
    )

    name     = detail.get("이름") or place.get("이름", "")
    addr     = detail.get("주소") or place.get("주소", "")
    images   = detail.get("images", [])
    overview = detail.get("개요", "")
    tel      = detail.get("전화번호", "")

    if images:
        st.image(images[0], use_container_width=True)
        if len(images) > 1:
            st.image(images[1], use_container_width=True)

    st.markdown(f"### {name}")
    if addr:
        st.markdown(f"📍 {addr}")
    if tel and tel != "정보 없음":
        st.markdown(f"📞 {tel}")
    if overview and overview != "정보 없음":
        with st.expander("장소 소개", expanded=True):
            st.write(overview)

    st.markdown('<hr class="divider"/>', unsafe_allow_html=True)
    st.markdown("#### ♿ 실시간 접근성 검증")
    st.caption("네이버 블로그·지식iN 리뷰 + GPT-4.1 추론 기반 자동 분석")

    if st.session_state.accessibility is None:
        content_id = place.get("content_id", "")
        category   = place.get("카테고리", "")

        extra_step = "<div style='background:white;border:1px solid #bee3f8;border-radius:20px;padding:4px 12px;font-size:11px;color:#2b6cb0;font-weight:600;display:inline-block'>🏨 공식홈페이지 확인</div>" if category == "숙박" else ""
        step_style = "background:white;border:1px solid #bee3f8;border-radius:20px;padding:4px 12px;font-size:11px;color:#2b6cb0;font-weight:600;display:inline-block"
        loading_html = (
            "<style>"
            "@keyframes acc-spin{0%{transform:rotate(0deg) scale(1)}25%{transform:rotate(15deg) scale(1.1)}50%{transform:rotate(0deg) scale(1)}75%{transform:rotate(-15deg) scale(1.1)}100%{transform:rotate(0deg) scale(1)}}"
            "@keyframes acc-pulse{0%,100%{opacity:1}50%{opacity:0.45}}"
            "@keyframes acc-bar{0%{width:0%}40%{width:55%}80%{width:85%}100%{width:95%}}"
            "</style>"
            "<div style='background:linear-gradient(135deg,#f0f7ff 0%,#e8f5e9 100%);border-radius:18px;padding:28px 24px 22px;text-align:center;border:1.5px solid #c8e6fa;margin:8px 0 12px'>"
            "<div style='font-size:52px;display:inline-block;animation:acc-spin 1.6s ease-in-out infinite;margin-bottom:12px;line-height:1'>♿</div>"
            "<p style='font-size:17px;font-weight:700;color:#1a73e8;margin:0 0 6px'>접근성 검증 중입니다…</p>"
            "<p style='font-size:13px;color:#555;margin:0 0 16px;animation:acc-pulse 2s ease-in-out infinite'>리뷰를 수집하고 AI가 분석하는 중이에요</p>"
            "<div style='display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin-bottom:16px'>"
            f"<div style='{step_style}'>📡 네이버 블로그 수집</div>"
            f"<div style='{step_style}'>💬 지식iN 검색</div>"
            f"{extra_step}"
            f"<div style='{step_style}'>🤖 GPT 추론</div>"
            f"<div style='{step_style}'>📸 이미지 분석</div>"
            "</div>"
            "<div style='background:#dbeafe;border-radius:999px;height:6px;overflow:hidden;max-width:280px;margin:0 auto 12px'>"
            "<div style='height:100%;background:linear-gradient(90deg,#4A90E2,#38a169);border-radius:999px;animation:acc-bar 18s ease-out forwards'></div>"
            "</div>"
            "<p style='font-size:11px;color:#888'>보통 15~30초 소요됩니다 · 잠시만 기다려 주세요 🙏</p>"
            "</div>"
        )
        loading_slot = st.empty()
        loading_slot.markdown(loading_html, unsafe_allow_html=True)

        st.session_state.accessibility = cached_accessibility(
            name, addr, tuple(images), content_id=content_id, category=category
        )
        loading_slot.empty()
        st.rerun()

    acc       = st.session_state.accessibility
    risk      = acc.get("overall_risk", "❓")
    data_info = acc.get("data_collected", {})
    gpt       = acc.get("gpt_inference", {})
    metrics   = gpt.get("metrics", {})
    official_info    = acc.get("official_info", {})
    hotel_directions = acc.get("hotel_directions", {})
    confidence    = gpt.get("confidence", "")
    gpt_summary   = gpt.get("summary", "")
    conflicts     = gpt.get("conflicts_with_official", [])
    positives     = acc.get("positive_signals", [])
    warnings      = acc.get("warnings", [])
    top_sources   = acc.get("top_sources", [])
    vision        = acc.get("vision_analysis", {})

    # ── overall_risk 보정: "알 수 없음"이지만 핵심 시설이 확인된 경우 ────────────
    # confirmed_facilities: 개별 metric 렌더링에서도 동일하게 "있음"으로 표시하기 위해 추적
    confirmed_facilities: set[str] = set()

    def _facility_confirmed(key: str) -> bool:
        m = metrics.get(key, {})
        if m.get("available") is True:
            return True
        _kw_map = {
            "accessible_parking":  ("주차 안내", "주차"),
            "accessible_restroom": ("장애인 화장실", "화장실"),
        }
        _label_key, _kw = _kw_map.get(key, ("", ""))
        if not _label_key:
            return False
        _combined = " ".join(official_info.values())
        return bool(official_info.get(_label_key, "") or _kw in _combined)

    if "❓" in risk or "알 수 없음" in risk:
        confirmed_labels = []
        if _facility_confirmed("accessible_parking"):
            confirmed_labels.append("장애인 주차장")
            confirmed_facilities.add("accessible_parking")
        if _facility_confirmed("accessible_restroom"):
            confirmed_labels.append("장애인 화장실")
            confirmed_facilities.add("accessible_restroom")

        if confirmed_labels:
            risk = "🟢 이용 가능"
            label_str = " · ".join(confirmed_labels)
            if gpt_summary:
                gpt_summary = f"{label_str} 있음 확인. {gpt_summary}"
            else:
                gpt_summary = f"{label_str} 있음 — 전반적으로 이용 용이"

    badge_css = "access-badge-green" if "🟢" in risk else ("access-badge-red" if "🔴" in risk else "access-badge-yellow")
    conf_label = {"high": "🟢 높음", "medium": "🟡 보통", "low": "🔴 낮음"}.get(confidence, "")
    summary_html = f'<p style="font-size:14px;color:#333;margin:8px 0 0;line-height:1.6">💬 {gpt_summary}</p>' if gpt_summary else ""

    st.markdown(f"""
    <div class="access-card">
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:6px;flex-wrap:wrap;gap:6px">
            <span class="{badge_css}">{risk}</span>
            <span style="font-size:11px;color:#aaa">
                {f"신뢰도 {conf_label} &nbsp;·&nbsp; " if conf_label else ""}블로그 {data_info.get('blog_posts',0)}건 · 지식iN {data_info.get('kin_posts',0)}건
            </span>
        </div>
        {summary_html}
    </div>
    """, unsafe_allow_html=True)

    # ── 긍정 신호 칩 ─────────────────────────────────────────────────────────
    if positives:
        chips = " ".join(
            f'<span style="background:#e8f5e9;color:#2e7d32;border-radius:20px;'
            f'padding:3px 10px;font-size:12px;margin:2px;display:inline-block">✅ {kw}</span>'
            for kw in positives[:8]
        )
        st.markdown(f'<div style="margin:6px 0 10px">{chips}</div>', unsafe_allow_html=True)

    # ── 4개 접근성 지표 ───────────────────────────────────────────────────────
    METRIC_LABELS = {
        "entrance_step":       ("🚪", "입구 단차"),
        "elevator":            ("🛗", "엘리베이터"),
        "accessible_restroom": ("🚻", "장애인 화장실"),
        "accessible_parking":  ("🅿️", "장애인 주차"),
    }

    _OUTDOOR_KW = (
        "해수욕장", "해변", "바닷가", "거리", "광장", "공원", "호수", "궁",
        "능", "원", "둘레길", "산책로", "해안", "갯벌", "섬", "계곡", "폭포",
        "해협", "하천", "강변", "숲", "고원", "산", "오름",
    )
    is_outdoor = any(kw in name for kw in _OUTDOOR_KW)

    for key, (icon, label) in METRIC_LABELS.items():
        m = metrics.get(key, {})
        status = m.get("status", "❓")
        evidence = m.get("evidence", [])
        inference_note = m.get("inference_note", "")

        if key == "entrance_step":
            v = "단차 없음" if m.get("has_step") is False else ("단차 있음" if m.get("has_step") else "미확인")
            h = m.get("estimated_height_cm")
            if h:
                v += f" (~{h}cm)"
            if m.get("has_ramp_alternative"):
                v += ", 경사로 있음"
        elif key in ("elevator", "accessible_restroom", "accessible_parking"):
            available = m.get("available")
            # official 데이터로 이미 확인된 시설은 GPT 판단과 무관하게 "있음"으로 표시
            if key in confirmed_facilities:
                v = "있음"
                if available is not True:
                    status = "🟢"
                    inference_note = "📋 KTO 공식 등록 데이터 기반"
            elif available is True:
                v = "있음"
            elif available is False:
                v = "없음"
            else:
                # 야외 장소는 엘리베이터가 애초에 해당 없음
                if key == "elevator" and is_outdoor:
                    v = "해당없음"
                    status = "➖"
                else:
                    # GPT가 판단 못한 경우 KTO 공식 데이터로 fallback
                    _kw_map = {
                        "accessible_parking":  ("주차 안내", "주차"),
                        "accessible_restroom": ("장애인 화장실", "화장실"),
                        "elevator":            ("엘리베이터", "승강기"),
                    }
                    _label_key, _kw = _kw_map[key]
                    _official_val = official_info.get(_label_key, "")
                    _combined = " ".join(official_info.values())
                    if _official_val or _kw in _combined:
                        v = _official_val if _official_val else "있음"
                        status = "🟢"
                        inference_note = "📋 KTO 공식 등록 데이터 기반"
                    else:
                        v = "미확인"
        else:
            v = "미확인"

        st.markdown(
            f'<div class="metric-row"><span>{icon} {label}</span>'
            f'<span style="color:#555">{v} {status}</span></div>',
            unsafe_allow_html=True,
        )
        if evidence or inference_note:
            with st.expander("상세 근거", expanded=False):
                if inference_note:
                    st.markdown(f"**추론:** {inference_note}")
                for ev in (evidence or [])[:3]:
                    if ev == "리뷰 없음 — 지식 기반 추론":
                        st.caption(ev)
                    elif ev:
                        st.markdown(f'> "{ev}"')

    # ── 주의사항 경고 ─────────────────────────────────────────────────────────
    if warnings:
        with st.expander(f"⚠️ 주의사항 {len(warnings)}건", expanded=True):
            for w in warnings:
                excerpt   = w.get("excerpt", "")
                inference = w.get("inference", "")
                date_str  = w.get("date", "")
                link      = w.get("link", "")
                st.markdown(f"**{w.get('severity','')}** — {w.get('category','')}")
                if excerpt:
                    st.markdown(f"> {excerpt}")
                if inference:
                    st.caption(f"💡 {inference}")
                if date_str or link:
                    st.caption(("출처: " + date_str if date_str else "") + (f"  [링크]({link})" if link else ""))
                st.divider()

    # ── 공식 정보와 상충 ──────────────────────────────────────────────────────
    if conflicts:
        with st.expander(f"🔶 공식 정보와 상충하는 내용 {len(conflicts)}건"):
            for c in conflicts:
                st.markdown(f"- **공식 주장:** {c.get('official_claim', '')}")
                st.markdown(f"  **실제 발견:** {c.get('actual_finding', '')}")
                if c.get("evidence"):
                    st.markdown(f'  > "{c.get("evidence")}"')

    # ── 사진 분석 (Vision) ────────────────────────────────────────────────────
    if vision and not vision.get("error"):
        with st.expander("📷 사진 분석 결과"):
            v_risk = vision.get("overall_risk", "")
            v_conf = vision.get("confidence", "")
            if v_risk:
                st.markdown(f"**종합 판정:** {v_risk}" + (f" (신뢰도: {v_conf})" if v_conf else ""))
            entrance_v = vision.get("entrance", {})
            if entrance_v:
                door = entrance_v.get("door_type", "")
                step = entrance_v.get("step_detected")
                ramp = entrance_v.get("ramp_detected")
                parts_v = []
                if door and door != "미확인":
                    parts_v.append(f"출입문: {door}")
                if step is True:
                    h_v = entrance_v.get("step_height_cm_est")
                    parts_v.append("단차 발견" + (f" (~{h_v}cm)" if h_v else ""))
                elif step is False:
                    parts_v.append("단차 없음")
                if ramp:
                    parts_v.append("경사로 있음")
                if parts_v:
                    st.markdown("🚪 **입구:** " + " / ".join(parts_v))
                notes_v = entrance_v.get("notes", "")
                if notes_v:
                    st.caption(notes_v)
            interior_v = vision.get("interior", {})
            if interior_v:
                tt_v = interior_v.get("table_type", "")
                th_v = interior_v.get("table_height_cm_est")
                aw_v = interior_v.get("aisle_width_cm_est")
                parts_v = []
                if tt_v and tt_v != "미확인":
                    parts_v.append(f"테이블: {tt_v}")
                if th_v:
                    parts_v.append(f"높이 ~{th_v}cm")
                if aw_v:
                    parts_v.append(f"통로 ~{aw_v}cm")
                if parts_v:
                    st.markdown("🏠 **내부:** " + " / ".join(parts_v))
                notes_v = interior_v.get("notes", "")
                if notes_v:
                    st.caption(notes_v)
            obstacles = vision.get("obstacles", [])
            facilities = vision.get("facilities", [])
            if obstacles:
                st.markdown("⚠️ **장애물:** " + ", ".join(obstacles))
            if facilities:
                st.markdown("✅ **편의시설:** " + ", ".join(facilities))

    # ── 분석 출처 ─────────────────────────────────────────────────────────────
    if top_sources:
        with st.expander(f"📰 분석 출처 {len(top_sources)}건"):
            for src in top_sources:
                title_s = src.get("title", "")
                date_s  = src.get("date", "")
                link_s  = src.get("link", "")
                if title_s and link_s:
                    st.markdown(f"- [{title_s}]({link_s})" + (f" ({date_s})" if date_s else ""))
                elif title_s:
                    st.markdown(f"- {title_s}" + (f" ({date_s})" if date_s else ""))

    st.markdown('<hr class="divider"/>', unsafe_allow_html=True)
    st.markdown("#### 🗺 가는 법 안내")

    # ── 숙박: 공식 홈페이지 오시는 길 카드 ─────────────────────────────────────
    if hotel_directions and any(hotel_directions.get(k) for k in ("subway", "bus", "car", "parking")):
        rows = ""
        _icons = {"subway": "🚇", "bus": "🚌", "car": "🚗", "parking": "🅿️"}
        _labels = {"subway": "지하철", "bus": "버스", "car": "자동차", "parking": "주차"}
        for key in ("subway", "bus", "car", "parking"):
            val = hotel_directions.get(key, "").strip()
            if val:
                rows += (
                    f'<p style="font-size:12px;color:#555;margin:3px 0">'
                    f'{_icons[key]} <b>{_labels[key]}</b>: {val}</p>'
                )
        src_url = hotel_directions.get("source_url", "")
        src_link = (f'<a href="{src_url}" target="_blank" '
                    f'style="font-size:11px;color:#4A90E2">출처 보기 →</a>') if src_url else ""
        st.markdown(f"""
        <div style="background:#f0f7ff;border-radius:14px;padding:14px 16px;
                    margin-bottom:12px;border-left:4px solid #4A90E2">
            <p style="font-size:13px;font-weight:700;color:#4A90E2;margin:0 0 8px">
                🏨 공식 홈페이지 오시는 길</p>
            {rows}
            <div style="margin-top:6px">{src_link}</div>
        </div>""", unsafe_allow_html=True)

    # 장소가 바뀌면 이전 경로 결과 초기화
    place_id = place.get("content_id", name)
    if st.session_state.route_place_id != place_id:
        st.session_state.route_result   = None
        st.session_state.route_place_id = place_id

    dest_addr = addr or name
    origin = st.text_input(
        "출발지를 입력하세요",
        placeholder="예: 서울 마포구 홍대입구역",
        key=f"route_origin_{place_id}",
    )
    if st.button("♿ 무장애 경로 안내받기", use_container_width=True, type="primary"):
        if not origin.strip():
            st.warning("출발지를 입력해 주세요.")
        else:
            with st.spinner(f"{origin} → {name} 무장애 경로 분석 중..."):
                st.session_state.route_result = transport_api.plan_accessible_route(
                    origin.strip(), dest_addr
                )
            st.rerun()

    route = st.session_state.route_result
    if route:
        참고 = route.get("참고사항", [])
        car  = route.get("자동차_경로", {})
        transit = route.get("대중교통_경로", {})
        버스정보 = route.get("저상버스", {})
        엘리베이터 = route.get("엘리베이터", [])
        고장 = route.get("리프트_고장", [])
        택시 = route.get("장애인콜택시", {})

        st.markdown(f"""
        <div style="background:#f8f9ff;border-radius:14px;padding:16px 18px;margin-top:8px;
                    border-left:4px solid #4A90E2">
            <p style="font-size:13px;font-weight:700;color:#4A90E2;margin:0 0 10px">
                🗺 무장애 경로 안내</p>
            <p style="font-size:12px;color:#555;margin:2px 0">
                📍 <b>출발지</b>: {route.get("출발지","")}</p>
            <p style="font-size:12px;color:#555;margin:2px 0 10px">
                📍 <b>목적지</b>: {route.get("목적지","")}</p>
        </div>""", unsafe_allow_html=True)

        # 자동차/택시 경로
        if "distance_km" in car:
            st.markdown(f"""
            <div style="background:white;border-radius:12px;padding:12px 16px;margin-top:8px;
                        box-shadow:0 1px 6px rgba(0,0,0,0.07)">
                <p style="font-size:12px;font-weight:700;color:#333;margin:0 0 6px">🚗 자동차 / 택시</p>
                <p style="font-size:12px;color:#555;margin:2px 0">
                    약 {car['distance_km']}km &nbsp;|&nbsp; 예상 {car['duration_min']}분</p>
                <p style="font-size:12px;color:#888;margin:2px 0">
                    예상 택시 요금: {car.get('taxi_fare',0):,}원</p>
            </div>""", unsafe_allow_html=True)

        # 대중교통 경로 (ODsay)
        if "error" not in transit and transit.get("총_소요시간"):
            st.markdown(f"""
            <div style="background:white;border-radius:12px;padding:12px 16px;margin-top:8px;
                        box-shadow:0 1px 6px rgba(0,0,0,0.07)">
                <p style="font-size:12px;font-weight:700;color:#333;margin:0 0 6px">
                    🚄 대중교통 (기차/지하철/버스)</p>
                <p style="font-size:12px;color:#555;margin:2px 0">
                    총 소요시간: {transit['총_소요시간']} &nbsp;|&nbsp; 요금: {transit['총_요금']}</p>
                <p style="font-size:12px;color:#555;margin:2px 0">
                    경로: {transit.get('경로_요약','')}</p>
                <p style="font-size:11px;color:#888;margin:2px 0">
                    {transit.get('상세_환승_단계','')}</p>
            </div>""", unsafe_allow_html=True)

        # 저상버스
        if isinstance(버스정보, dict) and 버스정보.get("도착정보"):
            arrivals = [b for b in 버스정보["도착정보"] if "error" not in b and "message" not in b]
            low_floor = [b for b in arrivals if "저상버스" in b.get("저상버스", "")]
            if low_floor or arrivals:
                rows_html = "".join(
                    f'<p style="font-size:11px;color:#555;margin:2px 0">'
                    f'{b["버스번호"]} {b["저상버스"]} &nbsp;▶&nbsp; {b["첫번째도착"]}</p>'
                    for b in (low_floor or arrivals)[:3]
                )
                st.markdown(f"""
                <div style="background:white;border-radius:12px;padding:12px 16px;margin-top:8px;
                            box-shadow:0 1px 6px rgba(0,0,0,0.07)">
                    <p style="font-size:12px;font-weight:700;color:#333;margin:0 0 6px">
                        🚌 저상버스 ({버스정보.get('정류장명','')})</p>
                    {rows_html}
                </div>""", unsafe_allow_html=True)

        # 지하철 엘리베이터
        valid_elev = [e for e in 엘리베이터 if "error" not in e and "message" not in e]
        if valid_elev:
            rows_html = "".join(
                f'<p style="font-size:11px;color:#555;margin:2px 0">'
                f'{e.get("호선","")} {e.get("역명","")} — {e.get("위치","")}</p>'
                for e in valid_elev[:3]
            )
            st.markdown(f"""
            <div style="background:white;border-radius:12px;padding:12px 16px;margin-top:8px;
                        box-shadow:0 1px 6px rgba(0,0,0,0.07)">
                <p style="font-size:12px;font-weight:700;color:#333;margin:0 0 6px">
                    🛗 지하철 엘리베이터</p>
                {rows_html}
            </div>""", unsafe_allow_html=True)

        # 고장 현황
        valid_fault = [f for f in 고장 if "error" not in f and f.get("상태")]
        fault_html = "".join(
            f'<p style="font-size:11px;color:#e53935;margin:2px 0">'
            f'⚠ {f["역명"]} {f["위치"]} — {f["상태"]}</p>'
            for f in valid_fault[:3]
        ) if valid_fault else '<p style="font-size:11px;color:#4CAF50;margin:2px 0">✅ 현재 고장·점검 없음</p>'
        st.markdown(f"""
        <div style="background:white;border-radius:12px;padding:12px 16px;margin-top:8px;
                    box-shadow:0 1px 6px rgba(0,0,0,0.07)">
            <p style="font-size:12px;font-weight:700;color:#333;margin:0 0 6px">
                ⚠️ 엘리베이터 점검·고장 현황</p>
            {fault_html}
        </div>""", unsafe_allow_html=True)

        # 장애인 콜택시
        if 택시.get("이름"):
            st.markdown(f"""
            <div style="background:white;border-radius:12px;padding:12px 16px;margin-top:8px;
                        box-shadow:0 1px 6px rgba(0,0,0,0.07)">
                <p style="font-size:12px;font-weight:700;color:#333;margin:0 0 6px">
                    ♿ 장애인 콜택시</p>
                <p style="font-size:12px;color:#555;margin:2px 0">{택시['이름']}</p>
                <p style="font-size:12px;color:#555;margin:2px 0">📞 {택시['전화']}</p>
                {'<p style="font-size:11px;color:#888;margin:2px 0">앱: ' + 택시['앱'] + '</p>' if 택시.get('앱') and 택시['앱'] != '없음' else ''}
            </div>""", unsafe_allow_html=True)

        # 참고사항
        if 참고:
            tips = "".join(f'<p style="font-size:11px;color:#555;margin:2px 0">💡 {t}</p>' for t in 참고)
            st.markdown(f"""
            <div style="background:#fffde7;border-radius:12px;padding:12px 16px;margin-top:8px">
                {tips}
            </div>""", unsafe_allow_html=True)

        # 카카오맵 링크
        origin_val = route.get("출발지", "")
        kakao_url = f"https://map.kakao.com/?sName={origin_val}&eName={dest_addr}"
        st.markdown(
            f'<a href="{kakao_url}" target="_blank">'
            f'<button style="background:#FEE500;border:none;border-radius:10px;padding:10px 24px;'
            f'font-weight:700;font-size:14px;cursor:pointer;width:100%;margin-top:10px">'
            f'🗺 카카오맵에서 길찾기</button></a>',
            unsafe_allow_html=True,
        )


# ══════════════════════════════════════════════════════════════════════════════
#  뷰: 지역 탐색 페이지 (지역 선택 후)
# ══════════════════════════════════════════════════════════════════════════════
def render_list():
    si  = st.session_state.selected_si or ""
    cat = st.session_state.selected_category

    # ── 헤더 ──────────────────────────────────────────────────────────────────
    h_home, h_title = st.columns([1, 9])
    with h_home:
        st.markdown('<div class="home-btn">', unsafe_allow_html=True)
        if st.button("🏠", key="list_home"):
            st.session_state.pop(f"cat_pills_{si}", None)
            st.session_state.view = "home"
            st.session_state.selected_category = None
            st.rerun()
        st.markdown('</div>', unsafe_allow_html=True)
    with h_title:
        st.markdown(
            f'<h2 style="font-size:clamp(17px,4vw,20px);font-weight:800;margin:4px 0 2px;color:#111">'
            f'<span style="color:#4A90E2">{si}</span> 무장애 여행지</h2>',
            unsafe_allow_html=True,
        )

    # ── 카테고리 칩 (st.pills — 페이지 이동 없이 인플레이스 전환) ──────────────
    chip_options = ["전체", "관광지", "문화시설", "축제", "숙박", "음식점"]
    selected_chip = st.pills(
        "카테고리",
        chip_options,
        default="전체" if cat is None else cat,
        key=f"cat_pills_{si}",
        label_visibility="collapsed",
    )
    if selected_chip is not None:
        new_cat = None if selected_chip == "전체" else selected_chip
        if new_cat != cat:
            st.session_state.selected_category = new_cat
            st.session_state.page = 0
            st.session_state.place_list = []
            st.session_state.place_list_key = ""
            st.rerun()
    cat = st.session_state.selected_category

    # ── 장소 데이터 로드 ──────────────────────────────────────────────────────
    if cat is None:
        if (not st.session_state.region_places) or st.session_state.region_places_si != si:
            with st.spinner(f"{si} 무장애 여행지 불러오는 중..."):
                st.session_state.region_places    = cached_region_random(si)
                st.session_state.region_places_si = si
        places   = st.session_state.region_places
        subtitle = f"♿ {si} 전체 무장애 여행지"
    else:
        cache_key = f"{si}_{cat}"
        if (not st.session_state.place_list) or st.session_state.place_list_key != cache_key:
            with st.spinner(f"{si} {cat} 불러오는 중..."):
                if cat == "축제":
                    st.session_state.place_list = cached_festival_latest(si)
                else:
                    st.session_state.place_list = cached_search(si, cat)
                st.session_state.place_list_key = cache_key
        places   = st.session_state.place_list
        subtitle = f"♿ {si} 무장애 {cat}"

    if not places or (len(places) == 1 and "message" in places[0]):
        st.warning(f"{si} 지역에서 해당 정보를 찾지 못했습니다.")
        return

    # ── 페이지네이션 설정 ─────────────────────────────────────────────────────
    total       = len(places)
    page        = min(st.session_state.page, max(0, (total - 1) // PAGE_SIZE))
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page_places = places[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

    st.markdown(
        f'<p style="font-size:13px;font-weight:600;color:#333;margin:4px 0 14px">'
        f'{subtitle} <span style="color:#aaa;font-weight:400">· 총 {total}개</span></p>',
        unsafe_allow_html=True,
    )

    # ── 2열 카드 그리드 ───────────────────────────────────────────────────────
    _render_card_grid(page_places, key_prefix=f"list_{page}", cols=2)

    # ── 페이지네이션 ──────────────────────────────────────────────────────────
    if total_pages > 1:
        p_cols = st.columns([1, 4, 1])
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
    # ── 헤더 ──────────────────────────────────────────────────────────────────
    st.markdown(
        '<h2 style="text-align:center;font-size:clamp(17px,4.5vw,21px);font-weight:800;margin-bottom:18px">'
        '♿ 무장애 여행지 추천</h2>',
        unsafe_allow_html=True,
    )

    # ── 지역 선택 버튼 ─────────────────────────────────────────────────────────
    s_col, n_col = st.columns([5, 1], gap="small")
    with s_col:
        if st.button("📍  지역선택  ›", key="open_modal", use_container_width=True):
            region_modal()
    with n_col:
        st.button("✈️\n내주변", key="nearby", use_container_width=True)

    # ── 최근 선택 지역 ──────────────────────────────────────────────────────────
    if st.session_state.recents:
        st.markdown('<p style="font-size:12px;color:#aaa;margin:10px 0 6px">최근 선택 지역</p>', unsafe_allow_html=True)
        chip_cols = st.columns(len(st.session_state.recents), gap="small")
        for i, r in enumerate(st.session_state.recents):
            with chip_cols[i]:
                st.markdown('<div class="chip-wrap">', unsafe_allow_html=True)
                if st.button(f"{r} ×", key=f"recent_{i}"):
                    st.session_state.recents.pop(i)
                    st.rerun()
                st.markdown('</div>', unsafe_allow_html=True)

    # ── 전국 카테고리 탐색 ──────────────────────────────────────────────────────
    st.markdown('<hr class="divider"/>', unsafe_allow_html=True)
    st.markdown(
        '<p style="font-size:14px;font-weight:700;margin:6px 0 14px">🔍 카테고리로 둘러보기</p>',
        unsafe_allow_html=True,
    )

    cat_cols = st.columns(5, gap="small")
    for i, (emoji, label) in enumerate(CATEGORIES):
        with cat_cols[i]:
            is_active = st.session_state.random_category == label
            css = "cat-btn active" if is_active else "cat-btn"
            st.markdown(f'<div class="{css}">', unsafe_allow_html=True)
            if st.button(emoji, key=f"rnd_cat_{label}"):
                with st.spinner(f"전국 {label} 불러오는 중..."):
                    st.session_state.random_category = label
                    if label == "축제":
                        st.session_state.random_places = cached_random_festivals(count=4)
                    else:
                        st.session_state.random_places = tour_api.search_random_places(label, count=4)
                st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
            color  = "#4A90E2" if is_active else "#555"
            weight = "700" if is_active else "400"
            st.markdown(
                f'<p style="text-align:center;font-size:clamp(10px,2.2vw,12px);'
                f'margin:-2px 0 10px;color:{color};font-weight:{weight}">{label}</p>',
                unsafe_allow_html=True,
            )

    # 첫 접속 시 관광지 자동 로드
    if not st.session_state.random_places and st.session_state.random_category is None:
        st.session_state.random_category = "관광지"
        with st.spinner("전국 관광지 불러오는 중..."):
            st.session_state.random_places = tour_api.search_random_places("관광지", count=4)

    rnd_places = st.session_state.random_places
    if rnd_places:
        rnd_cat = st.session_state.random_category or ""
        st.markdown(
            f'<p style="font-size:13px;color:#888;margin:4px 0 10px">♿ 전국 무장애 {rnd_cat} 추천</p>',
            unsafe_allow_html=True,
        )
        if rnd_cat == "축제":
            _render_festival_cards(rnd_places)
        else:
            _render_card_grid(rnd_places, key_prefix="rnd", cols=2, compact=True)

    # ── 무장애 축제 배너 (네이버 최신 검색) ─────────────────────────────────────
    st.markdown('<hr class="divider"/>', unsafe_allow_html=True)
    st.markdown('<p style="font-size:14px;font-weight:700;margin:6px 0 12px">🎉 최신 무장애 축제 소식</p>', unsafe_allow_html=True)

    if not st.session_state.banner_festivals:
        with st.spinner("최신 축제 정보 불러오는 중..."):
            st.session_state.banner_festivals = cached_naver_festivals()

    banners = st.session_state.banner_festivals
    idx     = st.session_state.banner_idx

    if banners:
        visible = banners[idx : idx + 2]
        b_cols  = st.columns(len(visible), gap="small")
        for j, b in enumerate(visible):
            with b_cols[j]:
                title    = b.get("title", "무장애 축제")
                snippet  = b.get("snippet", "")
                raw_date = b.get("date", "")
                link     = b.get("link", "#")
                source   = b.get("source", "")

                date_str = ""
                if raw_date:
                    if len(raw_date) == 8 and raw_date.isdigit():
                        date_str = f"{raw_date[:4]}.{raw_date[4:6]}.{raw_date[6:]}"
                    else:
                        try:
                            from email.utils import parsedate
                            parsed = parsedate(raw_date)
                            if parsed:
                                date_str = f"{parsed[0]}.{parsed[1]:02d}.{parsed[2]:02d}"
                        except Exception:
                            date_str = raw_date[:10]

                source_label  = "📰 뉴스" if source == "news" else "📝 블로그"
                snippet_short = snippet[:55] + "…" if len(snippet) > 55 else snippet

                st.markdown(f"""
                <a href="{link}" target="_blank" style="text-decoration:none">
                <div style="border-radius:16px;border:1.5px solid #e8e8e8;background:white;
                            padding:14px 16px;min-height:120px;cursor:pointer;
                            box-shadow:0 2px 10px rgba(0,0,0,0.07)">
                    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">
                        <span style="background:#EBF4FF;color:#4A90E2;font-size:10px;font-weight:700;
                                     padding:2px 8px;border-radius:4px">{source_label}</span>
                        <span style="font-size:10px;color:#bbb">{date_str}</span>
                    </div>
                    <p style="font-size:clamp(12px,2.5vw,13px);font-weight:700;color:#111;
                               margin:0 0 6px;line-height:1.45;
                               display:-webkit-box;-webkit-line-clamp:2;
                               -webkit-box-orient:vertical;overflow:hidden">{title}</p>
                    <p style="font-size:11px;color:#888;margin:0;line-height:1.4">{snippet_short}</p>
                </div>
                </a>""", unsafe_allow_html=True)

        arr_l, _, arr_r = st.columns([1, 6, 1])
        with arr_l:
            if idx > 0 and st.button("‹", key="prev_b"):
                st.session_state.banner_idx -= 1
                st.rerun()
        with arr_r:
            if idx < len(banners) - 2 and st.button("›", key="next_b"):
                st.session_state.banner_idx += 1
                st.rerun()
    else:
        st.caption("현재 무장애 축제 소식을 불러오지 못했습니다.")


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
