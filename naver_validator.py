"""
네이버 검색 API 기반 시설 접근성 자동 검증 모듈
- 블로그·지식iN 다중 쿼리 자동 수집
- 규칙 기반 경고 키워드 즉시 탐지
- GPT-4o 접근성 수치 추론 (테이블 높이·통로폭·단차)
- GPT-4o Vision 시설 사진 분석
"""

import os
import re
import json
import requests
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
NAVER_CLIENT_ID     = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")

# ── 규칙 기반 경고 사전 ───────────────────────────────────────────────────────

# 즉각 🔴 경고 — 진입·이동 자체를 막는 키워드
HARD_WARNINGS: dict[str, list[str]] = {
    "🔴 입구/진입 장애물": [
        "입구 계단", "입구에 계단", "계단이 있어요", "계단이 있습니다",
        "문턱이 있", "문턱 있어", "턱이 있어", "경사로 없어", "경사로가 없",
        "휠체어 이용 불가", "진입 불가", "진입이 안", "들어가기 어려",
        "들어갈 수 없", "휠체어는 안", "휠체어가 안 들어", "휠체어 못 들어",
    ],
    "🔴 통로 협소": [
        "좁아서 휠체어", "통로가 좁아", "좁은 통로", "비좁아서 휠체어",
        "지나가기 힘들", "휠체어 지나가기", "휠체어 통과 불가",
    ],
    "🔴 승강 설비 문제": [
        "엘리베이터 고장", "엘리베이터가 고장", "리프트 고장", "승강기 고장",
        "엘리베이터 없어요", "엘리베이터가 없어", "엘리베이터 없습니다",
        "엘리베이터 점검 중", "계단밖에 없어", "계단만 있어요",
    ],
    "🔴 화장실 이용 불가": [
        "장애인 화장실 없", "장애인 화장실이 없", "화장실 이용 불가",
        "휠체어 화장실 없",
    ],
}

# 🟡 주의 — 불편하지만 이용 가능, 수치 추론이 필요한 키워드
SOFT_WARNINGS: dict[str, dict] = {
    "🟡 좌식 구조 (테이블 높이 ~30cm)": {
        "keywords": ["좌식", "방석에 앉", "바닥에 앉아", "다다미", "방석 깔고", "바닥 좌석", "바닥에 방석"],
        "inference": "좌식 구조 추정 → 테이블 상판 높이 약 30cm, 휠체어 기준(70cm↑) 미달 🔴",
        "table_height_est_cm": 30,
    },
    "🟡 스탠딩 테이블": {
        "keywords": ["서서 먹어", "스탠딩 테이블", "스탠딩으로", "서서 드시", "서서 이용", "서서 먹는"],
        "inference": "스탠딩 테이블 구조 → 휠체어·보행 보조기 이용자 착석 불가 🔴",
        "table_height_est_cm": 95,
    },
    "🟡 협소한 테이블 간격": {
        "keywords": ["자리가 좁아", "테이블이 좁아", "테이블 간격이 좁", "협소해서", "빽빽해서", "꽉 차 있", "여유 공간이 없"],
        "inference": "테이블 간격 협소 추정 → 통로폭 80cm 미달 가능성 🟡",
        "table_height_est_cm": None,
    },
    "🟡 엘리베이터 크기 제한": {
        "keywords": ["엘리베이터가 좁", "엘리베이터 협소", "엘리베이터가 작", "리프트 협소", "엘리베이터 작아"],
        "inference": "엘리베이터/리프트 내부 협소 → 전동 휠체어 진입 불가 가능성 🟡",
        "table_height_est_cm": None,
    },
}

# 🟢 긍정 신호
POSITIVE_SIGNALS: list[str] = [
    "휠체어 이용 가능", "휠체어 가능해요", "휠체어로 갔어요", "휠체어 가져갔",
    "경사로 있어요", "경사로가 있어", "장애인 화장실 있어", "장애인 화장실 있습니다",
    "장애인 주차 있어", "장애인 주차장 있", "장애인 전용 주차", "장애인 주차 가능",
    "장애인 주차구역", "장애인 주차 구역", "장애인 주차칸", "장애인 주차공간",
    "장애인 주차 공간", "장애인 주차존", "장애인 주차 존",
    "자동문이에요", "넓은 통로", "통로가 넓어", "접근성 좋아요", "무장애",
    "휠체어 친화적", "배리어프리",
]


