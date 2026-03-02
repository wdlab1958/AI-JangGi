"""장기 챔피언 AI - FastAPI 메인 서버"""
import os
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from .orchestrator.orchestrator import JanggiOrchestrator
from .api.routes import router, set_orchestrator
from .api.websocket_handler import websocket_endpoint

app = FastAPI(
    title="장기 챔피언 AI",
    description="웹 기반 인간 대 AI 장기 게임 프로그램",
    version="1.0.0",
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 오케스트레이터 초기화
orchestrator = JanggiOrchestrator(
    ai_depth=int(os.environ.get("AI_DEPTH", "6")),
    ai_time_limit=float(os.environ.get("AI_TIME_LIMIT", "3.0")),
    storage_dir=os.environ.get("STORAGE_DIR", "./data/long_term"),
)
set_orchestrator(orchestrator)

# REST API 라우터 등록
app.include_router(router)


# WebSocket 엔드포인트
@app.websocket("/ws/{game_id}")
async def websocket_route(websocket: WebSocket, game_id: str):
    await websocket_endpoint(websocket, game_id, orchestrator)


# 프론트엔드 정적 파일 서빙
frontend_build = Path(__file__).parent.parent / "frontend" / "out"
if frontend_build.exists():
    app.mount("/", StaticFiles(directory=str(frontend_build), html=True), name="frontend")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "janggi-champion-ai"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )
