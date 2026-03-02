"""장기 Orchestrator - Native Sequential Orchestrator 패턴 (개선판)

5개 AI 에이전트의 순차적 실행을 조율.
핵심 개선: 탐색 엔진의 최적수를 최우선, 에이전트 실패 시 복원력 강화.
"""
import time
from typing import Optional

from ..agents.strategy_analyst import StrategyAnalyst
from ..agents.use_case_designer import UseCaseDesigner
from ..agents.win_loss_analyst import WinLossAnalyst
from ..agents.risk_assessor import RiskAssessor
from ..agents.report_generator import ReportGenerator
from ..engine.board import Board
from ..engine.pieces import Team
from ..engine.game import Game
from ..memory.memory_manager import MemoryManager


class JanggiOrchestrator:
    def __init__(self, ai_depth: int = 20, ai_time_limit: float = 5.0,
                 storage_dir: str = "./data/long_term"):
        self.strategy_analyst = StrategyAnalyst(
            max_depth=ai_depth, time_limit=ai_time_limit)
        self.usecase_designer = UseCaseDesigner()
        self.winloss_analyst = WinLossAnalyst()
        self.risk_assessor = RiskAssessor()
        self.report_generator = ReportGenerator()
        self.memory = MemoryManager(storage_dir=storage_dir)
        self.games: dict[str, Game] = {}

    def create_game(self, cho_formation="내상외마", han_formation="내상외마",
                     ai_team="han", ai_depth=20, ai_time_limit=5.0) -> dict:
        team = Team.HAN if ai_team == "han" else Team.CHO
        game = Game(
            cho_formation=cho_formation, han_formation=han_formation,
            ai_team=team, ai_depth=ai_depth, ai_time_limit=ai_time_limit,
        )
        self.games[game.game_id] = game
        self.memory.init_game(game.game_id)
        self.winloss_analyst.reset()
        # 새 게임에서 TT 초기화
        self.strategy_analyst.search_engine.clear_tt()
        return game.get_state()

    def human_move(self, game_id: str, from_row: int, from_col: int,
                    to_row: int, to_col: int) -> dict:
        game = self.games.get(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        result = game.make_human_move(from_row, from_col, to_row, to_col)

        if result["success"]:
            evaluation = game.evaluator.evaluate(
                game.board, game.ai_team, game.phase.value)
            self.memory.update_turn(
                board_state=game.board.to_matrix(),
                move=result["move"],
                phase=game.phase.value,
                evaluation=evaluation,
                is_opponent=True,
            )
        return result

    def ai_move(self, game_id: str) -> dict:
        """AI 수 실행 - 5개 에이전트 파이프라인 (탐색 엔진 결과 최우선)"""
        game = self.games.get(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}

        # 턴/상태 확인
        if game.status.value != "playing":
            return {"success": False, "error": "Game is not in playing state"}
        if game.current_turn != game.ai_team:
            return {"success": False, "error": "Not AI's turn"}

        start_time = time.time()
        memory_context = self.memory.get_full_context()

        # === Agent Pipeline ===

        # [1] 전략 분석가 (핵심: Minimax 탐색)
        strategy_output = self.strategy_analyst.run({
            "board": game.board,
            "team": game.ai_team,
            "phase": game.phase.value,
            "move_count": game.move_count,
            "memory_context": memory_context,
        })
        strategy_result = strategy_output.get("result", {})

        # Agent 1 실패 시 직접 게임 엔진 사용
        if strategy_output.get("status") == "error" or not strategy_result.get("recommended_move"):
            return game.make_ai_move()

        # [2] 사례 설계자
        usecase_output = self.usecase_designer.run({
            "strategy_result": strategy_result,
            "phase": game.phase.value,
            "memory_context": memory_context,
        })
        usecase_result = usecase_output.get("result", {})

        # [3] 승패 분석가
        winloss_output = self.winloss_analyst.run({
            "strategy_result": strategy_result,
            "usecase_result": usecase_result,
            "memory_context": memory_context,
        })
        winloss_result = winloss_output.get("result", {})

        # [4] 리스크 평가자 (board copy 사용, 원본 보호)
        risk_output = self.risk_assessor.run({
            "board": game.board,
            "team": game.ai_team,
            "strategy_result": strategy_result,
            "winloss_result": winloss_result,
            "memory_context": memory_context,
        })
        risk_result = risk_output.get("result", {})

        # 최종 수 결정: 리스크 평가자가 탐색 엔진 결과를 존중
        final_move = (risk_result.get("final_recommended_move")
                      or strategy_result.get("recommended_move"))

        if final_move is None:
            return game.make_ai_move()

        # 이동 유효성 검증
        fr, fc = final_move["from"]
        tr, tc = final_move["to"]
        piece = game.board.get_piece(fr, fc)

        if piece is None or piece.team != game.ai_team:
            # 잘못된 수 → 폴백
            return game.make_ai_move()

        # 합법수 확인
        valid = game.board.get_valid_moves(piece)
        if (tr, tc) not in valid:
            return game.make_ai_move()

        # 수 실행
        captured = game.board.move_piece(fr, fc, tr, tc)
        game.move_count += 1
        now = time.time()
        if game.ai_team == Team.CHO:
            game.cho_time += now - game.last_move_time
        else:
            game.han_time += now - game.last_move_time
        game.last_move_time = now

        evaluation = game.evaluator.evaluate_detailed(
            game.board, game.ai_team, game.phase.value)

        # [5] 보고서 생성자 (수 실행 후)
        report_output = self.report_generator.run({
            "strategy_result": strategy_result,
            "usecase_result": usecase_result,
            "winloss_result": winloss_result,
            "risk_result": risk_result,
            "game_state": game.get_state(),
            "move_number": game.move_count,
        })
        report_result = report_output.get("result", {})

        # 메모리 업데이트
        self.memory.update_turn(
            board_state=game.board.to_matrix(),
            move={
                "from": (fr, fc), "to": (tr, tc),
                "piece": piece.to_dict(),
                "captured": captured.to_dict() if captured else None,
            },
            phase=game.phase.value,
            evaluation=evaluation["total"],
            evaluation_detail=evaluation,
            is_opponent=False,
        )

        # 게임 종료 확인
        game._check_game_end()
        game._record_position()

        # 턴 전환
        if game.status.value == "playing":
            game.current_turn = game.human_team

        analysis = {
            "move_number": game.move_count,
            "move": {"from": (fr, fc), "to": (tr, tc)},
            "score": strategy_result.get("search_stats", {}).get("score", 0),
            "evaluation": evaluation,
            "depth": strategy_result.get("search_stats", {}).get("depth", 0),
            "nodes": strategy_result.get("search_stats", {}).get("nodes", 0),
            "time": round(time.time() - start_time, 3),
            "phase": game.phase.value,
        }
        game.analysis_history.append(analysis)

        total_time = round(time.time() - start_time, 3)

        return {
            "success": True,
            "move": {
                "from": (fr, fc), "to": (tr, tc),
                "piece": piece.to_dict(),
                "captured": captured.to_dict() if captured else None,
            },
            "analysis": analysis,
            "report": report_result,
            "agent_results": {
                "strategy": {
                    "status": strategy_output.get("status"),
                    "time": strategy_output.get("execution_time"),
                },
                "usecase": {
                    "status": usecase_output.get("status"),
                    "time": usecase_output.get("execution_time"),
                },
                "winloss": {
                    "status": winloss_output.get("status"),
                    "time": winloss_output.get("execution_time"),
                },
                "risk": {
                    "status": risk_output.get("status"),
                    "time": risk_output.get("execution_time"),
                },
                "report": {
                    "status": report_output.get("status"),
                    "time": report_output.get("execution_time"),
                },
            },
            "board_state": game.board.to_matrix(),
            "move_count": game.move_count,
            "phase": game.phase.value,
            "status": game.status.value,
            "win_probability": winloss_result.get("win_probability", 50),
            "total_pipeline_time": total_time,
        }

    def undo_move(self, game_id: str) -> dict:
        game = self.games.get(game_id)
        if not game:
            return {"success": False, "error": "Game not found"}
        return game.undo_move()

    def get_game_state(self, game_id: str) -> dict:
        game = self.games.get(game_id)
        if not game:
            return {"error": "Game not found"}
        state = game.get_state()
        state["win_probability"] = round(game.get_win_probability() * 100, 1)
        return state

    def get_valid_moves(self, game_id: str, row: int, col: int) -> list:
        game = self.games.get(game_id)
        if not game:
            return []
        return game.get_valid_moves_for_position(row, col)

    def get_analysis(self, game_id: str) -> dict:
        game = self.games.get(game_id)
        if not game:
            return {"error": "Game not found"}
        return {
            "analysis_history": game.analysis_history,
            "memory_context": self.memory.get_full_context(),
            "agent_status": {
                "strategy": self.strategy_analyst.get_status(),
                "usecase": self.usecase_designer.get_status(),
                "winloss": self.winloss_analyst.get_status(),
                "risk": self.risk_assessor.get_status(),
                "report": self.report_generator.get_status(),
            },
        }

    def get_or_create_report(self, game_id: str) -> dict:
        """GET /report용 idempotent 래퍼: 캐시된 보고서가 있으면 반환"""
        if not hasattr(self, "_report_cache"):
            self._report_cache: dict[str, dict] = {}
        if game_id in self._report_cache:
            return self._report_cache[game_id]
        result = self.finalize_game(game_id)
        if "error" not in result:
            self._report_cache[game_id] = result
        return result

    def finalize_game(self, game_id: str) -> dict:
        game = self.games.get(game_id)
        if not game:
            return {"error": "Game not found"}

        result = "draw"
        if game.status.value == "cho_win":
            result = "win" if game.ai_team == Team.CHO else "loss"
        elif game.status.value == "han_win":
            result = "win" if game.ai_team == Team.HAN else "loss"

        self.memory.finalize_game(game_id, result)

        final_report = self.report_generator.generate_final_report({
            "game_id": game_id,
            "result": result,
            "total_moves": game.move_count,
            "duration": time.time() - game.created_at,
            "analysis_history": game.analysis_history,
        })

        return {
            "game_id": game_id,
            "result": result,
            "total_moves": game.move_count,
            "final_report": final_report,
            "stats": self.memory.long_term.get_stats(),
        }

    def get_stats(self) -> dict:
        return self.memory.long_term.get_stats()