# ── 내부 유틸 ─────────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _naver_get(endpoint: str, query: str, display: int = 10,
               sort: str = "date") -> list[dict]:
    """Naver Search API 공통 호출 (blog / kin / news)"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []
    try:
        resp = requests.get(
            f"https://openapi.naver.com/v1/search/{endpoint}.json",
            headers={
                "X-Naver-Client-Id":     NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            params={"query": query, "display": display, "sort": sort},
            timeout=6,
        )
        if resp.status_code == 200:
            return resp.json().get("items", [])
    except Exception:
        pass
    return []


# ── 수집 함수 ─────────────────────────────────────────────────────────────────

def search_blogs(facility_name: str, location_hint: str = "",
                 max_per_query: int = 10, category: str = "") -> list[dict]:
    """접근성 관점별 다중 쿼리로 네이버 블로그 수집"""
    short_hint = " ".join(location_hint.split()[:2]) if location_hint else ""
    base = f"{short_hint} {facility_name}".strip()

    # (query, sort) — 핵심 쿼리는 관련도순(sim) + 날짜순(date) 병행
    query_specs: list[tuple[str, str]] = [
        (f"{base} 휠체어",                   "sim"),
        (f"{base} 휠체어",                   "date"),
        (f"{base} 장애인 이용",               "sim"),
        (f"{facility_name} 장애인 주차장",    "sim"),
        (f"{facility_name} 장애인 화장실",    "sim"),
        (f"{facility_name} 장애인 편의시설",  "sim"),
        (f"{base} 유모차",                   "sim"),
        (f"{base} 문턱 경사로",               "sim"),
        (f"{base} 접근성 후기",               "date"),
        (f"{facility_name} 배리어프리",       "sim"),
        (f"{facility_name} 접근성",          "date"),
    ]

    if category == "숙박":
        query_specs += [
            (f"{facility_name} 장애인 객실",   "sim"),
            (f"{facility_name} 엘리베이터",    "sim"),
            (f"{facility_name} 무장애",        "sim"),
            (f"{facility_name} 장애인 편의",   "sim"),
        ]
    elif category == "음식점":
        query_specs += [
            (f"{facility_name} 휠체어 입장",   "sim"),
            (f"{facility_name} 단차",          "sim"),
            (f"{facility_name} 문턱",          "sim"),
            (f"{base} 입구 계단",              "sim"),
        ]
    elif category == "문화시설":
        query_specs += [
            (f"{facility_name} 장애인 관람",   "sim"),
            (f"{facility_name} 엘리베이터",    "sim"),
            (f"{facility_name} 휠체어 관람",   "sim"),
        ]
    elif category == "관광지":
        query_specs += [
            (f"{facility_name} 휠체어 탐방",   "sim"),
            (f"{facility_name} 무장애 탐방",   "sim"),
        ]

    results, seen = [], set()
    for q, sort in query_specs:
        for item in _naver_get("blog", q, max_per_query, sort=sort):
            link = item.get("link", "")
            if link in seen:
                continue
            seen.add(link)
            results.append({
                "source":   "blog",
                "query":    q,
                "date":     item.get("postdate", ""),
                "title":    _strip_html(item.get("title", "")),
                "snippet":  _strip_html(item.get("description", "")),
                "link":     link,
                "blogger":  item.get("bloggername", ""),
            })
    return results


def search_kin(facility_name: str, location_hint: str = "",
               max_results: int = 5, category: str = "") -> list[dict]:
    """네이버 지식iN에서 접근성 Q&A 수집"""
    short_hint = " ".join(location_hint.split()[:2]) if location_hint else ""
    base = f"{short_hint} {facility_name}".strip()
    queries = [
        f"{base} 휠체어 이용 가능한가요",
        f"{base} 장애인 주차 가능한가요",
        f"{base} 장애인 접근 가능",
    ]
    if category == "숙박":
        queries += [
            f"{facility_name} 장애인 이용 가능한가요",
            f"{facility_name} 배리어프리 객실 있나요",
            f"{facility_name} 엘리베이터 있나요",
        ]

    results, seen = [], set()
    for q in queries:
        for item in _naver_get("kin", q, max_results):
            link = item.get("link", "")
            if link in seen:
                continue
            seen.add(link)
            results.append({
                "source":  "kin",
                "query":   q,
                "date":    "",
                "title":   _strip_html(item.get("title", "")),
                "snippet": _strip_html(item.get("description", "")),
                "link":    link,
            })
    return results


def search_news(facility_name: str, location_hint: str = "",
                max_per_query: int = 5) -> list[dict]:
    """네이버 뉴스에서 접근성 관련 기사 수집"""
    short_hint = " ".join(location_hint.split()[:2]) if location_hint else ""
    base = f"{short_hint} {facility_name}".strip()
    queries = [
        (f"{facility_name} 배리어프리",      "sim"),
        (f"{facility_name} 무장애",          "sim"),
        (f"{base} 장애인 접근성",             "sim"),
        (f"{facility_name} 휠체어 접근",     "date"),
    ]
    results, seen = [], set()
    for q, sort in queries:
        for item in _naver_get("news", q, max_per_query, sort=sort):
            link = item.get("link", "") or item.get("originallink", "")
            if not link or link in seen:
                continue
            seen.add(link)
            results.append({
                "source":  "news",
                "query":   q,
                "date":    item.get("pubDate", ""),
                "title":   _strip_html(item.get("title", "")),
                "snippet": _strip_html(item.get("description", "")),
                "link":    link,
            })
    return results


# ── 탐지 함수 ─────────────────────────────────────────────────────────────────

def detect_warnings(texts: list[dict]) -> list[dict]:
    """규칙 기반 경고·주의 키워드 탐지 (hard + soft)"""
    found = []
    for item in texts:
        full = (item.get("title", "") + " "
                + (item.get("full_content", "") or item.get("snippet", "")))

        for category, keywords in HARD_WARNINGS.items():
            for kw in keywords:
                if kw in full:
                    found.append({
                        "severity":  "🔴 위험",
                        "category":  category,
                        "keyword":   kw,
                        "excerpt":   item.get("snippet", "")[:160],
                        "date":      item.get("date", ""),
                        "source":    item.get("source", ""),
                        "link":      item.get("link", ""),
                    })
                    break  # 카테고리당 첫 번째 키워드 히트만

        for category, info in SOFT_WARNINGS.items():
            for kw in info["keywords"]:
                if kw in full:
                    found.append({
                        "severity":         "🟡 주의",
                        "category":         category,
                        "keyword":          kw,
                        "excerpt":          item.get("snippet", "")[:160],
                        "inference":        info["inference"],
                        "table_height_est": info.get("table_height_est_cm"),
                        "date":             item.get("date", ""),
                        "source":           item.get("source", ""),
                        "link":             item.get("link", ""),
                    })
                    break
    return found


def detect_positives(texts: list[dict]) -> list[str]:
    """긍정 접근성 신호 탐지"""
    found = set()
    for item in texts:
        full = (item.get("title", "") + " "
                + (item.get("full_content", "") or item.get("snippet", "")))
        for kw in POSITIVE_SIGNALS:
            if kw in full:
                found.add(kw)
    return sorted(found)


# ── GPT 추론 ──────────────────────────────────────────────────────────────────

def infer_with_gpt(facility_name: str, texts: list[dict],
                   official_info: dict = None,
                   rag_chunks: list[dict] = None,
                   category: str = "",
                   keyword_warnings: list = None) -> dict:
    """GPT-4o로 수집 텍스트에서 접근성 수치 및 신호 추론.
    리뷰가 없어도 시설명·공식정보 기반 지식 추론을 수행한다."""
    official_str = json.dumps(official_info or {}, ensure_ascii=False)

    if texts:
        block = "\n\n".join(
            f"[{t.get('date','날짜미상')} / {t.get('source','')}]\n"
            f"제목: {t.get('title','')}\n"
            f"내용: {t.get('full_content','') or t.get('snippet','')}"
            for t in texts[:25]
        )
        data_section = f"""아래는 네이버 블로그·지식iN에서 수집한 실제 방문자 텍스트입니다:
