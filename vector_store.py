"""
Qdrant Vector DB 연결 / 저장 / 검색 모듈
- 컬렉션: tour_places (관광지), transport_info (교통 정적 데이터),
          tour_overview_chunks (GPT 청킹된 장소 개요)
- 임베딩 모델: OpenAI text-embedding-3-small (1536차원)
"""

import os
import json
import re
from dotenv import load_dotenv
from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue

try:
    from rank_bm25 import BM25Okapi
    _BM25_AVAILABLE = True
except ImportError:
    _BM25_AVAILABLE = False

load_dotenv()

QDRANT_HOST = os.getenv("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.getenv("QDRANT_PORT", "6333"))
EMBED_MODEL = "text-embedding-3-small"
EMBED_DIM = 1536

COLLECTION_TOUR = "tour_places"
COLLECTION_TRANSPORT = "transport_info"
COLLECTION_FESTIVAL = "festival_news"
COLLECTION_OVERVIEW = "tour_overview_chunks"
COLLECTION_ACCESSIBILITY = "accessibility_chunks"

_CHUNK_PROMPT = """당신은 장애인 여행 전문가입니다. 아래 제공된 [관광지 상세 개요]를 검색 시스템(RAG)에 적합한 여러 개의 의미 있는 '검색 단위(Chunk)'로 분할하세요.

[분할 규칙]
1. 한 청크당 길이는 300~500자 내외로 유지하세요.
2. 각 청크는 독립적인 의미를 가져야 하며, 검색 시 문맥을 알 수 있도록 청크 시작 부분에 장소 이름을 포함하세요.
3. 특히 '휠체어 접근성', '단차 여부', '화장실/주차 편의', '유모차 대여', '경사로' 등 무장애 여행 관련 정보는 별도의 청크로 중요하게 다루세요.
4. 결과물은 JSON 배열 형식으로만 반환하세요. 다른 텍스트는 포함하지 마세요.

[반환 형식]
[
  {{
    "title": "장소명 - 일반 정보",
    "content": "장소명은 ...에 위치하며 ...한 특징이 있습니다.",
    "keywords": ["위치", "특징", "역사"]
  }},
  {{
    "title": "장소명 - 접근성 및 편의시설",
    "content": "장소명은 입구에 휠체어 경사로가 설치되어 있으며, 장애인 전용 주차구역은...",
    "keywords": ["휠체어", "경사로", "장애인 주차장"]
  }}
]

[관광지 상세 개요]:
{overview_text}"""

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


# ── Contextual Embedding ──────────────────────────────────────────────────────

_CONTEXT_PROMPT = """\
<document>
{full_document}
</document>

다음은 위 문서에서 추출한 청크입니다:
<chunk>
{chunk_content}
</chunk>

이 청크를 검색 시스템에서 잘 찾을 수 있도록, 전체 문서 내에서 이 청크의 위치와 의미를 설명하는 \
간결한 컨텍스트를 2~3문장(한국어)으로 작성하세요.
컨텍스트만 출력하고 다른 내용은 포함하지 마세요."""


def _generate_chunk_context(full_document: str, chunk_content: str) -> str:
    """GPT로 청크의 문서 내 위치·의미 컨텍스트 생성 (Contextual Embedding 핵심)."""
    if not full_document or not chunk_content:
        return ""
    prompt = _CONTEXT_PROMPT.format(
        full_document=full_document[:4000],
        chunk_content=chunk_content[:800],
    )
    try:
        resp = _openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=200,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return ""


# ── Contextual BM25 ───────────────────────────────────────────────────────────

_bm25_cache: dict[str, dict] = {}


def _tokenize(text: str) -> list[str]:
    """한국어 BM25용 토크나이저 (공백·특수문자 분리, 2자 이상만)."""
    text = re.sub(r"[^\w가-힣a-zA-Z0-9]", " ", text)
    return [t for t in text.split() if len(t) > 1]


def _build_bm25_index(collection_name: str) -> None:
    """Qdrant 페이로드의 contextualized_text로 BM25 인덱스 빌드 후 메모리 캐시."""
    if not _BM25_AVAILABLE:
        return
    client = get_client()
    ids, payloads, corpus = [], [], []
    offset = None
    while True:
        try:
            points, next_offset = client.scroll(
                collection_name=collection_name,
                limit=1000,
                offset=offset,
                with_payload=True,
                with_vectors=False,
            )
        except Exception:
            break
        for p in points:
            ids.append(p.id)
            payloads.append(p.payload)
            # contextualized_text 우선, 없으면 text 폴백
            text = p.payload.get("contextualized_text") or p.payload.get("text", "")
            corpus.append(_tokenize(text))
        if next_offset is None:
            break
        offset = next_offset

    if corpus:
        _bm25_cache[collection_name] = {
            "index":    BM25Okapi(corpus),
            "ids":      ids,
            "payloads": payloads,
        }


def _get_bm25_index(collection_name: str) -> dict | None:
    """BM25 인덱스 반환 — 없으면 lazy build."""
    if collection_name not in _bm25_cache:
        _build_bm25_index(collection_name)
    return _bm25_cache.get(collection_name)


def invalidate_bm25_cache(collection_name: str | None = None) -> None:
    """ingest 후 BM25 캐시 무효화 (다음 검색 시 재빌드)."""
    if collection_name:
        _bm25_cache.pop(collection_name, None)
    else:
        _bm25_cache.clear()


# ── GPT 청킹 ─────────────────────────────────────────────────────────────────

def chunk_overview_with_gpt(name: str, overview_text: str) -> list[dict]:
    """장소 개요를 GPT로 의미 단위 청크 분할. 파싱 실패 시 단일 청크 반환."""
    if not overview_text or overview_text.strip() in ("정보 없음", ""):
        return [{"title": f"{name} - 일반 정보", "content": name, "keywords": [name]}]

    prompt = _CHUNK_PROMPT.format(overview_text=overview_text)
    try:
        resp = _openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0,
            max_tokens=2000,
        )
        raw = resp.choices[0].message.content.strip()
        # 마크다운 코드블록 제거
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
        chunks = json.loads(raw)
        if isinstance(chunks, list) and chunks:
            return chunks
    except Exception:
        pass
    # 폴백: 원본 텍스트를 단일 청크로
    return [{"title": f"{name} - 개요", "content": f"{name}: {overview_text}", "keywords": [name]}]


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


