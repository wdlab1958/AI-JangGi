"""장기 오프닝 북 (Opening Book)

초반 포진 정석을 저장하여 탐색 시간을 절약하고 정석적 플레이 보장.
해시 기반 조회로 O(1) 매칭.

형식: {(board_hash, team_hash): [(from_r, from_c, to_r, to_c, weight), ...]}
weight가 높을수록 선호. 동일 weight이면 랜덤 선택.
"""
import random
from typing import Optional

# ── CHO (rows 0-3, forward = +1) 오프닝 정석 ──
# 내상외마 기본 포진 기준
_CHO_OPENINGS = [
    # Move 1 options: 중앙 졸 전진 (가장 일반적)
    {"move_num": 1, "from": (3, 4), "to": (4, 4), "name": "중앙졸진"},
    # Move 1: 좌마 발전
    {"move_num": 1, "from": (0, 1), "to": (2, 2), "name": "좌마진출"},
    # Move 1: 우마 발전
    {"move_num": 1, "from": (0, 7), "to": (2, 6), "name": "우마진출"},

    # Move 3 options (after 1 move each): 마 발전
    {"move_num": 3, "from": (0, 1), "to": (2, 2), "name": "좌마진출"},
    {"move_num": 3, "from": (0, 7), "to": (2, 6), "name": "우마진출"},
    # 졸 전진 (좌/우 날개)
    {"move_num": 3, "from": (3, 2), "to": (4, 2), "name": "좌졸진"},
    {"move_num": 3, "from": (3, 6), "to": (4, 6), "name": "우졸진"},

    # Move 5: 상 발전, 포 이동
    {"move_num": 5, "from": (0, 2), "to": (2, 1), "name": "좌상진출"},
    {"move_num": 5, "from": (0, 6), "to": (2, 7), "name": "우상진출"},
    {"move_num": 5, "from": (3, 0), "to": (4, 0), "name": "좌졸변진"},
    {"move_num": 5, "from": (3, 8), "to": (4, 8), "name": "우졸변진"},
]

# ── HAN (rows 7-9, forward = -1) 오프닝 정석 ──
_HAN_OPENINGS = [
    # Move 2 options: 중앙 졸 전진
    {"move_num": 2, "from": (6, 4), "to": (5, 4), "name": "중앙졸진"},
    # 마 발전
    {"move_num": 2, "from": (9, 1), "to": (7, 2), "name": "좌마진출"},
    {"move_num": 2, "from": (9, 7), "to": (7, 6), "name": "우마진출"},

    # Move 4 options
    {"move_num": 4, "from": (9, 1), "to": (7, 2), "name": "좌마진출"},
    {"move_num": 4, "from": (9, 7), "to": (7, 6), "name": "우마진출"},
    {"move_num": 4, "from": (6, 2), "to": (5, 2), "name": "좌졸진"},
    {"move_num": 4, "from": (6, 6), "to": (5, 6), "name": "우졸진"},

    # Move 6 options
    {"move_num": 6, "from": (9, 2), "to": (7, 1), "name": "좌상진출"},
    {"move_num": 6, "from": (9, 6), "to": (7, 7), "name": "우상진출"},
    {"move_num": 6, "from": (6, 0), "to": (5, 0), "name": "좌졸변진"},
    {"move_num": 6, "from": (6, 8), "to": (5, 8), "name": "우졸변진"},
]

# 오프닝 적용 최대 수 (이후 탐색 사용)
MAX_BOOK_MOVES = 6


class OpeningBook:
    """장기 오프닝 북 - 초반 정석 수 제공"""

    def __init__(self):
        self._cho_moves: dict[int, list[dict]] = {}
        self._han_moves: dict[int, list[dict]] = {}

        for entry in _CHO_OPENINGS:
            mn = entry["move_num"]
            self._cho_moves.setdefault(mn, []).append(entry)

        for entry in _HAN_OPENINGS:
            mn = entry["move_num"]
            self._han_moves.setdefault(mn, []).append(entry)

    def get_book_move(self, board, team, move_count: int,
                      valid_moves_set: Optional[set] = None) -> Optional[dict]:
        """오프닝 북에서 수를 조회. 합법수인 경우에만 반환.

        Args:
            board: Board 인스턴스
            team: 현재 팀
            move_count: 현재까지 진행된 총 수
            valid_moves_set: {(fr, fc, tr, tc), ...} 합법수 집합 (없으면 내부 계산)

        Returns:
            {"from": (r,c), "to": (r,c), "piece": dict, "book_name": str} or None
        """
        # 오프닝 구간 초과 시 None
        next_move_num = move_count + 1
        if next_move_num > MAX_BOOK_MOVES:
            return None

        from .pieces import Team
        book = self._cho_moves if team == Team.CHO else self._han_moves
        candidates = book.get(next_move_num, [])
        if not candidates:
            return None

        # 합법수 집합 준비
        if valid_moves_set is None:
            all_valid = board.get_all_valid_moves(team)
            valid_moves_set = {(p.row, p.col, r, c) for p, r, c in all_valid}

        # 합법수 중 오프닝 북 매칭
        legal_candidates = []
        for entry in candidates:
            fr, fc = entry["from"]
            tr, tc = entry["to"]
            if (fr, fc, tr, tc) in valid_moves_set:
                # 실제 기물 확인
                piece = board.get_piece(fr, fc)
                if piece is not None and piece.team == team:
                    legal_candidates.append((entry, piece))

        if not legal_candidates:
            return None

        # 랜덤 선택 (다양한 오프닝 플레이)
        entry, piece = random.choice(legal_candidates)
        return {
            "from": entry["from"],
            "to": entry["to"],
            "piece": piece.to_dict(),
            "book_name": entry["name"],
        }
