"""판면 평가 함수 (Evaluation Function) - 초고속 버전

단일 패스 평가: 모든 기물을 1번만 순회하여 material + position + king_safety 계산.
탐색 리프 노드에서 최고 속도 달성.
"""
from .board import Board, PALACE_CHO, PALACE_HAN
from .pieces import Piece, PieceType, Team, PIECE_VALUES

# ── 위치 점수 테이블 (CHO 관점, HAN은 행 반전) ──
POSITION_TABLE = {
    PieceType.PAWN: [
        [0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0],
        [2, 0, 4, 0, 8, 0, 4, 0, 2],
        [6, 0, 8, 0, 12, 0, 8, 0, 6],
        [6, 14, 16, 18, 20, 18, 16, 14, 6],
        [10, 18, 22, 26, 30, 26, 22, 18, 10],
        [14, 22, 28, 34, 40, 34, 28, 22, 14],
        [16, 26, 34, 42, 50, 42, 34, 26, 16],
        [18, 30, 38, 48, 60, 48, 38, 30, 18],
    ],
    PieceType.CAR: [
        [14, 16, 16, 16, 18, 16, 16, 16, 14],
        [16, 20, 20, 20, 22, 20, 20, 20, 16],
        [14, 18, 18, 18, 20, 18, 18, 18, 14],
        [14, 18, 18, 18, 20, 18, 18, 18, 14],
        [12, 16, 16, 16, 18, 16, 16, 16, 12],
        [12, 16, 16, 16, 18, 16, 16, 16, 12],
        [14, 18, 18, 18, 20, 18, 18, 18, 14],
        [14, 18, 18, 22, 26, 22, 18, 18, 14],
        [14, 18, 18, 26, 30, 26, 18, 18, 14],
        [14, 18, 18, 26, 30, 26, 18, 18, 14],
    ],
    PieceType.CANNON: [
        [10, 10, 10, 10, 10, 10, 10, 10, 10],
        [10, 14, 14, 14, 14, 14, 14, 14, 10],
        [8, 12, 12, 12, 14, 12, 12, 12, 8],
        [8, 12, 12, 12, 14, 12, 12, 12, 8],
        [8, 12, 14, 14, 16, 14, 14, 12, 8],
        [8, 12, 14, 14, 16, 14, 14, 12, 8],
        [8, 12, 14, 16, 20, 16, 14, 12, 8],
        [8, 12, 14, 18, 22, 18, 14, 12, 8],
        [8, 12, 14, 18, 22, 18, 14, 12, 8],
        [8, 12, 14, 18, 22, 18, 14, 12, 8],
    ],
    PieceType.HORSE: [
        [4, 8, 10, 10, 8, 10, 10, 8, 4],
        [8, 12, 16, 16, 16, 16, 16, 12, 8],
        [10, 16, 20, 22, 22, 22, 20, 16, 10],
        [10, 16, 22, 26, 28, 26, 22, 16, 10],
        [10, 16, 22, 26, 30, 26, 22, 16, 10],
        [10, 16, 22, 26, 30, 26, 22, 16, 10],
        [10, 16, 22, 26, 28, 26, 22, 16, 10],
        [10, 16, 20, 22, 22, 22, 20, 16, 10],
        [8, 12, 16, 16, 18, 16, 16, 12, 8],
        [4, 8, 10, 12, 14, 12, 10, 8, 4],
    ],
    PieceType.ELEPHANT: [
        [0, 4, 8, 0, 0, 0, 8, 4, 0],
        [4, 8, 12, 8, 0, 8, 12, 8, 4],
        [6, 12, 16, 14, 8, 14, 16, 12, 6],
        [8, 14, 18, 16, 12, 16, 18, 14, 8],
        [10, 16, 20, 18, 14, 18, 20, 16, 10],
        [10, 16, 20, 18, 14, 18, 20, 16, 10],
        [8, 14, 18, 16, 12, 16, 18, 14, 8],
        [6, 12, 16, 14, 8, 14, 16, 12, 6],
        [4, 8, 12, 8, 0, 8, 12, 8, 4],
        [0, 4, 8, 0, 0, 0, 8, 4, 0],
    ],
    PieceType.GUARD: [
        [0, 0, 0, 10, 8, 10, 0, 0, 0],
        [0, 0, 0, 8, 16, 8, 0, 0, 0],
        [0, 0, 0, 10, 8, 10, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 10, 8, 10, 0, 0, 0],
        [0, 0, 0, 8, 16, 8, 0, 0, 0],
        [0, 0, 0, 10, 8, 10, 0, 0, 0],
    ],
    PieceType.KING: [
        [0, 0, 0, 4, 2, 4, 0, 0, 0],
        [0, 0, 0, 6, 10, 6, 0, 0, 0],
        [0, 0, 0, 4, 2, 4, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 4, 2, 4, 0, 0, 0],
        [0, 0, 0, 6, 10, 6, 0, 0, 0],
        [0, 0, 0, 4, 2, 4, 0, 0, 0],
    ],
}

