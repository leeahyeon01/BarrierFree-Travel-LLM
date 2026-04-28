from fastapi import FastAPI
from pydantic import BaseModel
from .agent import run_agent

app = FastAPI(title="Barrier-Free Single Agent API")

class ChatRequest(BaseModel):
    message: str

@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    """프론트엔드(Streamlit) 등에서 호출하는 메인 API 엔드포인트"""
    result = run_agent(request.message)
    return {"reply": result}
