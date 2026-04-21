"""
Qdrant Vector DB 연결 / 저장 / 검색 모듈
- 컬렉션: tour_places (관광지), transport_info (교통 정적 데이터)
- 임베딩 모델: OpenAI text-embedding-3-small (1536차원)
"""

import os
from typing import Any
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

load_dotenv()

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536

COLLECTION_TOUR = "tour_places"
COLLECTION_TRANSPORT = "transport_info"
COLLECTION_FESTIVAL = "festival_news"

_openai = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
_qdrant: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _qdrant
    if _qdrant is None:
        _qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)
    return _qdrant


def _embed(text: str) -> list[float]:
    resp = _openai.embeddings.create(model=EMBED_MODEL, input=text)
    return resp.data[0].embedding


def _ensure_collection(name: str) -> None:
    client = get_client()
    existing = [c.name for c in client.get_collections().collections]
    if name not in existing:
        client.create_collection(
            collection_name=name,
            vectors_config=VectorParams(size=EMBED_DIM, distance=Distance.COSINE),
        )


# ── 저장 ────────────────────────────────────────────────────────────────────

def store_tour_place(doc_id: int, place: dict, area_name: str) -> None:
    """관광지 1건을 Vector DB에 저장"""
    _ensure_collection(COLLECTION_TOUR)

    text = (
        f"지역: {area_name} | 카테고리: {place.get('카테고리', '')} | "
        f"이름: {place.get('이름', '')} | 주소: {place.get('주소', '')} | "
        f"전화번호: {place.get('전화번호', '')}"
    )
    vector = _embed(text)

    get_client().upsert(
        collection_name=COLLECTION_TOUR,
        points=[
            PointStruct(
                id=doc_id,
                vector=vector,
                payload={
                    "area": area_name,
                    "category": place.get("카테고리", ""),
                    "name": place.get("이름", ""),
                    "address": place.get("주소", ""),
                    "tel": place.get("전화번호", ""),
                    "content_id": place.get("content_id", ""),
                    "text": text,
                },
            )
        ],
    )


def store_transport_info(doc_id: int, region: str, info: dict) -> None:
    """장애인 콜택시 정보 1건을 Vector DB에 저장"""
    _ensure_collection(COLLECTION_TRANSPORT)

    text = (
        f"지역: {region} | 서비스: {info.get('이름', '')} | "
        f"전화: {info.get('전화', '')} | 앱: {info.get('앱', '')}"
    )
    vector = _embed(text)

    get_client().upsert(
        collection_name=COLLECTION_TRANSPORT,
        points=[
            PointStruct(
                id=doc_id,
                vector=vector,
                payload={
                    "region": region,
                    "name": info.get("이름", ""),
                    "tel": info.get("전화", ""),
                    "app": info.get("앱", ""),
                    "text": text,
                },
            )
        ],
    )


def store_festival_news(doc_id: int, item: dict) -> None:
    """네이버 수집 축제 뉴스/블로그 1건을 Vector DB에 저장"""
    _ensure_collection(COLLECTION_FESTIVAL)

    text = f"축제: {item.get('title', '')} | 내용: {item.get('snippet', '')} | 날짜: {item.get('date', '')}"
    vector = _embed(text)

    get_client().upsert(
        collection_name=COLLECTION_FESTIVAL,
        points=[
            PointStruct(
                id=doc_id,
                vector=vector,
                payload={
                    "title":   item.get("title", ""),
                    "snippet": item.get("snippet", ""),
                    "date":    item.get("date", ""),
                    "link":    item.get("link", ""),
                    "source":  item.get("source", ""),
                    "text":    text,
                },
            )
        ],
    )


# ── 검색 ────────────────────────────────────────────────────────────────────

def search_tour_places(query: str, area: str | None = None, top_k: int = 5) -> list[dict]:
    """자연어 쿼리로 관광지 검색, area 필터 선택"""
    _ensure_collection(COLLECTION_TOUR)

    vector = _embed(query)
    search_filter = None
    if area:
        search_filter = Filter(
            must=[FieldCondition(key="area", match=MatchValue(value=area))]
        )

    hits = get_client().search(
        collection_name=COLLECTION_TOUR,
        query_vector=vector,
        limit=top_k,
        query_filter=search_filter,
    )
    return [{"score": h.score, **h.payload} for h in hits]


def search_transport_info(query: str, region: str | None = None, top_k: int = 3) -> list[dict]:
    """자연어 쿼리로 교통 지원 정보 검색"""
    _ensure_collection(COLLECTION_TRANSPORT)

    vector = _embed(query)
    search_filter = None
    if region:
        search_filter = Filter(
            must=[FieldCondition(key="region", match=MatchValue(value=region))]
        )

    hits = get_client().search(
        collection_name=COLLECTION_TRANSPORT,
        query_vector=vector,
        limit=top_k,
        query_filter=search_filter,
    )
    return [{"score": h.score, **h.payload} for h in hits]


def search_festival_news(query: str, top_k: int = 5) -> list[dict]:
    """자연어 쿼리로 축제 뉴스/블로그 검색"""
    _ensure_collection(COLLECTION_FESTIVAL)
    vector = _embed(query)
    hits = get_client().search(
        collection_name=COLLECTION_FESTIVAL,
        query_vector=vector,
        limit=top_k,
    )
    return [{"score": h.score, **h.payload} for h in hits]


def collection_counts() -> dict[str, int]:
    """각 컬렉션에 저장된 문서 수 반환"""
    client = get_client()
    result = {}
    for name in (COLLECTION_TOUR, COLLECTION_TRANSPORT, COLLECTION_FESTIVAL):
        try:
            info = client.get_collection(name)
            result[name] = info.points_count
        except Exception:
            result[name] = 0
    return result