═══════════════════════════════════════
{block}
═══════════════════════════════════════
【중요】모든 사실적 주장은 위 텍스트에서 직접 발견한 내용만 evidence로 인용하세요.
위 텍스트에 언급이 없는 항목은 수치를 임의 추정하지 말고 estimated_height_cm 등을 null로 두고,
inference_note에 "데이터 미발견"이라고 기재하세요.
evidence 배열에는 반드시 위 텍스트의 원문 구절을 그대로 복사하여 넣으세요 (paraphrase 금지)."""
    else:
        data_section = """⚠ 네이버 리뷰 데이터가 수집되지 않았습니다.
시설명·공식정보·시설 유형에 대한 전문 지식으로 추론하되,
evidence는 반드시 빈 배열 []로 두고 inference_note에 "지식 기반 추론: (근거)"를 기재하세요.
수치(테이블 높이·통로폭 등)는 리뷰 원문 없이 추정한 경우 estimated_height_cm 등을 null로 두세요."""

    # ── RAG 사전 수집 청크 섹션 ──────────────────────────────────────────────
    rag_section = ""
    if rag_chunks:
        rag_block = "\n\n".join(
            f"[{c.get('title', c.get('name', ''))}]\n{c.get('content', c.get('text', ''))}"
            for c in rag_chunks
        )
        rag_section = f"""