# 위치 테이블 pre-computed (tuple로 변환하여 빠른 접근)
_POS_TABLES = {pt: tuple(tuple(row) for row in table) for pt, table in POSITION_TABLE.items()}

# 게임 페이즈별 가중치
PHASE_WEIGHTS = {
    "opening":  {"material": 1.0, "position": 0.005, "king_safety": 0.6},
    "midgame":  {"material": 1.0, "position": 0.004, "king_safety": 0.8},
    "endgame":  {"material": 1.2, "position": 0.003, "king_safety": 1.0},
}

# 왕 근접 위험 가중치 (기물 타입별)
_KS_CAR_LINE = 8.0
_KS_CAR_NEAR = 3.0
_KS_HORSE = 4.0
_KS_CANNON_LINE = 5.0
_KS_GUARD_BONUS = 4.0
_KS_ALLY_BONUS = 1.0

# 종반전 보너스 가중치
_EG_KING_CENTER_BONUS = 3.0   # 왕의 중앙 위치 보너스
_EG_PAWN_ADVANCE_BONUS = 2.0  # 졸 전진 보너스
_EG_CAR_ACTIVITY = 1.5        # 차의 활동성 보너스


class Evaluator:
    """초고속 장기 판면 평가기 - 단일 패스"""

    def evaluate(self, board: Board, team: Team, phase: str = "midgame") -> float:
        """팀 관점 판면 점수. 양수 = 유리. 그리드 직접 순회로 최고 속도."""
        w = PHASE_WEIGHTS.get(phase, PHASE_WEIGHTS["midgame"])
        wm = w["material"]
        wp = w["position"]
        wk = w["king_safety"]

        # 기물 수 기반 보정 (한번만 계산)
        remaining = board.count_pieces()
        is_endgame = phase == "endgame" or remaining <= 14
        is_late = remaining <= 20

        # 왕 위치 (한번만 조회)
        my_king = board.get_king(team)
        if my_king is None:
            return -500.0 * wk
        enemy = Team.HAN if team == Team.CHO else Team.CHO
        en_king = board.get_king(enemy)
        if en_king is None:
            return 500.0 * wk

        my_kr, my_kc = my_king.row, my_king.col
        en_kr, en_kc = en_king.row, en_king.col
        my_palace = PALACE_CHO if team == Team.CHO else PALACE_HAN
        en_palace = PALACE_CHO if enemy == Team.CHO else PALACE_HAN

        # 로컬 변수 (빠른 참조)
        _CANNON = PieceType.CANNON
        _PAWN = PieceType.PAWN
        _CAR = PieceType.CAR
        _HORSE = PieceType.HORSE
        _GUARD = PieceType.GUARD
        _HAN = Team.HAN

        score = 0.0
        my_ks = 0.0
        en_ks = 0.0
        grid = board.grid

        # 그리드 직접 순회 (captured 체크 불필요)
        for r in range(10):
            row = grid[r]
            for c in range(9):
                p = row[c]
                if p is None:
                    continue

                pt = p.piece_type
                is_mine = (p.team is team)
                sign = 1.0 if is_mine else -1.0

                # Material (인라인, 캐시된 _value 사용)
                base = float(p._value)
                if pt is _CANNON:
                    if is_endgame:
                        base *= 0.6
                    elif is_late:
                        base *= 0.8
                elif pt is _PAWN:
                    if is_endgame:
                        base *= 1.5
                elif pt is _CAR:
                    base += 1.0
                score += sign * wm * base

                # Position (인라인)
                table = _POS_TABLES.get(pt)
                if table is not None:
                    trow = (9 - r) if p.team is _HAN else r
                    score += sign * wp * table[trow][c]

                # King Safety
                if is_mine:
                    if pt is _CAR:
                        if r == en_kr or c == en_kc:
                            en_ks -= _KS_CAR_LINE
                        elif abs(r - en_kr) + abs(c - en_kc) <= 3:
                            en_ks -= _KS_CAR_NEAR
                    elif pt is _HORSE:
                        if abs(r - en_kr) + abs(c - en_kc) <= 3:
                            en_ks -= _KS_HORSE
                    elif pt is _CANNON:
                        if r == en_kr or c == en_kc:
                            en_ks -= _KS_CANNON_LINE
                    if abs(r - my_kr) <= 1 and abs(c - my_kc) <= 1 and (r != my_kr or c != my_kc):
                        if (r, c) in my_palace:
                            my_ks += _KS_GUARD_BONUS if pt is _GUARD else _KS_ALLY_BONUS
                else:
                    if pt is _CAR:
                        if r == my_kr or c == my_kc:
                            my_ks -= _KS_CAR_LINE
                        elif abs(r - my_kr) + abs(c - my_kc) <= 3:
                            my_ks -= _KS_CAR_NEAR
                    elif pt is _HORSE:
                        if abs(r - my_kr) + abs(c - my_kc) <= 3:
                            my_ks -= _KS_HORSE
                    elif pt is _CANNON:
                        if r == my_kr or c == my_kc:
                            my_ks -= _KS_CANNON_LINE
                    if abs(r - en_kr) <= 1 and abs(c - en_kc) <= 1 and (r != en_kr or c != en_kc):
                        if (r, c) in en_palace:
                            en_ks += _KS_GUARD_BONUS if pt is _GUARD else _KS_ALLY_BONUS

        score += wk * (my_ks - en_ks)

        # ── 종반전 전략 보너스 ──
        if is_endgame:
            # 왕 중앙화 보너스 (종반에서 왕이 적극적으로 활동)
            my_king_center = 4.0 - abs(my_kc - 4) * 0.5
            en_king_center = 4.0 - abs(en_kc - 4) * 0.5
            score += _EG_KING_CENTER_BONUS * (my_king_center - en_king_center)

            # 졸 전진 보너스 (적진 깊숙이 진입한 졸)
            for r in range(10):
                row = grid[r]
                for c in range(9):
                    p = row[c]
                    if p is None or p.piece_type is not _PAWN:
                        continue
                    is_mine = (p.team is team)
                    if is_mine:
                        # CHO 졸은 row 클수록 전진, HAN 졸은 row 작을수록 전진
                        if p.team is Team.CHO:
                            advance = r - 3  # 초기 위치 row 3
                        else:
                            advance = 6 - r  # 초기 위치 row 6
                        if advance > 0:
                            score += _EG_PAWN_ADVANCE_BONUS * advance
                    else:
                        if p.team is Team.CHO:
                            advance = r - 3
                        else:
                            advance = 6 - r
                        if advance > 0:
                            score -= _EG_PAWN_ADVANCE_BONUS * advance

        return score

    def evaluate_detailed(self, board: Board, team: Team, phase: str = "midgame") -> dict:
        """상세 평가 (UI/분석용). evaluate()와 동일 결과 + 구성요소 분리."""
        w = PHASE_WEIGHTS.get(phase, PHASE_WEIGHTS["midgame"])
        wm = w["material"]
        wp = w["position"]
        wk = w["king_safety"]

        remaining = board.count_pieces()
        is_endgame = phase == "endgame" or remaining <= 14
        is_late = remaining <= 20
        enemy = Team.HAN if team == Team.CHO else Team.CHO

        # Material
        my_mat = 0.0
        en_mat = 0.0
        for p in board.pieces:
            if p.captured:
                continue
            base = float(p.value)
            pt = p.piece_type
            if pt == PieceType.CANNON:
                if is_endgame:
                    base *= 0.6
                elif is_late:
                    base *= 0.8
            elif pt == PieceType.PAWN:
                if is_endgame:
                    base *= 1.5
            elif pt == PieceType.CAR:
                base += 1.0
            if p.team == team:
                my_mat += base
            else:
                en_mat += base

        material = my_mat - en_mat

        # Position
        my_pos = 0.0
        en_pos = 0.0
        for p in board.pieces:
            if p.captured:
                continue
            table = POSITION_TABLE.get(p.piece_type)
            if table is None:
                continue
            row = (9 - p.row) if p.team == Team.HAN else p.row
            val = table[row][p.col]
            if p.team == team:
                my_pos += val
            else:
                en_pos += val
        position = my_pos - en_pos

        # King safety (simplified for display)
        king_safety = 0.0
        my_king = board.get_king(team)
        en_king = board.get_king(enemy)
        if my_king is None:
            king_safety = -500.0
        elif en_king is None:
            king_safety = 500.0
        else:
            # Use fast evaluation logic
            total = self.evaluate(board, team, phase)
            mat_pos = wm * material + wp * position
            king_safety = (total - mat_pos) / wk if wk != 0 else 0.0

        total = wm * material + wp * position + wk * king_safety

        return {
            "total": round(total, 2),
            "material": round(material, 2),
            "position": round(position * 0.01, 2),
            "mobility": 0.0,
            "king_safety": round(king_safety, 2),
            "weighted": {
                "material": round(wm * material, 2),
                "position": round(wp * position, 2),
                "mobility": 0.0,
                "king_safety": round(wk * king_safety, 2),
            },
        }
