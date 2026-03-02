"""탐색 알고리즘 모듈 (대폭 개선판)

Negamax + Alpha-Beta + PVS + Quiescence Search + Null Move Pruning
+ Iterative Deepening + Transposition Table (Zobrist) + History Heuristic
+ Check Extensions + Late Move Reductions + Aspiration Windows
"""
import time
import math
import random
from typing import Optional
from .board import Board, ZOBRIST_SIDE
from .pieces import Piece, PieceType, Team
from .evaluator import Evaluator
from .opening_book import OpeningBook


class SearchTimeout(Exception):
    """탐색 시간 초과 예외"""
    pass


class TranspositionEntry:
    __slots__ = ("score", "depth", "flag", "best_move")

    def __init__(self, score: float, depth: int, flag: str, best_move=None):
        self.score = score
        self.depth = depth
        self.flag = flag   # "exact", "upper", "lower"
        self.best_move = best_move  # (fr, fc, tr, tc)


# Transposition Table 최대 크기
TT_MAX_SIZE = 2_000_000
CHECKMATE_SCORE = 30000.0
MAX_QUIESCENCE_DEPTH = 6


class SearchEngine:
    """고성능 장기 AI 탐색 엔진"""

    def __init__(self, max_depth: int = 20, time_limit: float = 5.0):
        self.max_depth = max_depth
        self.time_limit = time_limit
        self.evaluator = Evaluator()
        self.opening_book = OpeningBook()

        # Transposition Table (Zobrist 키 기반)
        self.tt: dict[int, TranspositionEntry] = {}

        # Killer moves (depth별 2개)
        self.killers: list[list[Optional[tuple]]] = [
            [None, None] for _ in range(64)
        ]

        # History heuristic (team, fr, fc, tr, tc → 점수)
        self.history: dict[tuple, int] = {}

        # 반복 탐지 (게임 중 나타난 포지션 해시)
        self.position_history: list[int] = []

        # 탐색 통계
        self.nodes = 0
        self.start_time = 0.0
        self.timeout = False
        self.current_depth = 0
        self.game_phase = "midgame"

    def record_position(self, board: Board, team: Team):
        """현재 포지션을 이력에 기록 (매 수 후 호출)"""
        self.position_history.append(board.hash_with_side(team))

    def find_best_move(self, board: Board, team: Team,
                        phase: str = "midgame",
                        move_count: int = 0) -> dict:
        """최적 수 탐색 (Iterative Deepening + Aspiration Windows)"""
        self.nodes = 0
        self.start_time = time.time()
        self.timeout = False
        self.game_phase = phase

        # 반복 탐지용 해시 세트 (O(1) 룩업)
        self._pos_set = set(self.position_history)

        # 킬러 무브/히스토리 초기화
        for i in range(len(self.killers)):
            self.killers[i] = [None, None]
        self.history.clear()

        all_moves = board.get_all_valid_moves(team)
        if not all_moves:
            return {"move": None, "score": -math.inf, "depth": 0,
                    "nodes": 0, "candidates": []}

        # 오프닝 북 조회 (초반에만)
        valid_set = {(p.row, p.col, r, c) for p, r, c in all_moves}
        book_move = self.opening_book.get_book_move(
            board, team, move_count, valid_set)
        if book_move:
            return {
                "move": book_move,
                "score": 0.0,
                "depth": 0,
                "nodes": 0,
                "candidates": [],
                "book": True,
                "time": round(time.time() - self.start_time, 3),
            }

        if len(all_moves) == 1:
            p, tr, tc = all_moves[0]
            return {
                "move": {"from": (p.row, p.col), "to": (tr, tc), "piece": p.to_dict()},
                "score": 0.0, "depth": 1, "nodes": 1, "candidates": [],
            }

        best_result = None
        prev_score = 0.0

        for depth in range(1, self.max_depth + 1):
            self.current_depth = depth
            elapsed = time.time() - self.start_time

            # 남은 시간이 부족하면 새 반복 시작하지 않음
            if elapsed > self.time_limit * 0.6:
                break

            try:
                # Aspiration Window
                if depth >= 4 and best_result:
                    window = 50.0
                    alpha = prev_score - window
                    beta = prev_score + window
                    result = self._search_root(board, team, depth, alpha, beta)

                    # Window 실패 시 전체 탐색
                    if result and (result["score"] <= alpha or result["score"] >= beta):
                        result = self._search_root(board, team, depth,
                                                    -math.inf, math.inf)
                else:
                    result = self._search_root(board, team, depth,
                                                -math.inf, math.inf)

                if result and result["move"]:
                    best_result = result
                    best_result["depth"] = depth
                    prev_score = result["score"]

            except SearchTimeout:
                break

        if best_result is None:
            p, tr, tc = random.choice(all_moves)
            best_result = {
                "move": {"from": (p.row, p.col), "to": (tr, tc), "piece": p.to_dict()},
                "score": 0.0, "depth": 0, "nodes": self.nodes, "candidates": [],
            }

        # ── 반환 전 합법수 검증 ──
        best_result = self._validate_move(board, team, best_result, all_moves)

        best_result["time"] = round(time.time() - self.start_time, 3)
        best_result["nodes"] = self.nodes
        return best_result

    def _search_root(self, board: Board, team: Team, depth: int,
                      alpha: float, beta: float) -> Optional[dict]:
        """루트 레벨 탐색 (PVS)"""
        all_moves = board.get_all_valid_moves(team)
        if not all_moves:
            return None

        all_moves = self._order_moves(board, all_moves, team, depth)
        enemy = Team.HAN if team == Team.CHO else Team.CHO

        best_score = -math.inf
        best_move = None
        candidates = []
        first = True

        for piece, tr, tc in all_moves:
            self._check_time()
            fr, fc = piece.row, piece.col

            # 이동 실행 + try/finally로 undo 보장 (SearchTimeout 안전)
            board.move_piece(fr, fc, tr, tc)
            try:
                gives_check = board.is_in_check(enemy)

                if first:
                    score = -self._negamax(board, enemy, depth - 1, -beta, -alpha,
                                            gives_check)
                    first = False
                else:
                    score = -self._negamax(board, enemy, depth - 1,
                                            -alpha - 0.01, -alpha, gives_check)
                    if alpha < score < beta:
                        score = -self._negamax(board, enemy, depth - 1,
                                                -beta, -alpha, gives_check)
            finally:
                board.undo_move()

            candidates.append({
                "from": (fr, fc), "to": (tr, tc),
                "piece": piece.to_dict(), "score": round(score, 2),
            })

            if score > best_score:
                best_score = score
                best_move = {
                    "from": (fr, fc), "to": (tr, tc), "piece": piece.to_dict(),
                }

            if score > alpha:
                alpha = score

        candidates.sort(key=lambda x: x["score"], reverse=True)
        return {
            "move": best_move,
            "score": round(best_score, 2),
            "candidates": candidates[:5],
        }

    def _negamax(self, board: Board, team: Team, depth: int,
                  alpha: float, beta: float,
                  in_check: bool = False) -> float:
        """Negamax + Alpha-Beta + PVS + Null Move + Extensions"""
        self.nodes += 1

        # 시간 체크 (매 4096 노드)
        if self.nodes & 4095 == 0:
            self._check_time()

        # ── TT 조회 (Zobrist) ──
        tt_key = board.hash_with_side(team)

        # ── 반복 탐지: 이미 나타난 포지션이면 무승부 점수 ──
        if tt_key in self._pos_set:
            return 0.0

        entry = self.tt.get(tt_key)
        tt_move = None

        if entry and entry.depth >= depth:
            if entry.flag == "exact":
                return entry.score
            elif entry.flag == "lower" and entry.score >= beta:
                return entry.score
            elif entry.flag == "upper" and entry.score <= alpha:
                return entry.score
            if entry.best_move:
                tt_move = entry.best_move

        # ── 깊이 한계: Quiescence Search ──
        if depth <= 0:
            return self._quiescence(board, team, alpha, beta, MAX_QUIESCENCE_DEPTH)

        # ── 합법수 생성 (체크메이트/합법수 없음 동시 확인) ──
        all_moves = board.get_all_valid_moves(team)
        if not all_moves:
            # 합법수 없음 = 체크메이트 또는 스테일메이트 (장기에서는 둘 다 패배)
            return -CHECKMATE_SCORE + (self.current_depth - depth)

        # ── Null Move Pruning (장군 상태가 아닐 때만) ──
        if (not in_check and depth >= 3
                and len(all_moves) > 5):
            R = 2 if depth < 6 else 3
            enemy = Team.HAN if team == Team.CHO else Team.CHO
            # 턴 넘기기 (null move)
            null_score = -self._negamax(board, enemy, depth - 1 - R,
                                         -beta, -beta + 0.01, False)
            if null_score >= beta:
                return beta

        # ── 이동 정렬 ──
        all_moves = self._order_moves(board, all_moves, team, depth, tt_move)
        enemy = Team.HAN if team == Team.CHO else Team.CHO

        best_score = -math.inf
        best_move_coords = None
        flag = "upper"
        first = True
        moves_searched = 0

        for piece, tr, tc in all_moves:
            fr, fc = piece.row, piece.col
            is_capture = board.grid[tr][tc] is not None

            # 이동 실행 + try/finally로 undo 보장 (SearchTimeout 안전)
            board.move_piece(fr, fc, tr, tc)
            try:
                gives_check = board.is_in_check(enemy)
                ext = 1 if gives_check and depth >= 2 else 0

                reduction = 0
                if (moves_searched >= 4 and depth >= 3
                        and not in_check and not is_capture
                        and not gives_check):
                    reduction = 1 if moves_searched < 8 else 2

                if first:
                    score = -self._negamax(board, enemy, depth - 1 + ext,
                                            -beta, -alpha, gives_check)
                    first = False
                else:
                    score = -self._negamax(board, enemy,
                                            depth - 1 + ext - reduction,
                                            -alpha - 0.01, -alpha, gives_check)
                    if score > alpha:
                        score = -self._negamax(board, enemy, depth - 1 + ext,
                                                -beta, -alpha, gives_check)
            finally:
                board.undo_move()
            moves_searched += 1

            if score > best_score:
                best_score = score
                best_move_coords = (fr, fc, tr, tc)

            if score >= beta:
                # Beta cutoff
                if not is_capture:
                    self._update_killers(depth, fr, fc, tr, tc)
                    self._update_history(team, fr, fc, tr, tc, depth)
                flag = "lower"
                break

            if score > alpha:
                alpha = score
                flag = "exact"

        # ── TT 저장 ──
        self._store_tt(tt_key, best_score, depth, flag, best_move_coords)

        return best_score

    def _quiescence(self, board: Board, team: Team,
                     alpha: float, beta: float, depth: int) -> float:
        """Quiescence Search: 포획수만 탐색하여 수평선 효과 방지"""
        self.nodes += 1

        if self.nodes & 4095 == 0:
            self._check_time()

        # 장군 상태이면 모든 합법수를 탐색해야 함
        in_check = board.is_in_check(team)
        if in_check:
            # 깊이 한계 도달 시 정적 평가 반환 (무한 재귀 방지)
            if depth <= -MAX_QUIESCENCE_DEPTH:
                return self.evaluator.evaluate(board, team, self.game_phase)
            all_moves = board.get_all_valid_moves(team)
            if not all_moves:
                return -CHECKMATE_SCORE + self.current_depth
            enemy = Team.HAN if team == Team.CHO else Team.CHO
            best = -math.inf
            for piece, tr, tc in all_moves:
                fr, fc = piece.row, piece.col
                board.move_piece(fr, fc, tr, tc)
                try:
                    score = -self._quiescence(board, enemy, -beta, -alpha,
                                               depth - 1)
                finally:
                    board.undo_move()
                if score > best:
                    best = score
                if score >= beta:
                    return beta
                if score > alpha:
                    alpha = score
            return best

        # Stand-pat score (장군이 아닐 때만)
        stand_pat = self.evaluator.evaluate(board, team, self.game_phase)

        if stand_pat >= beta:
            return beta
        if stand_pat > alpha:
            alpha = stand_pat

        if depth <= 0:
            return alpha

        # 포획 이동만 생성
        captures = board.get_capture_moves(team)

        # MVV-LVA 순서로 정렬
        captures.sort(
            key=lambda m: (board.grid[m[1]][m[2]]._value * 10 - m[0]._value
                          if board.grid[m[1]][m[2]] else 0),
            reverse=True
        )

        enemy = Team.HAN if team == Team.CHO else Team.CHO

        for piece, tr, tc in captures:
            fr, fc = piece.row, piece.col
            target = board.grid[tr][tc]

            # Delta pruning
            if target and stand_pat + target._value + 5.0 < alpha:
                continue

            board.move_piece(fr, fc, tr, tc)
            try:
                score = -self._quiescence(board, enemy, -beta, -alpha, depth - 1)
            finally:
                board.undo_move()

            if score >= beta:
                return beta
            if score > alpha:
                alpha = score

        return alpha

    # ── 이동 정렬 ──
    def _order_moves(self, board: Board, moves: list[tuple[Piece,int,int]],
                      team: Team, depth: int,
                      tt_move: Optional[tuple] = None) -> list[tuple[Piece,int,int]]:
        scored = []
        tv = team.value

        for piece, tr, tc in moves:
            score = 0
            fr, fc = piece.row, piece.col

            # 1. TT 최선수 (최우선)
            if tt_move and tt_move == (fr, fc, tr, tc):
                score += 10000

            # 2. 포획수 (MVV-LVA)
            target = board.grid[tr][tc]
            if target and target.team != piece.team:
                score += 5000 + target.value * 10 - piece.value

            # 3. Killer moves
            if depth < len(self.killers):
                for km in self.killers[depth]:
                    if km and km == (fr, fc, tr, tc):
                        score += 3000
                        break

            # 4. History heuristic
            h_key = (tv, fr, fc, tr, tc)
            score += self.history.get(h_key, 0)

            scored.append((score, piece, tr, tc))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [(p, r, c) for _, p, r, c in scored]

    # ── 보조 함수 ──
    def _check_time(self):
        if time.time() - self.start_time > self.time_limit:
            self.timeout = True
            raise SearchTimeout()

    def _update_killers(self, depth: int, fr, fc, tr, tc):
        if depth < len(self.killers):
            move = (fr, fc, tr, tc)
            if self.killers[depth][0] != move:
                self.killers[depth][1] = self.killers[depth][0]
                self.killers[depth][0] = move

    def _update_history(self, team, fr, fc, tr, tc, depth):
        key = (team.value, fr, fc, tr, tc)
        self.history[key] = self.history.get(key, 0) + depth * depth

    def _store_tt(self, key: int, score: float, depth: int,
                   flag: str, best_move: Optional[tuple]):
        # 크기 제한 (간단한 항상-대체 정책)
        if len(self.tt) > TT_MAX_SIZE:
            # 절반 삭제 (오래된 엔트리)
            keys = list(self.tt.keys())
            for k in keys[:TT_MAX_SIZE // 2]:
                del self.tt[k]

        self.tt[key] = TranspositionEntry(score, depth, flag, best_move)

    def clear_tt(self):
        """TT 초기화 (새 게임 시)"""
        self.tt.clear()
        self.position_history.clear()

    def _validate_move(self, board: Board, team: Team,
                        result: dict, all_moves: list) -> dict:
        """반환 수가 합법인지 검증. 불법이면 합법수로 대체."""
        move = result.get("move")
        if not move:
            return result

        fr, fc = move["from"]
        tr, tc = move["to"]

        # all_moves에서 좌표 매칭으로 검증
        valid_set = set()
        for p, r, c in all_moves:
            valid_set.add((p.row, p.col, r, c))

        if (fr, fc, tr, tc) in valid_set:
            return result

        # 불법수 감지 — 합법수 중 최선을 재선택
        # candidates에서 합법수 찾기
        for cand in result.get("candidates", []):
            cfr, cfc = cand["from"]
            ctr, ctc = cand["to"]
            if (cfr, cfc, ctr, ctc) in valid_set:
                result["move"] = {
                    "from": (cfr, cfc), "to": (ctr, ctc),
                    "piece": cand["piece"],
                }
                result["score"] = cand["score"]
                return result

        # candidates에도 합법수 없으면 랜덤
        p, r, c = random.choice(all_moves)
        result["move"] = {
            "from": (p.row, p.col), "to": (r, c),
            "piece": p.to_dict(),
        }
        result["score"] = 0.0
        return result

    def get_search_stats(self) -> dict:
        return {
            "nodes_searched": self.nodes,
            "transposition_size": len(self.tt),
            "time_elapsed": round(time.time() - self.start_time, 3),
        }
