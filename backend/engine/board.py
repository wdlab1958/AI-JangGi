"""장기 보드 및 이동 규칙 구현 모듈 (개선판)

9x10 보드. Zobrist 해싱, 궁성 대각선 슬라이딩, 빅장 분리 처리.
"""
import random as _random
from typing import Optional
from .pieces import Piece, PieceType, Team

# ── 궁성 좌표 ──
PALACE_CHO = {(0,3),(0,4),(0,5),(1,3),(1,4),(1,5),(2,3),(2,4),(2,5)}
PALACE_HAN = {(7,3),(7,4),(7,5),(8,3),(8,4),(8,5),(9,3),(9,4),(9,5)}
PALACE_ALL = PALACE_CHO | PALACE_HAN

# 궁성 1칸 대각선 (왕/사/졸 이동용)
PALACE_DIAG = {
    (0,3):[(1,4)], (0,5):[(1,4)],
    (1,4):[(0,3),(0,5),(2,3),(2,5)],
    (2,3):[(1,4)], (2,5):[(1,4)],
    (7,3):[(8,4)], (7,5):[(8,4)],
    (8,4):[(7,3),(7,5),(9,3),(9,5)],
    (9,3):[(8,4)], (9,5):[(8,4)],
}

# 궁성 대각선 슬라이딩 경로 (차/포용): 각 위치에서 대각선 방향별 순서 리스트
PALACE_SLIDE = {
    (0,3):[[(1,4),(2,5)]], (0,5):[[(1,4),(2,3)]],
    (1,4):[[(0,3)],[(0,5)],[(2,3)],[(2,5)]],
    (2,3):[[(1,4),(0,5)]], (2,5):[[(1,4),(0,3)]],
    (7,3):[[(8,4),(9,5)]], (7,5):[[(8,4),(9,3)]],
    (8,4):[[(7,3)],[(7,5)],[(9,3)],[(9,5)]],
    (9,3):[[(8,4),(7,5)]], (9,5):[[(8,4),(7,3)]],
}

# ── Zobrist 해시 테이블 (고정 시드로 결정적) ──
_zrng = _random.Random(20260303)
ZOBRIST_PIECE: dict[tuple[str,str,int,int], int] = {}
for _t in ("cho","han"):
    for _pt in ("king","car","cannon","horse","elephant","guard","pawn"):
        for _r in range(10):
            for _c in range(9):
                ZOBRIST_PIECE[(_t,_pt,_r,_c)] = _zrng.getrandbits(64)
ZOBRIST_SIDE = _zrng.getrandbits(64)   # HAN 차례일 때 XOR


