from __future__ import annotations
import json
import tempfile
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from .orchestrator import OrchestratorAgent
from .schemas import ChatRequest, ChatResponse
from .storage import save_itinerary, list_itineraries, get_itinerary, delete_itinerary

app = FastAPI(title="배리어프리 MultiAgent API")
_orchestrator = OrchestratorAgent()


@app.post("/chat", response_model=ChatResponse)
def chat_endpoint(request: ChatRequest):
    """메인 채팅 엔드포인트. reply / complete / itinerary / validation_result 반환."""
    result = _orchestrator.run(request.message)
    if result.itinerary:
        save_itinerary(result.itinerary)
    return result


# ── 일정 CRUD ─────────────────────────────────────────────────────────────────

@app.get("/itineraries")
def list_itineraries_endpoint():
    """저장된 일정 목록 조회."""
    return {"itineraries": list_itineraries()}


@app.get("/itineraries/{itinerary_id}")
def get_itinerary_endpoint(itinerary_id: str):
    """특정 일정 조회."""
    data = get_itinerary(itinerary_id)
    if data is None:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
    return data


@app.get("/itineraries/{itinerary_id}/download")
def download_itinerary_endpoint(itinerary_id: str):
    """일정 JSON 다운로드."""
    data = get_itinerary(itinerary_id)
    if data is None:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")

    tmp = tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    )
    json.dump(data, tmp, ensure_ascii=False, indent=2)
    tmp.close()

    destination = data.get("destination", "여행")
    short_id = itinerary_id[:8]
    return FileResponse(
        path=tmp.name,
        filename=f"itinerary_{destination}_{short_id}.json",
        media_type="application/json",
    )


@app.delete("/itineraries/{itinerary_id}")
def delete_itinerary_endpoint(itinerary_id: str):
    """일정 삭제."""
    ok = delete_itinerary(itinerary_id)
    if not ok:
        raise HTTPException(status_code=404, detail="일정을 찾을 수 없습니다.")
    return {"deleted": itinerary_id}
