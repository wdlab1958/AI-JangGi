"""장기 게임 세션 관리 모듈 (개선판)

게임 페이즈를 기물 수로 판단, 반복 검출, 빅장 처리 개선.
"""
import uuid
import time
import math
from typing import Optional
from enum import Enum

from .board import Board
from .pieces import Piece, PieceType, Team
from .evaluator import Evaluator
from .search import SearchEngine


class GamePhase(Enum):
    OPENING = "opening"
    MIDGAME = "midgame"
    ENDGAME = "endgame"


class GameStatus(Enum):
    WAITING = "waiting"
    PLAYING = "playing"
    CHO_WIN = "cho_win"
    HAN_WIN = "han_win"
    DRAW = "draw"


class Game:
    def __init__(self, game_id: Optional[str] = None,
                 cho_formation: str = "내상외마",
                 han_formation: str = "내상외마",
                 ai_team: Team = Team.HAN,
                 ai_depth: int = 20,
                 ai_time_limit: float = 5.0):
        self.game_id = game_id or str(uuid.uuid4())
        self.board = Board()
        self.board.setup_initial_position(cho_formation, han_formation)
        self.current_turn = Team.CHO
        self.status = GameStatus.PLAYING
        self.move_count = 0
        self.ai_team = ai_team
        self.human_team = Team.CHO if ai_team == Team.HAN else Team.HAN
        self.evaluator = Evaluator()
        self.search_engine = SearchEngine(max_depth=ai_depth, time_limit=ai_time_limit)
        self.created_at = time.time()
        self.last_move_time = time.time()
        self.cho_time = 0.0
        self.han_time = 0.0
        self.analysis_history: list[dict] = []
        # 반복 포지션 검출용
        self.position_history: dict[int, int] = {}
        self._position_order: list[int] = []  # 순서 추적 (undo 시 복원용)
        self._record_position()

    @property
    def phase(self) -> GamePhase:
        """기물 수 기반 페이즈 판단"""
        remaining = self.board.count_pieces()
        if remaining >= 28:           # 거의 모든 기물이 살아있음
            return GamePhase.OPENING
        elif remaining >= 16:
            return GamePhase.MIDGAME
        else:
            return GamePhase.ENDGAME

    def _record_position(self):
        """현재 포지션을 기록 (반복 검출용)"""
        key = self.board.hash_with_side(self.current_turn)
        self.position_history[key] = self.position_history.get(key, 0) + 1
        self._position_order.append(key)
        # 탐색 엔진에도 기록 (탐색 중 반복 탐지)
        self.search_engine.record_position(self.board, self.current_turn)

    def _check_repetition(self) -> bool:
        """같은 포지션이 3회 반복되었는지"""
        key = self.board.hash_with_side(self.current_turn)
        return self.position_history.get(key, 0) >= 3

    def make_human_move(self, from_row: int, from_col: int,
                         to_row: int, to_col: int) -> dict:
        if self.status != GameStatus.PLAYING:
            return {"success": False, "error": "Game is not in playing state"}
        if self.current_turn != self.human_team:
            return {"success": False, "error": "Not your turn"}

        piece = self.board.get_piece(from_row, from_col)
        if piece is None:
            return {"success": False, "error": "No piece at this position"}
        if piece.team != self.human_team:
            return {"success": False, "error": "Not your piece"}

        valid_moves = self.board.get_valid_moves(piece)
        if (to_row, to_col) not in valid_moves:
            return {"success": False, "error": "Invalid move"}

        captured = self.board.move_piece(from_row, from_col, to_row, to_col)
        self.move_count += 1
        now = time.time()
        if self.human_team == Team.CHO:
            self.cho_time += now - self.last_move_time
        else:
            self.han_time += now - self.last_move_time
        self.last_move_time = now

        self._check_game_end()
        self._record_position()

        result = {
            "success": True,
            "move": {
                "from": (from_row, from_col),
                "to": (to_row, to_col),
                "piece": piece.to_dict(),
                "captured": captured.to_dict() if captured else None,
            },
            "board_state": self.board.to_matrix(),
            "move_count": self.move_count,
            "phase": self.phase.value,
            "status": self.status.value,
        }

        if self.status == GameStatus.PLAYING:
            self.current_turn = self.ai_team
        return result

    def make_ai_move(self) -> dict:
        if self.status != GameStatus.PLAYING:
            return {"success": False, "error": "Game is not in playing state"}
        if self.current_turn != self.ai_team:
            return {"success": False, "error": "Not AI's turn"}

        search_result = self.search_engine.find_best_move(
            self.board, self.ai_team, phase=self.phase.value,
            move_count=self.move_count)

        if search_result["move"] is None:
            self.status = (GameStatus.CHO_WIN if self.ai_team == Team.HAN
                           else GameStatus.HAN_WIN)
            return {"success": False, "error": "AI has no valid moves",
                    "status": self.status.value}

        move = search_result["move"]
        fr, fc = move["from"]
        tr, tc = move["to"]

        captured = self.board.move_piece(fr, fc, tr, tc)
        self.move_count += 1
        now = time.time()
        if self.ai_team == Team.CHO:
            self.cho_time += now - self.last_move_time
        else:
            self.han_time += now - self.last_move_time
        self.last_move_time = now

        evaluation = self.evaluator.evaluate_detailed(
            self.board, self.ai_team, self.phase.value)

        analysis = {
            "move_number": self.move_count,
            "move": {"from": (fr, fc), "to": (tr, tc)},
            "score": search_result["score"],
            "evaluation": evaluation,
            "candidates": search_result.get("candidates", []),
            "depth": search_result.get("depth", 0),
            "nodes": search_result.get("nodes", 0),
            "time": search_result.get("time", 0),
            "phase": self.phase.value,
        }
        self.analysis_history.append(analysis)

        self._check_game_end()
        self._record_position()

        result = {
            "success": True,
            "move": {
                "from": (fr, fc), "to": (tr, tc),
                "piece": move["piece"],
                "captured": captured.to_dict() if captured else None,
            },
            "analysis": analysis,
            "board_state": self.board.to_matrix(),
            "move_count": self.move_count,
            "phase": self.phase.value,
            "status": self.status.value,
        }

        if self.status == GameStatus.PLAYING:
            self.current_turn = self.human_team
        return result

    def undo_move(self) -> dict:
        if self.move_count < 2:
            return {"success": False, "error": "Not enough moves to undo"}

        self.board.undo_move()
        self.board.undo_move()
        self.move_count -= 2
        self.current_turn = self.human_team
        self.status = GameStatus.PLAYING

        # position_history 복원 (마지막 2개 제거)
        for _ in range(2):
            if self._position_order:
                key = self._position_order.pop()
                cnt = self.position_history.get(key, 1)
                if cnt <= 1:
                    self.position_history.pop(key, None)
                else:
                    self.position_history[key] = cnt - 1

        # 탐색 엔진 포지션 히스토리도 정리
        if len(self.search_engine.position_history) >= 2:
            self.search_engine.position_history = self.search_engine.position_history[:-2]

        if self.analysis_history:
            self.analysis_history.pop()

        return {
            "success": True,
            "board_state": self.board.to_matrix(),
            "move_count": self.move_count,
            "phase": self.phase.value,
        }

    def get_valid_moves_for_position(self, row: int, col: int) -> list[tuple[int,int]]:
        if self.status != GameStatus.PLAYING:
            return []
        piece = self.board.get_piece(row, col)
        if piece is None or piece.team != self.current_turn:
            return []
        return self.board.get_valid_moves(piece)

    def _check_bikjang(self) -> bool:
        """빅장 검출: 두 왕이 같은 열에서 사이에 기물 없이 마주보는 상태"""
        cho_king = self.board.get_king(Team.CHO)
        han_king = self.board.get_king(Team.HAN)
        if cho_king is None or han_king is None:
            return False
        if cho_king.col != han_king.col:
            return False
        # 같은 열 → 사이에 기물 있는지 확인
        col = cho_king.col
        min_row = min(cho_king.row, han_king.row)
        max_row = max(cho_king.row, han_king.row)
        for row in range(min_row + 1, max_row):
            if self.board.get_piece(row, col) is not None:
                return False
        return True

    def _check_game_end(self):
        """게임 종료 조건: 외통, 반복, 빅장"""
        enemy = Team.HAN if self.current_turn == Team.CHO else Team.CHO
        next_team = enemy

        # 외통 (체크메이트 또는 합법수 없음)
        if self.board.is_checkmate(next_team):
            if next_team == Team.CHO:
                self.status = GameStatus.HAN_WIN
            else:
                self.status = GameStatus.CHO_WIN
            return

        # 빅장 (두 왕이 마주봄) → 무승부
        if self._check_bikjang():
            self.status = GameStatus.DRAW
            return

        # 3회 반복 → 무승부
        if self._check_repetition():
            self.status = GameStatus.DRAW
            return

        # 200수 초과 → 무승부
        if self.move_count >= 200:
            self.status = GameStatus.DRAW

    def get_state(self) -> dict:
        is_check = self.board.is_in_check(self.current_turn)

        return {
            "game_id": self.game_id,
            "board": self.board.to_matrix(),
            "current_turn": self.current_turn.value,
            "status": self.status.value,
            "move_count": self.move_count,
            "phase": self.phase.value,
            "is_check": is_check,
            "cho_time": round(self.cho_time, 1),
            "han_time": round(self.han_time, 1),
            "captured_pieces": [p.to_dict() for p in self.board.captured_pieces],
            "evaluation": self.evaluator.evaluate_detailed(
                self.board, self.ai_team, self.phase.value),
        }

    def get_win_probability(self) -> float:
        eval_score = self.evaluator.evaluate(
            self.board, self.ai_team, self.phase.value)
        try:
            return 1.0 / (1.0 + math.exp(-eval_score * 0.15))
        except OverflowError:
            return 0.0 if eval_score < 0 else 1.0
