"""REST API 엔드포인트 정의"""
import asyncio
import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api")


# --- Request Models ---

class NewGameRequest(BaseModel):
    cho_formation: str = "내상외마"
    han_formation: str = "내상외마"
    ai_team: str = "han"
    ai_depth: int = 6
    ai_time_limit: float = 3.0

    @field_validator("ai_depth")
    @classmethod
    def validate_depth(cls, v):
        if not (1 <= v <= 30):
            raise ValueError("ai_depth must be between 1 and 30")
        return v

    @field_validator("ai_time_limit")
    @classmethod
    def validate_time_limit(cls, v):
        if not (0.1 <= v <= 60.0):
            raise ValueError("ai_time_limit must be between 0.1 and 60.0")
        return v


class MoveRequest(BaseModel):
    from_row: int
    from_col: int
    to_row: int
    to_col: int


class ValidMovesRequest(BaseModel):
    row: int
    col: int


# --- 오케스트레이터 참조 (main.py에서 주입) ---
_orchestrator = None


def set_orchestrator(orch):
    global _orchestrator
    _orchestrator = orch


def get_orchestrator():
    if _orchestrator is None:
        raise HTTPException(status_code=500, detail="Orchestrator not initialized")
    return _orchestrator


# --- Endpoints ---

@router.post("/game/new")
async def create_game(req: NewGameRequest):
    """POST /api/game/new - 새 게임 생성"""
    orch = get_orchestrator()
    state = orch.create_game(
        cho_formation=req.cho_formation,
        han_formation=req.han_formation,
        ai_team=req.ai_team,
        ai_depth=req.ai_depth,
        ai_time_limit=req.ai_time_limit,
    )
    return state


@router.post("/game/{game_id}/move")
async def make_move(game_id: str, req: MoveRequest):
    """POST /api/game/{id}/move - 수 두기 (Human)"""
    orch = get_orchestrator()

    # 인간 수 실행
    human_result = orch.human_move(game_id, req.from_row, req.from_col, req.to_row, req.to_col)
    if not human_result.get("success"):
        raise HTTPException(status_code=400, detail=human_result.get("error", "Invalid move"))

    # 게임이 종료되지 않았으면 AI 수 실행 (별도 스레드에서 CPU-집약적 탐색)
    if human_result.get("status") == "playing":
        ai_result = await asyncio.to_thread(orch.ai_move, game_id)
        return {
            "human_move": human_result,
            "ai_move": ai_result,
        }

    return {"human_move": human_result, "ai_move": None}


@router.get("/game/{game_id}/state")
async def get_game_state(game_id: str):
    """GET /api/game/{id}/state - 현재 게임 상태 조회"""
    orch = get_orchestrator()
    state = orch.get_game_state(game_id)
    if "error" in state:
        raise HTTPException(status_code=404, detail=state["error"])
    return state


@router.get("/game/{game_id}/analysis")
async def get_analysis(game_id: str):
    """GET /api/game/{id}/analysis - AI 분석 결과 조회"""
    orch = get_orchestrator()
    analysis = orch.get_analysis(game_id)
    if "error" in analysis:
        raise HTTPException(status_code=404, detail=analysis["error"])
    return analysis


@router.post("/game/{game_id}/undo")
async def undo_move(game_id: str):
    """POST /api/game/{id}/undo - 수 무르기"""
    orch = get_orchestrator()
    result = orch.undo_move(game_id)
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Cannot undo"))
    return result


@router.post("/game/{game_id}/valid-moves")
async def get_valid_moves(game_id: str, req: ValidMovesRequest):
    """POST /api/game/{id}/valid-moves - 유효 이동 위치 조회"""
    orch = get_orchestrator()
    moves = orch.get_valid_moves(game_id, req.row, req.col)
    return {"valid_moves": moves}


@router.get("/game/{game_id}/report")
async def get_report(game_id: str):
    """GET /api/game/{id}/report - 경기 보고서 (idempotent)"""
    orch = get_orchestrator()
    result = orch.get_or_create_report(game_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return result


@router.get("/stats")
async def get_stats():
    """GET /api/stats - AI 전체 통계"""
    orch = get_orchestrator()
    return orch.get_stats()
