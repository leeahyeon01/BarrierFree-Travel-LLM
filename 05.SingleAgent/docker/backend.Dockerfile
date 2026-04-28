FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스코드 복사
COPY backend/ ./backend/
COPY prompts/ ./prompts/

# FastAPI 앱 실행
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