def store_tour_overview_chunks(doc_id_start: int, content_id: str, name: str,
                               area: str, category: str, overview: str) -> int:
    """
    장소 개요를 GPT 청킹 → Contextual Embedding → Vector DB 저장.
    각 청크에 문서 내 위치 컨텍스트를 부여한 뒤 임베딩 (Contextual Retrieval).
    저장된 청크 수 반환.
    """
    _ensure_collection(COLLECTION_OVERVIEW)
    chunks = chunk_overview_with_gpt(name, overview)
    for i, chunk in enumerate(chunks):
        title    = chunk.get("title", f"{name} - {i+1}")
        content  = chunk.get("content", "")
        keywords = chunk.get("keywords", [])

        # ── Contextual Embedding: 전체 문서 내 위치 컨텍스트 생성 ─────────────
        context = _generate_chunk_context(overview, content)
        # 컨텍스트를 청크 앞에 붙여 임베딩 — 검색 정확도 향상
        contextualized_text = (
            f"{context}\n\n{title}\n{content}" if context else f"{title}\n{content}"
        )

        vector = _embed(contextualized_text)

        get_client().upsert(
            collection_name=COLLECTION_OVERVIEW,
            points=[
                PointStruct(
                    id=doc_id_start + i,
                    vector=vector,
                    payload={
                        "content_id":          content_id,
                        "name":                name,
                        "area":                area,
                        "category":            category,
                        "title":               title,
                        "content":             content,
                        "context":             context,             # 생성된 컨텍스트
                        "contextualized_text": contextualized_text, # BM25 색인용
                        "keywords":            keywords,
                        "text":                f"{title}\n{content}",
                    },
                )
            ],
        )

    # BM25 캐시 무효화 → 다음 검색 시 자동 재빌드
    invalidate_bm25_cache(COLLECTION_OVERVIEW)
    return len(chunks)


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


