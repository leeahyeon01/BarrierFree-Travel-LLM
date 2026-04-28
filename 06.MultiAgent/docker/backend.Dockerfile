FROM python:3.11-slim

WORKDIR /app

COPY 06.MultiAgent/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 멀티에이전트 소스
COPY 06.MultiAgent/backend/ ./backend/
COPY 06.MultiAgent/prompts/ ./prompts/

# 부모 프로젝트 공유 모듈 (RAG, 검증, 평가)
COPY vector_store.py .
COPY naver_validator.py .
COPY eval/ ./eval/

# 일정 저장 디렉토리
RUN mkdir -p /app/data/itineraries

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
