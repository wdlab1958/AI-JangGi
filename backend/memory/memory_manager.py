"""3-Layer Memory Manager

Working Memory ← 매 턴 갱신 → Short-term ← 5턴마다 동기화 → Long-term ← 경기 종료 시 전이
"""
from .working_memory import WorkingMemory
from .short_term_memory import ShortTermMemory
from .long_term_memory import LongTermMemory


class MemoryManager:
    """3-Layer 메모리 시스템 통합 관리자"""

    def __init__(self, storage_dir: str = "./data/long_term"):
        self.working = WorkingMemory()
        self.short_term = ShortTermMemory()
        self.long_term = LongTermMemory(storage_dir=storage_dir)

    def init_game(self, game_id: str):
        """새 게임 시작 시 메모리 초기화"""
        self.working.reset()
        self.short_term.init_game(game_id)

    def update_turn(self, board_state: list, move: dict, phase: str,
                     evaluation: float, evaluation_detail: dict = None,
                     is_check: bool = False, valid_moves_count: int = 0,
                     is_opponent: bool = False):
        """매 턴마다 메모리 갱신"""
        # Layer 1: Working Memory 갱신
        self.working.update(
            board_state=board_state,
            move=move,
            evaluation=evaluation,
            evaluation_detail=evaluation_detail,
            is_check=is_check,
            valid_moves_count=valid_moves_count,
        )

        if is_opponent:
            self.working.set_opponent_move(move)

        # Layer 2: Short-term Memory 기록
        self.short_term.record_move(move, phase, evaluation, is_opponent)

        # 5턴마다 Layer 2 → Layer 3 동기화
        if self.short_term.should_sync():
            self._sync_to_long_term()
            self.short_term.reset_sync_counter()

    def _sync_to_long_term(self):
        """Short-term → Long-term 동기화"""
        profile = self.short_term.get_opponent_profile()
        if profile and self.short_term.game_id:
            self.long_term.update_player_profile(
                "current_opponent", profile
            )

    def finalize_game(self, game_id: str, result: str,
                       opponent_id: str = "anonymous"):
        """경기 종료 시 전체 데이터를 Long-term으로 전이"""
        game_data = {
            "move_sequence": self.short_term.move_sequence,
            "opponent_profile": self.short_term.get_opponent_profile(),
            "critical_points": self.short_term.critical_points,
            "phase_strategies": self.short_term.phase_strategies,
            "evaluation_history": self.short_term.evaluation_history,
            "total_moves": len(self.short_term.move_sequence),
        }

        self.long_term.record_game_result(
            game_id=game_id,
            result=result,
            opponent_id=opponent_id,
            game_data=game_data,
        )

        # 상대 프로파일 영구 저장
        if opponent_id != "anonymous":
            self.long_term.update_player_profile(
                opponent_id, self.short_term.get_opponent_profile()
            )

    def get_full_context(self) -> dict:
        """전체 메모리 컨텍스트 반환 (에이전트 입력용)"""
        return {
            "working": self.working.get_context(),
            "short_term": self.short_term.get_context(),
            "long_term": self.long_term.get_context(),
        }
