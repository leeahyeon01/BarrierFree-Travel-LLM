from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from routers import chat, places, transport, validation

app = FastAPI(title="Barrier-Free Chatbot API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat.router,       prefix="/api/chat",       tags=["chat"])
app.include_router(places.router,     prefix="/api/places",     tags=["places"])
app.include_router(transport.router,  prefix="/api/transport",  tags=["transport"])
app.include_router(validation.router, prefix="/api/validation", tags=["validation"])


@app.get("/health")
def health():
    return {"status": "ok"}