[사전 수집된 접근성 정보 (RAG — Vector DB)]
───────────────────────────────────────
{rag_block}
───────────────────────────────────────
위 RAG 정보는 사전에 수집·정제된 신뢰도 높은 데이터입니다.
【중요】RAG 데이터에서 언급된 사실은 evidence 배열에 원문을 그대로 인용하세요.
RAG 데이터와 실시간 리뷰가 상충할 경우 양쪽 근거를 모두 반영하고 conflicts_with_official에 기재하세요."""

    # ── 키워드 경고 검증 섹션 ────────────────────────────────────────────────
    keyword_section = ""
    if keyword_warnings:
        kw_lines = "\n".join(
            f'- [{w.get("severity","")}] {w.get("category","")} '
            f'(키워드: "{w.get("keyword","")}", 스니펫: "{w.get("excerpt","")[:120]}")'
            for w in keyword_warnings
        )
        keyword_section = f"""

[규칙 기반 키워드 경고 — 오탐 검증 필요]
───────────────────────────────────────
{kw_lines}
───────────────────────────────────────
위 경고는 텍스트에서 특정 키워드가 자동 탐지된 결과입니다.
각 경고가 실제 이 시설({facility_name})의 접근성 문제를 정확히 설명하는지 판단하세요.
다른 장소 언급, 가정문, 과거 개선 전 상태, 부정문("계단이 없다") 등 오탐으로 판단되면
false_positive_warnings 배열에 카테고리와 이유를 기재하세요."""

    category_context = _CATEGORY_CONTEXT.get(category, "")

    prompt = f"""당신은 교통약자 시설 접근성 분석 전문가입니다.
【핵심 원칙】evidence 배열에는 반드시 수집 데이터(블로그·지식iN·RAG)에서 직접 발견한 원문만 인용하세요.
수집 데이터에 언급이 없는 사실은 evidence를 []로 두고 inference_note에 추론 근거를 명시하세요.
available(true/false)의 경우 법적 의무 기준으로 추론 가능한 항목은 추론해도 되지만,
evidence는 수집 데이터 인용만 허용하고, 추론 근거는 inference_note에만 기재하세요.
특히 accessible_parking·accessible_restroom·elevator는 리뷰 언급이 없어도
아래 법적 기준으로 available 여부를 추론하세요:
- 한국 「장애인·노인·임산부 등의 편의증진 보장에 관한 법률」 상 공공 관광지·해수욕장·문화시설은
  장애인 전용 주차구역, 장애인 화장실, 경사로 설치가 의무화되어 있습니다.
- 공식 등록 편의시설 정보에 '주차 안내'가 존재하면 장애인 주차구역도 함께 운영됩니다.
- 대규모 공공 해수욕장/관광지(수용인원 수천 명 이상)는 특별한 반증이 없는 한 available: true로 추론하세요.
{category_context}
시설명: {facility_name}
공식 등록 편의시설 정보: {official_str}

{data_section}{rag_section}{keyword_section}

{{
  "overall_risk": "🔴 위험 | 🟡 주의 | 🟢 양호",
  "confidence": "high | medium | low",
  "metrics": {{
    "entrance_step": {{
      "has_step": null,
      "estimated_height_cm": null,
      "has_ramp_alternative": null,
      "status": "🔴 | 🟡 | 🟢 | ❓",
      "evidence": ["리뷰 원문 인용"],
      "inference_note": ""
    }},
    "elevator": {{
      "available": null,
      "operational": null,
      "status": "🔴 | 🟡 | 🟢 | ❓",
      "evidence": ["리뷰 원문 인용"],
      "inference_note": ""
    }},
    "accessible_parking": {{
      "available": null,
      "status": "🔴 | 🟡 | 🟢 | ❓",
      "evidence": ["리뷰 원문 인용"],
      "inference_note": ""
    }},
    "accessible_restroom": {{
      "available": null,
      "status": "🔴 | 🟡 | 🟢 | ❓",
      "evidence": ["리뷰 원문 인용"],
      "inference_note": ""
    }}
  }},
  "conflicts_with_official": [
    {{
      "official_claim": "공식 정보",
      "actual_finding": "실제 리뷰 발견 내용",
      "severity": "high | medium | low",
      "evidence": "리뷰 원문"
    }}
  ],
  "false_positive_warnings": [
    {{
      "category": "오탐으로 판단된 경고 카테고리 (예: 🔴 입구/진입 장애물)",
      "reason": "오탐 이유 (예: 다른 장소 언급, 부정문, 과거 개선 전 상태 등)"
    }}
  ],
  "summary": "2~3문장 종합 평가"
}}"""

    try:
        resp = _client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2200,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content.strip())
    except json.JSONDecodeError:
        return {"raw": resp.choices[0].message.content.strip()}
    except Exception as e:
        return {"error": f"GPT 추론 실패: {str(e)}"}


def analyze_images(image_urls: list[str], facility_name: str) -> dict:
    """GPT-4o Vision으로 시설 사진 접근성 분석"""
    if not image_urls:
        return {}

    content: list = [{
        "type": "text",
        "text": f"""교통약자 접근성 전문가로서 '{facility_name}' 시설 사진을 분석하세요.