class Board:
    """9x10 장기 보드"""
    ROWS = 10
    COLS = 9

    def __init__(self):
        self.grid: list[list[Optional[Piece]]] = [
            [None]*self.COLS for _ in range(self.ROWS)
        ]
        self.pieces: list[Piece] = []
        self.move_history: list[tuple] = []
        self.captured_pieces: list[Piece] = []
        self.zobrist_hash: int = 0

    # ── Zobrist helpers ──
    @staticmethod
    def _zhash(piece: Piece) -> int:
        return ZOBRIST_PIECE.get(
            (piece.team.value, piece.piece_type.value, piece.row, piece.col), 0)

    def hash_with_side(self, team: Team) -> int:
        """side-to-move를 포함한 해시 키"""
        return self.zobrist_hash ^ (ZOBRIST_SIDE if team == Team.HAN else 0)

    # ── 초기 배치 ──
    def setup_initial_position(self, cho_formation="내상외마",
                                han_formation="내상외마"):
        self.grid = [[None]*self.COLS for _ in range(self.ROWS)]
        self.pieces = []
        self.move_history = []
        self.captured_pieces = []
        self.zobrist_hash = 0

        # CHO (rows 0-3)
        self._place(PieceType.KING, Team.CHO, 1, 4)
        self._place(PieceType.GUARD, Team.CHO, 0, 3)
        self._place(PieceType.GUARD, Team.CHO, 0, 5)
        self._place(PieceType.CAR, Team.CHO, 0, 0)
        self._place(PieceType.CAR, Team.CHO, 0, 8)
        self._place(PieceType.CANNON, Team.CHO, 2, 1)
        self._place(PieceType.CANNON, Team.CHO, 2, 7)
        for c in [0,2,4,6,8]:
            self._place(PieceType.PAWN, Team.CHO, 3, c)
        cho_h, cho_e = self._get_formation(cho_formation)
        for c in cho_h: self._place(PieceType.HORSE, Team.CHO, 0, c)
        for c in cho_e: self._place(PieceType.ELEPHANT, Team.CHO, 0, c)

        # HAN (rows 6-9)
        self._place(PieceType.KING, Team.HAN, 8, 4)
        self._place(PieceType.GUARD, Team.HAN, 9, 3)
        self._place(PieceType.GUARD, Team.HAN, 9, 5)
        self._place(PieceType.CAR, Team.HAN, 9, 0)
        self._place(PieceType.CAR, Team.HAN, 9, 8)
        self._place(PieceType.CANNON, Team.HAN, 7, 1)
        self._place(PieceType.CANNON, Team.HAN, 7, 7)
        for c in [0,2,4,6,8]:
            self._place(PieceType.PAWN, Team.HAN, 6, c)
        han_h, han_e = self._get_formation(han_formation)
        for c in han_h: self._place(PieceType.HORSE, Team.HAN, 9, c)
        for c in han_e: self._place(PieceType.ELEPHANT, Team.HAN, 9, c)

    def _get_formation(self, fmt: str):
        fmts = {
            "내상외마": ([1,7],[2,6]),
            "외상내마": ([2,6],[1,7]),
            "좌상우마": ([6,7],[1,2]),
            "우상좌마": ([1,2],[6,7]),
        }
        return fmts.get(fmt, fmts["내상외마"])

    def _place(self, pt: PieceType, team: Team, row: int, col: int):
        p = Piece(piece_type=pt, team=team, row=row, col=col)
        self.grid[row][col] = p
        self.pieces.append(p)
        self.zobrist_hash ^= self._zhash(p)

    # ── 기본 접근 ──
    def get_piece(self, row: int, col: int) -> Optional[Piece]:
        if 0 <= row < self.ROWS and 0 <= col < self.COLS:
            return self.grid[row][col]
        return None

    def get_team_pieces(self, team: Team) -> list[Piece]:
        return [p for p in self.pieces if p.team == team and not p.captured]

    def get_king(self, team: Team) -> Optional[Piece]:
        for p in self.pieces:
            if p.piece_type == PieceType.KING and p.team == team and not p.captured:
                return p
        return None

    # ── 이동 실행 / 되돌리기 ──
    def move_piece(self, fr: int, fc: int, tr: int, tc: int) -> Optional[Piece]:
        piece = self.grid[fr][fc]
        if piece is None:
            return None

        # Zobrist: 출발지에서 제거
        self.zobrist_hash ^= self._zhash(piece)

        captured = self.grid[tr][tc]
        if captured:
            captured.captured = True
            self.captured_pieces.append(captured)
            # Zobrist: 포획 기물 제거
            self.zobrist_hash ^= ZOBRIST_PIECE.get(
                (captured.team.value, captured.piece_type.value, tr, tc), 0)

        self.grid[fr][fc] = None
        self.grid[tr][tc] = piece
        piece.row = tr
        piece.col = tc

        # Zobrist: 도착지에 배치
        self.zobrist_hash ^= self._zhash(piece)

        # 직접 참조 저장 (undo 시 정확한 기물 복원 보장)
        self.move_history.append((fr, fc, tr, tc, captured))
        return captured

    def undo_move(self) -> bool:
        if not self.move_history:
            return False

        fr, fc, tr, tc, captured = self.move_history.pop()

        piece = self.grid[tr][tc]
        if piece is None:
            return False

        # Zobrist: 현재 위치 제거
        self.zobrist_hash ^= self._zhash(piece)

        self.grid[tr][tc] = None
        self.grid[fr][fc] = piece
        piece.row = fr
        piece.col = fc

        # Zobrist: 원래 위치에 배치
        self.zobrist_hash ^= self._zhash(piece)

        if captured is not None:
            captured.captured = False
            self.grid[tr][tc] = captured
            # Zobrist: 포획 기물 복원
            self.zobrist_hash ^= ZOBRIST_PIECE.get(
                (captured.team.value, captured.piece_type.value, tr, tc), 0)
            if captured in self.captured_pieces:
                self.captured_pieces.remove(captured)
        return True

    # ── 유효 이동 ──
    def get_valid_moves(self, piece: Piece) -> list[tuple[int,int]]:
        if piece.captured:
            return []
        raw = self._get_raw_moves(piece)
        valid = [(r,c) for r,c in raw
                 if self.grid[r][c] is None or self.grid[r][c].team != piece.team]
        return [m for m in valid if self._is_move_safe(piece, m[0], m[1])]

    def _is_move_safe(self, piece: Piece, tr: int, tc: int) -> bool:
        fr, fc = piece.row, piece.col
        captured = self.grid[tr][tc]

        self.grid[fr][fc] = None
        self.grid[tr][tc] = piece
        piece.row = tr
        piece.col = tc
        if captured:
            captured.captured = True

        safe = not self.is_in_check(piece.team)

        self.grid[tr][tc] = captured
        self.grid[fr][fc] = piece
        piece.row = fr
        piece.col = fc
        if captured:
            captured.captured = False
        return safe

    def _get_raw_moves(self, piece: Piece) -> list[tuple[int,int]]:
        r, c = piece.row, piece.col
        pt = piece.piece_type
        if pt == PieceType.KING:   return self._king_moves(r, c, piece.team)
        if pt == PieceType.GUARD:  return self._guard_moves(r, c, piece.team)
        if pt == PieceType.CAR:    return self._car_moves(r, c)
        if pt == PieceType.CANNON: return self._cannon_moves(r, c)
        if pt == PieceType.HORSE:  return self._horse_moves(r, c)
        if pt == PieceType.ELEPHANT: return self._elephant_moves(r, c)
        if pt == PieceType.PAWN:   return self._pawn_moves(r, c, piece.team)
        return []

    # ── 기물별 이동 규칙 ──
    def _king_moves(self, r, c, team):
        palace = PALACE_CHO if team == Team.CHO else PALACE_HAN
        moves = []
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r+dr, c+dc
            if (nr, nc) in palace:
                moves.append((nr, nc))
        if (r, c) in PALACE_DIAG:
            for nr, nc in PALACE_DIAG[(r, c)]:
                if (nr, nc) in palace:
                    moves.append((nr, nc))
        return moves

    def _guard_moves(self, r, c, team):
        palace = PALACE_CHO if team == Team.CHO else PALACE_HAN
        moves = []
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r+dr, c+dc
            if (nr, nc) in palace:
                moves.append((nr, nc))
        if (r, c) in PALACE_DIAG:
            for nr, nc in PALACE_DIAG[(r, c)]:
                if (nr, nc) in palace:
                    moves.append((nr, nc))
        return moves

    def _car_moves(self, r, c):
        """차: 직선 무제한 + 궁성 대각선 슬라이딩 (양쪽 궁성)"""
        moves = []
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r+dr, c+dc
            while 0 <= nr < self.ROWS and 0 <= nc < self.COLS:
                if self.grid[nr][nc] is None:
                    moves.append((nr, nc))
                else:
                    moves.append((nr, nc))  # 포획 가능
                    break
                nr += dr; nc += dc
        # 궁성 대각선 슬라이딩 (양쪽 궁성 모두)
        if (r, c) in PALACE_SLIDE:
            for path in PALACE_SLIDE[(r, c)]:
                for pr, pc in path:
                    target = self.grid[pr][pc]
                    if target is None:
                        moves.append((pr, pc))
                    else:
                        moves.append((pr, pc))  # 포획
                        break
        return moves

    def _cannon_moves(self, r, c):
        """포: 직선에서 1개 넘어 착지/포획 + 궁성 대각선 점프. 포끼리 불가."""
        moves = []
        # 직선
        for dr, dc in [(-1,0),(1,0),(0,-1),(0,1)]:
            nr, nc = r+dr, c+dc
            jumped = False
            while 0 <= nr < self.ROWS and 0 <= nc < self.COLS:
                target = self.grid[nr][nc]
                if not jumped:
                    if target is not None:
                        if target.piece_type == PieceType.CANNON:
                            break  # 포는 포를 넘을 수 없음
                        jumped = True
                else:
                    if target is None:
                        moves.append((nr, nc))
                    else:
                        if target.piece_type != PieceType.CANNON:
                            moves.append((nr, nc))
                        break
                nr += dr; nc += dc
        # 궁성 대각선 점프
        if (r, c) in PALACE_SLIDE:
            for path in PALACE_SLIDE[(r, c)]:
                if len(path) >= 2:
                    # 첫 칸이 스크린, 두 번째 칸이 착지점
                    screen = self.grid[path[0][0]][path[0][1]]
                    if screen is not None and screen.piece_type != PieceType.CANNON:
                        target = self.grid[path[1][0]][path[1][1]]
                        if target is None:
                            moves.append(path[1])
                        elif target.piece_type != PieceType.CANNON:
                            moves.append(path[1])
                # len==1: 포가 중앙에 있고 스크린 없이 코너로 이동 불가
        return moves

    def _horse_moves(self, r, c):
        moves = []
        steps = [
            ((-1,0),(-2,-1)),((-1,0),(-2,1)),
            ((1,0),(2,-1)),((1,0),(2,1)),
            ((0,-1),(-1,-2)),((0,-1),(1,-2)),
            ((0,1),(-1,2)),((0,1),(1,2)),
        ]
        for (dr1,dc1),(dr2,dc2) in steps:
            mr, mc = r+dr1, c+dc1
            if 0<=mr<self.ROWS and 0<=mc<self.COLS and self.grid[mr][mc] is None:
                nr, nc = r+dr2, c+dc2
                if 0<=nr<self.ROWS and 0<=nc<self.COLS:
                    moves.append((nr, nc))
        return moves

    def _elephant_moves(self, r, c):
        moves = []
        steps = [
            ((-1,0),(-2,-1),(-3,-2)),((-1,0),(-2,1),(-3,2)),
            ((1,0),(2,-1),(3,-2)),((1,0),(2,1),(3,2)),
            ((0,-1),(-1,-2),(-2,-3)),((0,-1),(1,-2),(2,-3)),
            ((0,1),(-1,2),(-2,3)),((0,1),(1,2),(2,3)),
        ]
        for (d1r,d1c),(d2r,d2c),(d3r,d3c) in steps:
            m1r, m1c = r+d1r, c+d1c
            if not (0<=m1r<self.ROWS and 0<=m1c<self.COLS): continue
            if self.grid[m1r][m1c] is not None: continue
            m2r, m2c = r+d2r, c+d2c
            if not (0<=m2r<self.ROWS and 0<=m2c<self.COLS): continue
            if self.grid[m2r][m2c] is not None: continue
            nr, nc = r+d3r, c+d3c
            if 0<=nr<self.ROWS and 0<=nc<self.COLS:
                moves.append((nr, nc))
        return moves

    def _pawn_moves(self, r, c, team):
        """졸/병: 전진 + 좌우 + 궁성 대각선 전진"""
        moves = []
        fwd = 1 if team == Team.CHO else -1
        nr = r + fwd
        if 0 <= nr < self.ROWS:
            moves.append((nr, c))
        for dc in [-1, 1]:
            nc = c + dc
            if 0 <= nc < self.COLS:
                moves.append((r, nc))
        # 궁성 대각선 전진 (적 궁성에서)
        if (r, c) in PALACE_DIAG:
            for dr, dc_ in PALACE_DIAG[(r, c)]:
                if (dr - r) == fwd or (dr - r) * fwd > 0:
                    # 전진 방향의 대각선만
                    if (dr - r) == fwd:
                        moves.append((dr, dc_))
        return moves

    # ── 장군 / 빅장 / 외통 ──
    def is_in_check(self, team: Team) -> bool:
        """해당 팀의 왕이 장군인지 확인 (빅장 제외) - 고속 역방향 탐지"""
        king = self.get_king(team)
        if king is None:
            return True
        enemy = Team.HAN if team == Team.CHO else Team.CHO
        return self._is_square_attacked(king.row, king.col, enemy)

    def _is_square_attacked(self, kr: int, kc: int, by_team: Team) -> bool:
        """(kr, kc)가 by_team에 의해 공격받는지 역방향 검사 (고속)"""
        ROWS, COLS = self.ROWS, self.COLS
        grid = self.grid

        # 1. 직선: 차 & 포 (4방향 레이 스캔)
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = kr + dr, kc + dc
            screen_found = False
            while 0 <= nr < ROWS and 0 <= nc < COLS:
                p = grid[nr][nc]
                if p is not None:
                    if not screen_found:
                        if p.team == by_team and p.piece_type == PieceType.CAR:
                            return True
                        if p.piece_type == PieceType.CANNON:
                            break  # 포는 스크린 불가
                        screen_found = True
                    else:
                        if p.team == by_team and p.piece_type == PieceType.CANNON:
                            return True
                        break
                nr += dr
                nc += dc

        # 2. 마 공격 (역 L자)
        for (dr, dc), (br, bc) in (
            ((-2, -1), (-1, 0)), ((-2, 1), (-1, 0)),
            ((2, -1), (1, 0)),   ((2, 1), (1, 0)),
            ((-1, -2), (0, -1)), ((1, -2), (0, -1)),
            ((-1, 2), (0, 1)),   ((1, 2), (0, 1)),
        ):
            nr, nc = kr + dr, kc + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                mr, mc = kr + br, kc + bc
                if 0 <= mr < ROWS and 0 <= mc < COLS and grid[mr][mc] is None:
                    p = grid[nr][nc]
                    if p is not None and p.team == by_team and p.piece_type == PieceType.HORSE:
                        return True

        # 3. 상 공격 (역 대각선)
        for (dr, dc), (b1r, b1c), (b2r, b2c) in (
            ((-3, -2), (-1, 0), (-2, -1)), ((-3, 2), (-1, 0), (-2, 1)),
            ((3, -2), (1, 0), (2, -1)),     ((3, 2), (1, 0), (2, 1)),
            ((-2, -3), (0, -1), (-1, -2)),  ((2, -3), (0, -1), (1, -2)),
            ((-2, 3), (0, 1), (-1, 2)),     ((2, 3), (0, 1), (1, 2)),
        ):
            nr, nc = kr + dr, kc + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                m1r, m1c = kr + b1r, kc + b1c
                m2r, m2c = kr + b2r, kc + b2c
                if (0 <= m1r < ROWS and 0 <= m1c < COLS and grid[m1r][m1c] is None
                        and 0 <= m2r < ROWS and 0 <= m2c < COLS and grid[m2r][m2c] is None):
                    p = grid[nr][nc]
                    if p is not None and p.team == by_team and p.piece_type == PieceType.ELEPHANT:
                        return True

        # 4. 졸/병 공격 (전진 + 좌우)
        pawn_fwd = 1 if by_team == Team.CHO else -1
        pr = kr - pawn_fwd
        if 0 <= pr < ROWS:
            p = grid[pr][kc]
            if p is not None and p.team == by_team and p.piece_type == PieceType.PAWN:
                return True
        for dc in (-1, 1):
            nc = kc + dc
            if 0 <= nc < COLS:
                p = grid[kr][nc]
                if p is not None and p.team == by_team and p.piece_type == PieceType.PAWN:
                    return True

        # 5. 왕/사 공격 (인접 + 궁성 대각선)
        for dr, dc in ((-1, 0), (1, 0), (0, -1), (0, 1)):
            nr, nc = kr + dr, kc + dc
            if 0 <= nr < ROWS and 0 <= nc < COLS:
                p = grid[nr][nc]
                if p is not None and p.team == by_team and p.piece_type in (PieceType.KING, PieceType.GUARD):
                    return True
        if (kr, kc) in PALACE_DIAG:
            for nr, nc in PALACE_DIAG[(kr, kc)]:
                p = grid[nr][nc]
                if p is not None and p.team == by_team:
                    if p.piece_type in (PieceType.KING, PieceType.GUARD):
                        return True
                    # 졸의 궁성 대각선 전진 공격
                    if p.piece_type == PieceType.PAWN and (nr - kr) == -pawn_fwd:
                        return True

        # 6. 궁성 대각선 슬라이딩 (차/포)
        if (kr, kc) in PALACE_SLIDE:
            for path in PALACE_SLIDE[(kr, kc)]:
                screen = False
                for pr_, pc_ in path:
                    p = grid[pr_][pc_]
                    if p is not None:
                        if not screen:
                            if p.team == by_team and p.piece_type == PieceType.CAR:
                                return True
                            if p.piece_type == PieceType.CANNON:
                                break
                            screen = True
                        else:
                            if p.team == by_team and p.piece_type == PieceType.CANNON:
                                return True
                            break

        return False

    def is_bikjang(self) -> bool:
        """빅장: 두 왕이 같은 열에서 사이 기물 없이 마주봄 (무승부 기회)"""
        cho_k = self.get_king(Team.CHO)
        han_k = self.get_king(Team.HAN)
        if cho_k is None or han_k is None:
            return False
        if cho_k.col != han_k.col:
            return False
        lo = min(cho_k.row, han_k.row)
        hi = max(cho_k.row, han_k.row)
        for row in range(lo+1, hi):
            if self.grid[row][cho_k.col] is not None:
                return False
        return True

    def is_checkmate(self, team: Team) -> bool:
        """해당 팀이 합법적 수가 없는 상태"""
        for piece in self.get_team_pieces(team):
            if self.get_valid_moves(piece):
                return False
        return True

    def get_all_valid_moves(self, team: Team) -> list[tuple[Piece,int,int]]:
        result = []
        for piece in self.get_team_pieces(team):
            for r, c in self.get_valid_moves(piece):
                result.append((piece, r, c))
        return result

    # ── 빠른 공격 이동 생성 (포획수만, Quiescence 용) ──
    def get_capture_moves(self, team: Team) -> list[tuple[Piece,int,int]]:
        """포획 이동만 반환 (Quiescence Search용)"""
        result = []
        for piece in self.get_team_pieces(team):
            if piece.captured:
                continue
            raw = self._get_raw_moves(piece)
            for r, c in raw:
                target = self.grid[r][c]
                if target and target.team != piece.team:
                    if self._is_move_safe(piece, r, c):
                        result.append((piece, r, c))
        return result

    # ── 복사 / 직렬화 ──
    def copy(self) -> "Board":
        nb = Board()
        nb.pieces = []
        nb.grid = [[None]*self.COLS for _ in range(self.ROWS)]
        pmap = {}
        for p in self.pieces:
            np_ = p.copy()
            nb.pieces.append(np_)
            pmap[id(p)] = np_
            if not np_.captured:
                nb.grid[np_.row][np_.col] = np_
        # move_history: 포획 기물 참조를 새 보드 기물로 매핑
        nb.move_history = []
        for fr, fc, tr, tc, cap in self.move_history:
            new_cap = pmap.get(id(cap)) if cap is not None else None
            nb.move_history.append((fr, fc, tr, tc, new_cap))
        nb.captured_pieces = [pmap[id(p)] for p in self.captured_pieces if id(p) in pmap]
        nb.zobrist_hash = self.zobrist_hash
        return nb

    def to_matrix(self) -> list[list[Optional[dict]]]:
        return [[p.to_dict() if p else None for p in row] for row in self.grid]

    def to_state_string(self) -> str:
        """보드 상태 문자열 (하위 호환용)"""
        st = []
        for r in range(self.ROWS):
            for c in range(self.COLS):
                p = self.grid[r][c]
                if p:
                    # 포/차 구분을 위해 2글자 접두사
                    tv = p.team.value[0]      # 'c' or 'h'
                    pv = p.piece_type.value[:2]  # 'ki','ca','co','ho','el','gu','pa'
                    st.append(f"{tv}{pv}{r}{c}")
                else:
                    st.append("__")
        return "|".join(st)

    # ── 기물 개수 (게임 페이즈 판단용) ──
    def count_pieces(self) -> int:
        return sum(1 for p in self.pieces if not p.captured)

    def count_material(self, team: Team) -> int:
        return sum(p.value for p in self.get_team_pieces(team))
