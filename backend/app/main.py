from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import chat, sandbox, vapi

settings = get_settings()

app = FastAPI(title="Ava - Dropout Recovery Voice Agent", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin, "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(vapi.router)
app.include_router(sandbox.router)
app.include_router(chat.router)


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