휠체어 기준: 입구 단차 0cm, 통로폭 ≥80cm, 테이블 높이 70~75cm

아래 JSON으로 응답하세요:
{{
  "entrance": {{
    "step_detected": true/false,
    "step_height_cm_est": null,
    "ramp_detected": true/false,
    "door_type": "자동문 | 수동문 | 회전문 | 미확인",
    "notes": ""
  }},
  "interior": {{
    "table_type": "입식 | 좌식 | 스탠딩 | 혼합 | 미확인",
    "table_height_cm_est": null,
    "aisle_width_cm_est": null,
    "floor_hazard": false,
    "notes": ""
  }},
  "obstacles": ["탐지된 장애물 목록"],
  "facilities": ["탐지된 편의시설 목록"],
  "overall_risk": "🔴위험 | 🟡주의 | 🟢양호",
  "confidence": "high | medium | low"
}}""",
    }]

    for url in image_urls[:4]:
        content.append({
            "type": "image_url",
            "image_url": {"url": url, "detail": "high"},
        })

    try:
        resp = _client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": content}],
            max_tokens=1200,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content.strip())
    except Exception as e:
        return {"error": f"Vision 분석 실패: {str(e)}"}


# ── 축제 검색 함수 ────────────────────────────────────────────────────────────

def search_barrier_free_festivals(area: str = "", display: int = 10) -> list[dict]:
    """
    네이버 뉴스·블로그에서 현재 연도 기준 최신 무장애 축제를 실시간 검색.
    date 순 정렬로 가장 최근 결과를 우선 반환.

    Args:
        area: 지역 필터 (예: "서울", "부산"). 빈 문자열이면 전국.
        display: 쿼리당 최대 결과 수
    Returns: [{title, date, link, source, snippet}, ...]
    """
    from datetime import date
    year = date.today().year
    region = f"{area} " if area else ""

    # 연도 없이 검색 → sort=date 로 최신 기사가 자동으로 상위 노출
    queries = [
        f"{region}무장애 축제",
        f"{region}배리어프리 축제",
        f"{region}장애인 축제",
        f"{region}동행 축제",
        f"{region}무장애 행사",
        f"{region}배리어프리 행사",
        f"{region}장애인 문화 행사",
    ]

    results, seen = [], set()
    # news 우선(최신성), blog 보완
    for endpoint in ("news", "blog"):
        for q in queries:
            for item in _naver_get(endpoint, q, display):
                link = item.get("link", "")
                if link in seen:
                    continue
                seen.add(link)
                raw_date = item.get("pubDate", "") or item.get("postdate", "")
                results.append({
                    "title":   _strip_html(item.get("title", "")),
                    "snippet": _strip_html(item.get("description", "")),
                    "date":    raw_date,
                    "link":    link,
                    "source":  endpoint,
                })

    # 날짜 내림차순 정렬 후 현재 연도 결과 우선 노출
    results.sort(key=lambda x: x.get("date", ""), reverse=True)
    current_year_results = [r for r in results if str(year) in r.get("date", "") or str(year) in r.get("title", "") or str(year) in r.get("snippet", "")]
    other_results = [r for r in results if r not in current_year_results]
    return (current_year_results + other_results)[:30]


def fetch_og_image(url: str) -> str:
    """기사/블로그 URL에서 og:image 메타태그 이미지 URL 추출. 실패 시 빈 문자열 반환."""
    if not url:
        return ""
    try:
        resp = requests.get(
            url,
            timeout=4,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return ""
        html = resp.text
        # property="og:image" content="..."
        m = re.search(r'property=["\']og:image["\']\s+content=["\'](https?://[^"\'>\s]+)', html)
        if not m:
            # content="..." property="og:image"
            m = re.search(r'content=["\'](https?://[^"\'>\s]+)["\']\s+property=["\']og:image["\']', html)
        if not m:
            # name="og:image"
            m = re.search(r'name=["\']og:image["\']\s+content=["\'](https?://[^"\'>\s]+)', html)
        return m.group(1) if m else ""
    except Exception:
        return ""


def _naver_thumb_to_original(thumb_url: str) -> str:
    """네이버 프록시 썸네일 URL(search.pstatic.net)에서 원본 이미지 URL 추출."""
    if not thumb_url:
        return thumb_url
    if "search.pstatic.net" in thumb_url:
        from urllib.parse import urlparse, parse_qs, unquote
        qs = parse_qs(urlparse(thumb_url).query)
        src = qs.get("src", [""])[0]
        if src:
            return unquote(src)
    return thumb_url


def search_place_images(name: str, address: str = "", count: int = 3) -> list:
    """네이버 이미지 검색으로 장소 사진 원본 URL 목록 반환."""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []
    query = f"{name} {address[:30]}".strip() if address else name
    try:
        resp = requests.get(
            "https://openapi.naver.com/v1/search/image.json",
            headers={
                "X-Naver-Client-Id": NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            params={"query": query, "display": min(count * 3, 20), "sort": "sim", "filter": "large"},
            timeout=5,
        )
        resp.raise_for_status()
        items = resp.json().get("items", [])
        urls = []
        for item in items:
            thumb = item.get("thumbnail", "")
            original = _naver_thumb_to_original(thumb)
            if original and original.startswith("http") and original not in urls:
                urls.append(original)
            if len(urls) >= count:
                break
        return urls
    except Exception:
        return []


def fetch_blog_content(url: str, max_chars: int = 3000, timeout: int = 6) -> str:
    """블로그/뉴스 URL에서 본문 텍스트 추출 (최대 max_chars자). 실패 시 빈 문자열."""
    if not url:
        return ""
    try:
        resp = requests.get(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            allow_redirects=True,
        )
        if resp.status_code != 200:
            return ""
        html = resp.text
        # script / style 블록 제거
        html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.DOTALL | re.IGNORECASE)
        # HTML 태그 제거
        text = re.sub(r"<[^>]+>", " ", html)
        # 연속 공백·개행 정리
        text = re.sub(r"[ \t]+", " ", text)
        text = re.sub(r"\n{3,}", "\n\n", text)
        # 짧은 줄(메뉴/버튼 텍스트) 제거
        lines = [l.strip() for l in text.splitlines() if len(l.strip()) > 20]
        cleaned = "\n".join(lines)
        return cleaned[:max_chars]
    except Exception:
        return ""


# ── 숙박 전용: 공식 홈페이지 수집 ────────────────────────────────────────────

def fetch_hotel_official_content(facility_name: str) -> list[dict]:
    """
    호텔 공식 홈페이지·예약 사이트에서 접근성·시설 안내 페이지 본문 수집.
    블로그 API 상위 결과(공홈·예약 사이트 포함) URL을 직접 fetch해 반환.
    """
    queries = [
        f"{facility_name} 장애인 편의시설",
        f"{facility_name} 배리어프리 시설안내",
        f"{facility_name} 접근성 안내",
    ]
    results: list[dict] = []
    seen: set = set()
    for q in queries:
        for item in _naver_get("blog", q, 5):
            link = item.get("link", "")
            if not link or link in seen:
                continue
            seen.add(link)
            content = fetch_blog_content(link, max_chars=3000, timeout=5)
            if content and len(content) > 100:
                results.append({
                    "source": "hotel_web",
                    "title":  _strip_html(item.get("title", "")),
                    "snippet": _strip_html(item.get("description", "")),
                    "full_content": content,
                    "link":  link,
                    "date":  item.get("postdate", ""),
                })
        if len(results) >= 3:
            break
    return results


def get_hotel_directions(facility_name: str, address: str = "") -> dict:
    """
    호텔 공식 홈페이지·블로그에서 오시는 길 정보를 수집 후 GPT로 구조화.
    Returns:
        {"subway": "...", "bus": "...", "car": "...", "parking": "...",
         "summary": "...", "source_url": "..."}
    """
    queries = [
        f"{facility_name} 오시는 길",
        f"{facility_name} 찾아오시는 길",
        f"{facility_name} 교통편 안내",
    ]
    texts: list[str] = []
    source_url = ""
    seen: set = set()
    for q in queries:
        for item in _naver_get("blog", q, 4):
            link = item.get("link", "")
            if not link or link in seen:
                continue
            seen.add(link)
            content = fetch_blog_content(link, max_chars=3000, timeout=5)
            if content and len(content) > 80:
                texts.append(content)
                if not source_url:
                    source_url = link
        if len(texts) >= 2:
            break

    if not texts:
        return {}

    combined = "\n\n---\n\n".join(texts[:3])
    prompt = f"""'{facility_name}' ({address}) 관련 교통·오시는 길 텍스트입니다.
