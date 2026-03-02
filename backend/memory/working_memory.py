"""Layer 1: Working Memory (작업 메모리)

현재 턴의 실시간 판면 상태를 관리한다.
- 현재 보드 상태 (9×10 매트릭스)
- 직전 3수 이동 기록
- 현재 턴 평가 점수
- 상대방 직전 수 분석
"""
from collections import deque
from typing import Optional


class WorkingMemory:
    """Layer 1: 현재 턴의 실시간 상태를 관리하는 작업 메모리"""

    def __init__(self):
        self.current_board_state: Optional[list] = None
        self.recent_moves: deque = deque(maxlen=3)  # 직전 3수
        self.current_evaluation: float = 0.0
        self.current_evaluation_detail: dict = {}
        self.opponent_last_move: Optional[dict] = None
        self.current_turn: int = 0
        self.is_in_check: bool = False
        self.valid_moves_count: int = 0
        self.threat_pieces: list = []  # 위협하는 기물 목록
        self.candidate_moves: list = []  # 현재 후보수 목록

    def update(self, board_state: list, move: Optional[dict] = None,
               evaluation: float = 0.0, evaluation_detail: dict = None,
               is_check: bool = False, valid_moves_count: int = 0):
        """매 턴마다 작업 메모리 갱신"""
        self.current_board_state = board_state
        self.current_evaluation = evaluation
        self.current_evaluation_detail = evaluation_detail or {}
        self.is_in_check = is_check
        self.valid_moves_count = valid_moves_count
        self.current_turn += 1

        if move:
            self.recent_moves.append(move)

    def set_opponent_move(self, move: dict):
        """상대방 직전 수 기록"""
        self.opponent_last_move = move

    def set_candidates(self, candidates: list):
        """후보수 설정"""
        self.candidate_moves = candidates

    def set_threats(self, threats: list):
        """위협 기물 설정"""
        self.threat_pieces = threats

    def get_context(self) -> dict:
        """현재 작업 메모리의 컨텍스트 반환 (에이전트 입력용)"""
        return {
            "board_state": self.current_board_state,
            "recent_moves": list(self.recent_moves),
            "evaluation": self.current_evaluation,
            "evaluation_detail": self.current_evaluation_detail,
            "opponent_last_move": self.opponent_last_move,
            "turn": self.current_turn,
            "is_in_check": self.is_in_check,
            "valid_moves_count": self.valid_moves_count,
            "threats": self.threat_pieces,
            "candidates": self.candidate_moves,
        }

    def reset(self):
        """작업 메모리 초기화"""
        self.current_board_state = None
        self.recent_moves.clear()
        self.current_evaluation = 0.0
        self.current_evaluation_detail = {}
        self.opponent_last_move = None
        self.current_turn = 0
        self.is_in_check = False
        self.valid_moves_count = 0
        self.threat_pieces = []
        self.candidate_moves = []
