"""장기 챔피언 AI - FastAPI 메인 서버"""
import os
import math
import logging
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from starlette.responses import FileResponse, JSONResponse
from pathlib import Path

from .orchestrator.orchestrator import JanggiOrchestrator
from .api.routes import router, set_orchestrator
from .api.websocket_handler import websocket_endpoint

logger = logging.getLogger(__name__)


def _json_safe(o, path="$"):
    """비유한 float(inf/nan)를 유한값으로 치환하여 JSON 직렬화 5xx 를 방지.

    탐색 타임아웃 등 드문 경계에서 ±inf 점수가 응답에 새어 들어가면
    표준 json.dumps 가 ValueError 를 던져 500 이 발생한다(견고성 위반).
    여기서 안전하게 치환하고, 무엇을 고쳤는지 경고 로그로 남겨 원인 추적을 돕는다.
    """
    if isinstance(o, bool):
        return o
    if isinstance(o, float):
        if math.isinf(o):
            logger.warning("Sanitized non-finite float at %s: %r -> clamp", path, o)
            return 1e9 if o > 0 else -1e9
        if math.isnan(o):
            logger.warning("Sanitized NaN at %s -> 0.0", path)
            return 0.0
        return o
    if isinstance(o, dict):
        return {k: _json_safe(v, f"{path}.{k}") for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [_json_safe(v, f"{path}[{i}]") for i, v in enumerate(o)]
    return o


class SafeJSONResponse(JSONResponse):
    """inf/nan 안전 처리 후 직렬화하는 응답 클래스."""
    def render(self, content) -> bytes:
        return super().render(_json_safe(content))


app = FastAPI(
    title="장기 챔피언 AI",
    description="웹 기반 인간 대 AI 장기 게임 프로그램",
    version="1.0.0",
    default_response_class=SafeJSONResponse,
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
        port=8007,
        reload=True,
    )