아래 JSON으로 교통편 정보를 추출하세요. 없는 항목은 빈 문자열("")로 두세요.

{{
  "subway": "가장 가까운 지하철역 및 출구·도보 소요시간",
  "bus":    "버스 정류장명 및 버스 번호",
  "car":    "자동차 이용 시 주요 경로 요약",
  "parking": "주차장 안내 (장애인 주차 포함)",
  "summary": "1~2줄 요약"
}}

텍스트:
{combined[:3000]}"""

    try:
        resp = _client.chat.completions.create(
            model="gpt-4.1",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            temperature=0,
            response_format={"type": "json_object"},
        )
        result = json.loads(resp.choices[0].message.content.strip())
        result["source_url"] = source_url
        return result
    except Exception:
        return {}


# ── 카테고리별 GPT 추론 컨텍스트 ────────────────────────────────────────────

_CATEGORY_CONTEXT: dict[str, str] = {
    "숙박": """
[숙박시설 접근성 법적 의무 기준]
- 「장애인·노인·임산부 등의 편의증진 보장에 관한 법률」에 따라
  객실 30실 이상 숙박시설은 장애인 전용 객실·화장실·주차구역 설치가 의무입니다.
- 2층 이상 숙박시설(객실 10실 이상)은 엘리베이터 설치가 의무화되어 있습니다.
- '그래비티', '조선', '신라', '롯데', '하얏트', '힐튼', '메리어트', '노보텔',
  '인터컨티넨탈', 'JW', '파크하얏트', '페어몬트', '포시즌스' 등 브랜드 체인호텔은
  반드시 엘리베이터·장애인 화장실·장애인 주차가 있습니다.