def search_tour_overviews(query: str, area: str | None = None,
                          category: str | None = None, top_k: int = 5) -> list[dict]:
    """GPT 청킹된 장소 개요 컬렉션에서 Semantic 단독 검색 (하위 호환)."""
    _ensure_collection(COLLECTION_OVERVIEW)
    vector = _embed(query)
    must = []
    if area:
        must.append(FieldCondition(key="area", match=MatchValue(value=area)))
    if category:
        must.append(FieldCondition(key="category", match=MatchValue(value=category)))
    search_filter = Filter(must=must) if must else None
    hits = get_client().search(
        collection_name=COLLECTION_OVERVIEW,
        query_vector=vector,
        limit=top_k,
        query_filter=search_filter,
    )
    return [{"score": h.score, **h.payload} for h in hits]


def search_tour_overviews_hybrid(
    query: str,
    area: str | None = None,
    category: str | None = None,
    top_k: int = 5,
    sem_weight: float = 0.7,
    bm25_weight: float = 0.3,
) -> list[dict]:
    """
    Contextual Embedding + Contextual BM25 하이브리드 검색.

    1) Semantic: contextualized_text 기반 벡터 검색 (Qdrant)
    2) BM25:     contextualized_text 토큰 기반 키워드 검색 (rank-bm25)
    3) RRF(Reciprocal Rank Fusion)로 두 결과를 결합

    rank-bm25 미설치 시 Semantic 단독 검색으로 자동 폴백.
    """
    _ensure_collection(COLLECTION_OVERVIEW)
    fetch_n = top_k * 4  # RRF를 위해 넉넉하게 수집

    # ── 1) Semantic 검색 ──────────────────────────────────────────────────────
    vector = _embed(query)
    must = []
    if area:
        must.append(FieldCondition(key="area", match=MatchValue(value=area)))
    if category:
        must.append(FieldCondition(key="category", match=MatchValue(value=category)))
    search_filter = Filter(must=must) if must else None

    sem_hits = get_client().search(
        collection_name=COLLECTION_OVERVIEW,
        query_vector=vector,
        limit=fetch_n,
        query_filter=search_filter,
        with_payload=True,
    )
    sem_rank:      dict[int, int]  = {h.id: rank for rank, h in enumerate(sem_hits)}
    id_to_payload: dict[int, dict] = {h.id: h.payload for h in sem_hits}

    # ── 2) BM25 검색 ─────────────────────────────────────────────────────────
    bm25_rank: dict[int, int] = {}
    bm25_data = _get_bm25_index(COLLECTION_OVERVIEW) if _BM25_AVAILABLE else None

    if bm25_data:
        tokens = _tokenize(query)
        raw_scores = bm25_data["index"].get_scores(tokens)

        filtered: list[tuple[int, dict, float]] = []
        for pid, payload, score in zip(
            bm25_data["ids"], bm25_data["payloads"], raw_scores
        ):
            if area and payload.get("area") != area:
                continue
            if category and payload.get("category") != category:
                continue
            filtered.append((pid, payload, score))

        filtered.sort(key=lambda x: x[2], reverse=True)
        for rank, (pid, payload, _) in enumerate(filtered[:fetch_n]):
            bm25_rank[pid] = rank
            id_to_payload.setdefault(pid, payload)

    # BM25 없으면 Semantic 단독 반환
    if not bm25_rank:
        return [{"score": h.score, **h.payload} for h in sem_hits[:top_k]]

    # ── 3) RRF 융합 ───────────────────────────────────────────────────────────
    big = fetch_n + 100  # 미등장 문서 패널티 순위
    all_ids = set(sem_rank) | set(bm25_rank)
    rrf: dict[int, float] = {
        pid: (
            sem_weight  / (60 + sem_rank.get(pid,  big)) +
            bm25_weight / (60 + bm25_rank.get(pid, big))
        )
        for pid in all_ids
    }

    top_ids = sorted(rrf, key=rrf.__getitem__, reverse=True)[:top_k]
    return [
        {
            "score":         rrf[pid],
            "semantic_rank": sem_rank.get(pid),
            "bm25_rank":     bm25_rank.get(pid),
            **id_to_payload.get(pid, {}),
        }
        for pid in top_ids
    ]


def collection_counts() -> dict[str, int]:
    """각 컬렉션에 저장된 문서 수 반환"""
    client = get_client()
    result = {}
    for name in (COLLECTION_TOUR, COLLECTION_TRANSPORT, COLLECTION_FESTIVAL, COLLECTION_OVERVIEW):
        try:
            info = client.get_collection(name)
            result[name] = info.points_count
        except Exception:
            result[name] = 0
    return result
