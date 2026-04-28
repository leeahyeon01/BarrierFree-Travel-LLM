"""
단일 RAG 진입점 — 중복 호출 방지를 위해 모든 에이전트는 여기서만 검색합니다.
Qdrant VectorStore가 없으면 스텁 데이터를 반환합니다.
"""
from __future__ import annotations
import os
import sys
from typing import List, Dict, Any

# 부모 프로젝트(04_barrier_free_chatbot)를 sys.path에 추가
_PARENT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _PARENT_DIR not in sys.path:
    sys.path.insert(0, _PARENT_DIR)

try:
    from vector_store import (
        search_tour_places,
        search_tour_overviews_hybrid,
        search_transport_info,
    )
    _HAS_VS = True
except Exception:
    _HAS_VS = False


def retrieve_places(
    destination: str,
    accessibility_needs: List[str],
    top_k: int = 10,
) -> List[Dict[str, Any]]:
    """접근성 조건에 맞는 관광지·음식점·교통 정보를 검색합니다."""
    if not _HAS_VS:
        return _stub_places(destination, accessibility_needs)

    query = f"{destination} {' '.join(accessibility_needs)} 무장애 배리어프리"
    results: List[Dict[str, Any]] = []

    try:
        tour = search_tour_overviews_hybrid(query=query, area=destination, top_k=top_k)
        results.extend(_normalize_tour(r) for r in tour)
    except Exception:
        try:
            tour = search_tour_places(query=query, area=destination, top_k=top_k)
            results.extend(_normalize_tour(r) for r in tour)
        except Exception:
            pass

    try:
        transport = search_transport_info(query=query, region=destination, top_k=3)
        results.extend(_normalize_transport(r) for r in transport)
    except Exception:
        pass

    # 이름 기준 중복 제거
    seen: set[str] = set()
    deduped = []
    for r in results:
        key = r["name"].strip()
        if key not in seen:
            seen.add(key)
            deduped.append(r)

    return deduped[:top_k] if deduped else _stub_places(destination, accessibility_needs)


def _normalize_tour(raw: dict) -> Dict[str, Any]:
    return {
        "name": raw.get("place_name") or raw.get("name") or raw.get("title", "알 수 없음"),
        "category": raw.get("category", "tourist"),
        "accessibility_summary": raw.get("accessibility_summary") or raw.get("content", ""),
        "source": raw.get("source", ""),
    }


def _normalize_transport(raw: dict) -> Dict[str, Any]:
    return {
        "name": raw.get("transport_name") or raw.get("name", "교통 정보"),
        "category": "transport",
        "accessibility_summary": raw.get("content", ""),
        "source": raw.get("source", ""),
    }


def _stub_places(destination: str, accessibility_needs: List[str]) -> List[Dict[str, Any]]:
    """VectorStore 미연결 시 개발·테스트용 샘플 데이터"""
    wheelchair = "휠체어" in accessibility_needs
    return [
        {
            "name": f"{destination} 관광지 A",
            "category": "tourist",
            "accessibility_summary": f"{'휠체어 경사로 있음, ' if wheelchair else ''}엘리베이터 운영, 장애인 화장실 완비",
            "source": "stub",
        },
        {
            "name": f"{destination} 식당 B",
            "category": "restaurant",
            "accessibility_summary": "단차 없는 출입구, 장애인 화장실 구비, 넓은 복도",
            "source": "stub",
        },
        {
            "name": f"{destination} 박물관 C",
            "category": "tourist",
            "accessibility_summary": "배리어프리 인증 관광지, 무료 휠체어 대여",
            "source": "stub",
        },
        {
            "name": f"{destination} 공원 D",
            "category": "tourist",
            "accessibility_summary": "평탄한 산책로, 휠체어 이동 가능, 유모차 대여 서비스",
            "source": "stub",
        },
        {
            "name": f"{destination} 카페 E",
            "category": "restaurant",
            "accessibility_summary": "자동문, 넓은 테이블 간격, 장애인 주차 구역 인접",
            "source": "stub",
        },
    ]