- 리뷰 언급이 없어도 대형 호텔·비즈니스호텔은 elevator·accessible_restroom·accessible_parking 모두 available: true로 추론하세요.
""",
    "문화시설": """
[문화시설 접근성 법적 의무 기준]
- 공공 박물관·미술관·도서관·공연장은 장애인 화장실·엘리베이터·주차구역 설치가 의무입니다.
- 300석 이상 공공 문화시설은 반증 없는 한 elevator·accessible_restroom·accessible_parking 모두 available: true로 추론하세요.
""",
    "음식점": """
[음식점 접근성 참고]
- 영업면적 300㎡ 이상 음식점은 장애인 화장실 설치가 의무입니다.
- 건물 1층에 위치한 음식점은 엘리베이터가 해당없을 수 있습니다.
""",
}


# ── 메인 검증 함수 ────────────────────────────────────────────────────────────

def validate_accessibility(
    facility_name: str,
    address: str = "",
    official_info: dict = None,
    image_urls: list = None,
    category: str = "",
    include_sources: bool = False,
) -> dict:
    """
    네이버 수집 → 키워드 탐지 → GPT 추론 → Vision 분석 → 검증 결과 반환
    """
    location_hint = " ".join(address.split()[:3]) if address else ""

    # 1) 네이버 데이터 수집 (키 없으면 빈 리스트 — GPT 지식 추론으로 대체)
    blog_texts = search_blogs(facility_name, location_hint, category=category)
    kin_texts  = search_kin(facility_name, location_hint, category=category)
    news_texts = search_news(facility_name, location_hint)

    # 숙박 카테고리: 공식 홈페이지 추가 수집
    hotel_web_texts: list[dict] = []
    if category == "숙박":
        hotel_web_texts = fetch_hotel_official_content(facility_name)

    all_texts = blog_texts + kin_texts + news_texts + hotel_web_texts
    naver_available = bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET
                           and NAVER_CLIENT_ID != "your_naver_client_id_here")

    # 1-a) 블로그·뉴스 본문 전체 fetch — 상위 10건 (snippet만으론 분석 정확도 부족)
    fetch_targets = [t for t in blog_texts if not t.get("full_content")][:8] + \
                    [t for t in news_texts if not t.get("full_content")][:4]
    for item in fetch_targets:
        link = item.get("link", "")
        if link:
            full = fetch_blog_content(link, max_chars=3000, timeout=4)
            if full:
                item["full_content"] = full

    # 1-b) Vector DB 사전 수집 청크 조회 (Hybrid Search + Reranking)
    rag_chunks: list[dict] = []
    try:
        import vector_store as _vs
        rag_chunks = _vs.search_tour_overviews_hybrid(
            f"{facility_name} 접근성 휠체어 단차 경사로", top_k=5
        )
        if hasattr(_vs, "search_accessibility_chunks"):
            rag_chunks += _vs.search_accessibility_chunks(
                f"{facility_name} 접근성", top_k=3
            )
    except Exception:
        pass

    # 1-c) 숙박: 오시는 길 정보 비동기 수집 (접근성 분석과 병렬 실행 불가하므로 순차)
    hotel_directions: dict = {}
    if category == "숙박":
        hotel_directions = get_hotel_directions(facility_name, address)

    # 2) 규칙 기반 경고 탐지
    warnings  = detect_warnings(all_texts)
    positives = detect_positives(all_texts)

    # 3) GPT 접근성 수치 추론 (본문 + RAG 청크 + 키워드 경고 전달 → 오탐 검증)
    gpt_result = infer_with_gpt(facility_name, all_texts, official_info,
                                rag_chunks=rag_chunks or None,
                                category=category,
                                keyword_warnings=warnings or None)

    # 4) Vision 분석
    vision_result = analyze_images(image_urls or [], facility_name) if image_urls else {}

    # 5) 3-way 교차검증 후 경고 정제
    # 5-a) GPT가 오탐으로 판단한 경고 제거
    fp_categories = {
        fp.get("category", "")
        for fp in gpt_result.get("false_positive_warnings", [])
        if fp.get("category")
    }
    if fp_categories:
        warnings = [w for w in warnings if w.get("category", "") not in fp_categories]

    # 5-b) Vision ↔ entrance_step 메트릭 동기화
    vision_entrance = (vision_result or {}).get("entrance", {})
    entrance_metric = gpt_result.setdefault("metrics", {}).setdefault("entrance_step", {})

    if vision_entrance.get("step_detected") is True:
        # Vision이 단차 감지 → entrance_step을 위험으로 강제 업데이트
        entrance_metric["has_step"] = True
        entrance_metric["status"] = "🔴"
        h = vision_entrance.get("step_height_cm_est")
        if h:
            entrance_metric["estimated_height_cm"] = h
        entrance_metric.setdefault("evidence", [])
        entrance_metric["evidence"].insert(0, f"📷 사진 분석: 단차 감지" + (f" (~{h}cm)" if h else ""))
        entrance_metric["inference_note"] = "사진 분석 결과 기반"
    elif vision_entrance.get("step_detected") is False:
        # Vision이 단차 없음 → 입구단차 경고 제거
        warnings = [
            w for w in warnings
            if "입구/진입" not in w.get("category", "")
        ]

    # 5-c) 정제된 경고 + Vision 단차 기준으로 종합 위험도 확정
    has_red = any("🔴" in w.get("severity", "") for w in warnings)
    vision_step_danger = vision_entrance.get("step_detected") is True
    if has_red or vision_step_danger:
        overall_risk = "🔴 위험"
    else:
        overall_risk = gpt_result.get("overall_risk", "❓ 알 수 없음")

    result = {
        "facility_name": facility_name,
        "address": address,
        "overall_risk": overall_risk,
        "data_collected": {
            "blog_posts":        len(blog_texts),
            "blog_full_content": sum(1 for t in blog_texts if t.get("full_content")),
            "news_posts":        len(news_texts),
            "news_full_content": sum(1 for t in news_texts if t.get("full_content")),
            "kin_posts":         len(kin_texts),
            "total":             len(all_texts),
            "naver_available":   naver_available,
            "rag_chunks_used":   len(rag_chunks),
        },
        "official_info":     official_info or {},
        "hotel_directions":  hotel_directions,
        "warnings":          warnings,
        "positive_signals":  positives,
        "gpt_inference":     gpt_result,
        "vision_analysis":   vision_result,
        "top_sources": [
            {
                "title": t.get("title", ""),
                "date":  t.get("date", ""),
                "link":  t.get("link", ""),
            }
            for t in all_texts[:5]
        ],
    }
    if include_sources:
        result["_sources"] = {
            "blog_texts":  blog_texts,
            "kin_texts":   kin_texts,
            "news_texts":  news_texts,
            "all_texts":   all_texts,
            "rag_chunks":  rag_chunks,
        }
    return result
