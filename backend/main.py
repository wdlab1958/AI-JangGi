"""장기 챔피언 AI - FastAPI 메인 서버"""
import os
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse
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


@app.get("/health")
async def health():
    return {"status": "ok", "service": "janggi-champion-ai"}


# REST API 라우터 등록
app.include_router(router)


# WebSocket 엔드포인트
@app.websocket("/ws/{game_id}")
async def websocket_route(websocket: WebSocket, game_id: str):
    await websocket_endpoint(websocket, game_id, orchestrator)


# 프론트엔드 정적 파일 서빙
# mount는 모든 라우트보다 후순위이므로, _next 에셋만 mount하고
# 나머지는 catch-all 라우트로 index.html 서빙 (SPA)
frontend_build = Path(__file__).parent.parent / "frontend" / "out"
if frontend_build.exists():
    # /_next 정적 에셋 (JS, CSS, 이미지)
    next_dir = frontend_build / "_next"
    if next_dir.exists():
        app.mount("/_next", StaticFiles(directory=str(next_dir)), name="next_static")

    # favicon 등 정적 파일
    @app.get("/favicon.ico")
    async def favicon():
        fav = frontend_build / "favicon.ico"
        if fav.exists():
            return FileResponse(str(fav))

    @app.get("/favicon.svg")
    async def favicon_svg():
        fav = frontend_build / "favicon.svg"
        if fav.exists():
            return FileResponse(str(fav))

    # SPA catch-all: API/WS가 아닌 모든 요청에 index.html 반환
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # 정적 파일이 존재하면 해당 파일 반환
        file_path = frontend_build / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        # 그 외 SPA 라우팅 → index.html
        return FileResponse(str(frontend_build / "index.html"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
    )
