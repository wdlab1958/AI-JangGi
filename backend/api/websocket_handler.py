"""WebSocket 이벤트 핸들러

이벤트:
- game:move (Client → Server): {from, to, piece_type}
- game:ai_move (Server → Client): {from, to, analysis, win_probability}
- game:state_update (Server → Client): {board_state, turn, captured_pieces}
- game:analysis_update (Server → Client): {agent_id, analysis_result, confidence}
- game:janggun (Server → Client): {check_type, threatening_pieces}
- game:end (Server → Client): {winner, reason, final_report}
"""
import json
import asyncio
import logging
from fastapi import WebSocket, WebSocketDisconnect
from typing import Optional

logger = logging.getLogger(__name__)


class ConnectionManager:
    """WebSocket 연결 관리자"""

    def __init__(self):
        self.active_connections: dict[str, list[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, game_id: str):
        await websocket.accept()
        if game_id not in self.active_connections:
            self.active_connections[game_id] = []
        self.active_connections[game_id].append(websocket)

    def disconnect(self, websocket: WebSocket, game_id: str):
        if game_id in self.active_connections:
            if websocket in self.active_connections[game_id]:
                self.active_connections[game_id].remove(websocket)
            if not self.active_connections[game_id]:
                del self.active_connections[game_id]

    async def send_to_game(self, game_id: str, event: str, data: dict):
        """게임 참가자에게 이벤트 전송"""
        message = json.dumps({"event": event, "data": data}, default=str)
        if game_id in self.active_connections:
            disconnected = []
            for ws in self.active_connections[game_id]:
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.append(ws)
            for ws in disconnected:
                self.disconnect(ws, game_id)


manager = ConnectionManager()


async def websocket_endpoint(websocket: WebSocket, game_id: str, orchestrator):
    """WebSocket 엔드포인트 핸들러"""
    await manager.connect(websocket, game_id)

    try:
        # 초기 상태 전송
        state = orchestrator.get_game_state(game_id)
        await manager.send_to_game(game_id, "game:state_update", state)

        while True:
            data = await websocket.receive_text()
            message = json.loads(data)
            event = message.get("event", "")
            payload = message.get("data", {})

            if event == "game:move":
                await handle_move(game_id, payload, orchestrator)

            elif event == "game:valid_moves":
                row = payload.get("row", 0)
                col = payload.get("col", 0)
                moves = orchestrator.get_valid_moves(game_id, row, col)
                await websocket.send_text(json.dumps({
                    "event": "game:valid_moves_response",
                    "data": {"valid_moves": moves, "row": row, "col": col},
                }))

            elif event == "game:undo":
                result = orchestrator.undo_move(game_id)
                state = orchestrator.get_game_state(game_id)
                await manager.send_to_game(game_id, "game:state_update", state)

    except WebSocketDisconnect:
        manager.disconnect(websocket, game_id)
    except Exception as e:
        logger.error("WebSocket error for game %s: %s", game_id, e, exc_info=True)
        manager.disconnect(websocket, game_id)


async def handle_move(game_id: str, payload: dict, orchestrator):
    """수 두기 처리"""
    from_row = payload.get("from_row", payload.get("from", [0, 0])[0] if isinstance(payload.get("from"), list) else 0)
    from_col = payload.get("from_col", payload.get("from", [0, 0])[1] if isinstance(payload.get("from"), list) else 0)
    to_row = payload.get("to_row", payload.get("to", [0, 0])[0] if isinstance(payload.get("to"), list) else 0)
    to_col = payload.get("to_col", payload.get("to", [0, 0])[1] if isinstance(payload.get("to"), list) else 0)

    # 인간 수 실행
    human_result = orchestrator.human_move(game_id, from_row, from_col, to_row, to_col)

    if not human_result.get("success"):
        await manager.send_to_game(game_id, "game:error", {
            "message": human_result.get("error", "Invalid move"),
        })
        return

    # 상태 업데이트 전송
    state = orchestrator.get_game_state(game_id)
    await manager.send_to_game(game_id, "game:state_update", state)

    # 장군 확인
    if state.get("is_check"):
        await manager.send_to_game(game_id, "game:janggun", {
            "check_type": "janggun",
            "message": "장군!",
        })

    # 게임 종료 확인
    if human_result.get("status") != "playing":
        result = orchestrator.finalize_game(game_id)
        await manager.send_to_game(game_id, "game:end", result)
        return

    # AI 수 실행 (별도 스레드에서 CPU-집약적 탐색)
    ai_result = await asyncio.to_thread(orchestrator.ai_move, game_id)

    if ai_result.get("success"):
        # AI 수 전송
        await manager.send_to_game(game_id, "game:ai_move", {
            "move": ai_result["move"],
            "analysis": ai_result.get("report", {}),
            "win_probability": ai_result.get("win_probability", 50),
            "pipeline_time": ai_result.get("total_pipeline_time", 0),
        })

        # 에이전트별 분석 업데이트
        for agent_id, agent_info in ai_result.get("agent_results", {}).items():
            await manager.send_to_game(game_id, "game:analysis_update", {
                "agent_id": agent_id,
                "status": agent_info.get("status"),
                "time": agent_info.get("time"),
            })

        # 상태 업데이트
        state = orchestrator.get_game_state(game_id)
        await manager.send_to_game(game_id, "game:state_update", state)

        # 장군 확인
        if state.get("is_check"):
            await manager.send_to_game(game_id, "game:janggun", {
                "check_type": "janggun",
                "message": "장군!",
            })

        # 게임 종료 확인
        if ai_result.get("status") != "playing":
            result = orchestrator.finalize_game(game_id)
            await manager.send_to_game(game_id, "game:end", result)
