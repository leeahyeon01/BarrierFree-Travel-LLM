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
    "경사로 있어요", "경사로가 있어", "장애인 화장실 있어", "장애인 주차 있어",
    "자동문이에요", "넓은 통로", "통로가 넓어", "접근성 좋아요", "무장애",
    "휠체어 친화적", "배리어프리",
]


# ── 내부 유틸 ─────────────────────────────────────────────────────────────────

def _strip_html(text: str) -> str:
    return re.sub(r"<[^>]+>", "", text).strip()


def _naver_get(endpoint: str, query: str, display: int = 5) -> list[dict]:
    """Naver Search API 공통 호출 (blog / kin)"""
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        return []
    try:
        resp = requests.get(
            f"https://openapi.naver.com/v1/search/{endpoint}.json",
            headers={
                "X-Naver-Client-Id":     NAVER_CLIENT_ID,
                "X-Naver-Client-Secret": NAVER_CLIENT_SECRET,
            },
            params={"query": query, "display": display, "sort": "date"},
            timeout=6,
        )
        if resp.status_code == 200:
            return resp.json().get("items", [])
    except Exception:
        pass
    return []


# ── 수집 함수 ─────────────────────────────────────────────────────────────────

def search_blogs(facility_name: str, location_hint: str = "",
                 max_per_query: int = 5) -> list[dict]:
    """접근성 관점별 다중 쿼리로 네이버 블로그 수집"""
    base = f"{location_hint} {facility_name}".strip()
    queries = [
        f"{base} 휠체어",
        f"{base} 장애인 이용",
        f"{base} 유모차",
        f"{base} 문턱 계단 경사로",
        f"{base} 테이블 높이",
        f"{base} 접근성 후기",
    ]

    results, seen = [], set()
    for q in queries:
        for item in _naver_get("blog", q, max_per_query):
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
               max_results: int = 5) -> list[dict]:
    """네이버 지식iN에서 접근성 Q&A 수집"""
    base = f"{location_hint} {facility_name}".strip()
    queries = [
        f"{base} 휠체어 이용 가능한가요",
        f"{base} 장애인 접근 가능",
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


# ── 탐지 함수 ─────────────────────────────────────────────────────────────────

def detect_warnings(texts: list[dict]) -> list[dict]:
    """규칙 기반 경고·주의 키워드 탐지 (hard + soft)"""
    found = []
    for item in texts:
        full = (item.get("title", "") + " " + item.get("snippet", ""))

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
        full = item.get("title", "") + " " + item.get("snippet", "")
        for kw in POSITIVE_SIGNALS:
            if kw in full:
                found.add(kw)
    return sorted(found)


# ── GPT 추론 ──────────────────────────────────────────────────────────────────

def infer_with_gpt(facility_name: str, texts: list[dict],
                   official_info: dict = None) -> dict:
    """GPT-4o로 수집 텍스트에서 접근성 수치 및 신호 추론.
    리뷰가 없어도 시설명·공식정보 기반 지식 추론을 수행한다."""
    official_str = json.dumps(official_info or {}, ensure_ascii=False)

    if texts:
        block = "\n\n".join(
            f"[{t.get('date','날짜미상')} / {t.get('source','')}]\n"
            f"제목: {t.get('title','')}\n내용: {t.get('snippet','')}"
            for t in texts[:25]
        )
        data_section = f"""아래는 네이버 블로그·지식iN에서 수집한 실제 방문자 텍스트입니다:
═══════════════════════════════════════
{block}
═══════════════════════════════════════
텍스트를 분석하여 접근성을 추론하세요. 직접 언급이 없어도 문맥에서 추론 가능하면 반드시 수치를 추정하고,
근거가 된 리뷰 원문을 그대로 인용하세요."""
    else:
        data_section = """⚠ 네이버 리뷰 데이터가 수집되지 않았습니다.
시설명·공식정보·시설 유형에 대한 당신의 전문 지식으로 접근성을 추론하세요.
한국의 일반적인 동종 시설 접근성 패턴, 시설 규모, 건축 연도 등을 근거로
반드시 구체적인 수치(테이블 높이·통로폭 등)를 추정해야 합니다.
추론에 직접 리뷰가 없을 경우 inference_note에 "지식 기반 추론"이라고 명시하세요.
evidence는 ["리뷰 없음 — 지식 기반 추론"]으로 기재하세요."""

    prompt = f"""당신은 교통약자 시설 접근성 분석 전문가입니다.
리뷰 데이터 유무와 관계없이 반드시 각 항목을 추론하여 구체적인 결과를 반환해야 합니다.
"알 수 없음" 또는 null을 남용하지 말고, 합리적 추론이 가능하면 수치와 근거를 제시하세요.

시설명: {facility_name}
공식 등록 편의시설 정보: {official_str}

{data_section}

{{
  "overall_risk": "🔴 위험 | 🟡 주의 | 🟢 양호",
  "confidence": "high | medium | low",
  "metrics": {{
    "table_height": {{
      "estimated_cm": null,
      "table_type": "입식 | 좌식 | 스탠딩 | 혼합 | 미확인",
      "meets_wheelchair_standard": null,
      "status": "🔴 | 🟡 | 🟢 | ❓",
      "evidence": ["리뷰 원문 인용"],
      "inference_note": "추론 과정 설명"
    }},
    "aisle_width": {{
      "estimated_cm": null,
      "meets_standard": null,
      "status": "🔴 | 🟡 | 🟢 | ❓",
      "evidence": ["리뷰 원문 인용"],
      "inference_note": ""
    }},
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
  "summary": "2~3문장 종합 평가"
}}"""

    try:
        resp = _client.chat.completions.create(
            model="gpt-4o",
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
            model="gpt-4o",
            messages=[{"role": "user", "content": content}],
            max_tokens=1200,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        return json.loads(resp.choices[0].message.content.strip())
    except Exception as e:
        return {"error": f"Vision 분석 실패: {str(e)}"}


# ── 메인 검증 함수 ────────────────────────────────────────────────────────────

def validate_accessibility(
    facility_name: str,
    address: str = "",
    official_info: dict = None,
    image_urls: list = None,
) -> dict:
    """
    네이버 수집 → 키워드 탐지 → GPT 추론 → Vision 분석 → 검증 결과 반환
    """
    location_hint = " ".join(address.split()[:3]) if address else ""

    # 1) 네이버 데이터 수집 (키 없으면 빈 리스트 — GPT 지식 추론으로 대체)
    blog_texts = search_blogs(facility_name, location_hint)
    kin_texts  = search_kin(facility_name, location_hint)
    all_texts  = blog_texts + kin_texts
    naver_available = bool(NAVER_CLIENT_ID and NAVER_CLIENT_SECRET
                           and NAVER_CLIENT_ID != "your_naver_client_id_here")

    # 2) 규칙 기반 경고 탐지
    warnings  = detect_warnings(all_texts)
    positives = detect_positives(all_texts)

    # 3) GPT 접근성 수치 추론
    gpt_result = infer_with_gpt(facility_name, all_texts, official_info)

    # 4) Vision 분석
    vision_result = analyze_images(image_urls or [], facility_name) if image_urls else {}

    # 5) 종합 위험도 (규칙 경고가 있으면 GPT 결과보다 우선)
    has_red = any("🔴" in w.get("severity", "") for w in warnings)
    overall_risk = "🔴 위험" if has_red else gpt_result.get("overall_risk", "❓ 알 수 없음")

    return {
        "facility_name": facility_name,
        "address": address,
        "overall_risk": overall_risk,
        "data_collected": {
            "blog_posts":      len(blog_texts),
            "kin_posts":       len(kin_texts),
            "total":           len(all_texts),
            "naver_available": naver_available,
        },
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
