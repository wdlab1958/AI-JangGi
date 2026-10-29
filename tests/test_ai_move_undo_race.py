"""F1 재현 테스트 — formal/ai-move-undo-race (WDLAB-STD-VERIFY-001 G6)

TLC 반례(formal/ai-move-undo-race/evidence/tlc_bug*.log)를 결정적으로 재현한다.
게이트(threading.Event)를 모델의 action 경계와 같은 지점에 꽂는다:

  - AiSearchPush 직후 = SearchEngine._negamax 의 첫 호출.
    _search_root 가 투기적 수 1개를 *실제* game.board 에 push 한 직후이다
    (backend/engine/search.py:195 → :201). 이 지점에서 워커 스레드를 세워 두고,
    이벤트 루프 스레드가 하던 일(undo / move / 두 번째 ai_move)을 메인 스레드에서 수행한다.

ai_move 는 서버와 같은 방식(별도 스레드; asyncio.to_thread 와 동일)으로 실행한다.
외부 서비스는 없다. 장기기억은 pytest tmp_path 에 쓴다.

속성(동결, formal/ai-move-undo-race/tla/Properties.tla):
  P1 TurnParity       : current_turn == CHO  <=>  move_count 짝수   (사람=CHO 선수)
  P2 RecordAlternates : 정지 상태에서 수 기록은 홀수번째=CHO, 짝수번째=HAN, 길이 == move_count
"""
import logging
import os
import sys
import threading

# 테스트 하네스 우회: CPython 3.12.11 에서 워커 스레드가 logger.warning() 을 호출하면
# logging.LogRecord.__init__ 의 asyncio.current_task() 조회가 세그폴트를 일으켜(pytest 하에서 재현)
# 프로세스가 죽는다. 속성 검증과 무관한 로그 레코드 필드(taskName)만 끄는 것이므로 결과에 영향 없음.
logging.logAsyncioTasks = False

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engine.board import Board
from backend.engine.pieces import Team
from backend.orchestrator.orchestrator import JanggiOrchestrator


# ─────────────────────────── helpers ───────────────────────────

def _side_to_move(move_count: int) -> Team:
    """P1: 선수(CHO)가 먼저, 교대로 → 짝수 수에서는 CHO 차례."""
    return Team.CHO if move_count % 2 == 0 else Team.HAN


def _replay_movers(game):
    """보드의 move_history 를 초기 배치에서 재생하여 각 수의 mover 를 복원한다 (P2 검사용)."""
    b = Board()
    b.setup_initial_position()
    movers = []
    for (fr, fc, tr, tc, _cap) in game.board.move_history:
        p = b.get_piece(fr, fc)
        movers.append(p.team if p else None)
        if p is not None:
            b.move_piece(fr, fc, tr, tc)
    return movers


def _assert_record_alternates(game, context: str):
    """P2 RecordAlternates (frozen)."""
    movers = _replay_movers(game)
    expected = [_side_to_move(i) for i in range(len(movers))]
    detail = (f"{context}: move_count={game.move_count}, "
              f"len(move_history)={len(game.board.move_history)}, "
              f"movers={[m.value if m else None for m in movers]}, "
              f"current_turn={game.current_turn.value}")
    assert len(game.board.move_history) == game.move_count, "P2 violated (length): " + detail
    assert movers == expected, "P2 violated (record does not alternate CHO/HAN): " + detail


def _assert_turn_parity(game, context: str):
    """P1 TurnParity (frozen)."""
    assert game.current_turn == _side_to_move(game.move_count), (
        f"P1 TurnParity violated — {context}: move_count={game.move_count}, "
        f"current_turn={game.current_turn.value}, "
        f"expected={_side_to_move(game.move_count).value}")


class _Gate:
    def __init__(self):
        self.reached = threading.Event()
        self.release = threading.Event()


def _gate_first_negamax(engine, gate: _Gate):
    """SearchEngine._negamax 첫 호출에서 멈춘다 = 투기적 수 1개가 실제 보드에 올라간 시점."""
    orig = engine._negamax
    fired = threading.Event()

    def gated(board, team, depth, alpha, beta, in_check=False):
        if not fired.is_set():
            fired.set()
            gate.reached.set()
            gate.release.wait(timeout=15)
        return orig(board, team, depth, alpha, beta, in_check)

    engine._negamax = gated


class _AiWorker(threading.Thread):
    """서버의 `await asyncio.to_thread(orchestrator.ai_move, game_id)` 와 동일한 실행."""

    def __init__(self, orch, gid):
        super().__init__(daemon=True)
        self.orch, self.gid = orch, gid
        self.result, self.exc = None, None

    def run(self):
        try:
            self.result = self.orch.ai_move(self.gid)
        except Exception as e:  # noqa: BLE001 — 재현 목적으로 모두 기록
            self.exc = e


def _new_game(tmp_path):
    orch = JanggiOrchestrator(ai_depth=2, ai_time_limit=1.0, storage_dir=str(tmp_path))
    state = orch.create_game()  # human = CHO (선수), AI = HAN
    gid = state["game_id"]
    game = orch.games[gid]
    # 오프닝 북이 탐색을 건너뛰면 게이트에 도달하지 못하므로 비활성화 (실제 탐색 경로 강제)
    orch.strategy_analyst.search_engine.opening_book.get_book_move = lambda *a, **k: None
    game.search_engine.opening_book.get_book_move = lambda *a, **k: None
    return orch, gid, game


def _play_h_a_h(orch, gid, game):
    """H1 A1 H2 → move_count=3, HAN(AI) 차례. 졸 전진만 사용(빅장·외통 불가)."""
    r = orch.human_move(gid, 3, 0, 4, 0)          # H1: 초 졸 (3,0)→(4,0)
    assert r["success"], r
    r = orch.ai_move(gid)                          # A1 (동기 실행)
    assert r["success"], r
    r = orch.human_move(gid, 3, 8, 4, 8)           # H2: 초 졸 (3,8)→(4,8)
    assert r["success"], r
    assert game.move_count == 3 and game.current_turn == Team.HAN
    _assert_record_alternates(game, "setup")


# ─────────────────────────── F1 reproductions ───────────────────────────

def test_F1a_undo_during_ai_search_breaks_turn_parity(tmp_path):
    """TLC trace MC_bug (8 steps): H, A, H, [ai_move in flight], Undo → turn=H but move_count=1.

    실코드: AI 가 '사고 중'(워커 스레드가 탐색 중)일 때 POST /api/game/{id}/undo.
    """
    orch, gid, game = _new_game(tmp_path)
    _play_h_a_h(orch, gid, game)

    gate = _Gate()
    _gate_first_negamax(orch.strategy_analyst.search_engine, gate)
    worker = _AiWorker(orch, gid)
    worker.start()
    try:
        assert gate.reached.wait(10), "search gate not reached (opening book? no search?)"
        # 워커는 투기적 수 1개를 실제 보드에 올려 둔 채 멈춰 있다.
        undo = orch.undo_move(gid)   # ← 이벤트 루프 스레드에서 들어온 undo (routes.py:139-146)

        _assert_turn_parity(game, f"right after undo during AI search (undo={undo})")
        assert not undo.get("success"), f"undo must be rejected while AI is thinking: {undo}"
    finally:
        gate.release.set()
        worker.join(20)


def test_F1b_undo_then_human_move_during_ai_search_corrupts_record(tmp_path):
    """TLC trace MC_bug_record (9 steps): ..., Undo, HumanMove → record <<H, H>> / 사람 수 소실, AI 2수.

    실코드: undo 가 받아들여져 '사람 차례'가 되고 사람이 한 수 더 두면, 멈춰 있던 탐색의
    finally: board.undo_move() 가 그 사람 수를 보드에서 지우고 AI 가 수를 적용한다.
    """
    orch, gid, game = _new_game(tmp_path)
    _play_h_a_h(orch, gid, game)

    gate = _Gate()
    _gate_first_negamax(orch.strategy_analyst.search_engine, gate)
    worker = _AiWorker(orch, gid)
    worker.start()
    try:
        assert gate.reached.wait(10), "search gate not reached"
        undo = orch.undo_move(gid)                       # during AI search
        extra = orch.human_move(gid, 3, 2, 4, 2)         # 사람이 다시 둔다: 초 졸 (3,2)→(4,2)
    finally:
        gate.release.set()
        worker.join(20)

    context = (f"after undo={undo.get('success')} ({undo.get('error')}), "
               f"extra human move={extra.get('success')} ({extra.get('error')}), "
               f"ai={worker.result and worker.result.get('success')} "
               f"({worker.result and worker.result.get('error')}), exc={worker.exc!r}")
    assert worker.exc is None, context
    _assert_record_alternates(game, context)
    _assert_turn_parity(game, context)


def test_F1c_concurrent_ai_move_calls_apply_two_ai_moves(tmp_path):
    """TLC trace MC_guard_only (10 steps): AiStartOk(a1), ..., AiStartOk(a2), ... → AI applies twice.

    실코드: POST /api/game/{id}/ai-move 가 첫 ai_move 가 끝나기 전에 다시 들어온다
    (routes.py:112 두 번, 또는 routes.py:92 + :112). 둘 다 턴 확인(orchestrator.py:75)을 통과한다.
    """
    orch, gid, game = _new_game(tmp_path)
    _play_h_a_h(orch, gid, game)

    gate = _Gate()
    _gate_first_negamax(orch.strategy_analyst.search_engine, gate)
    w1 = _AiWorker(orch, gid)
    w1.start()
    try:
        assert gate.reached.wait(10), "search gate not reached"
        w2 = _AiWorker(orch, gid)      # 두 번째 ai_move, 첫 번째가 아직 탐색 중
        w2.start()
        w2.join(4)                     # bug: 완주하여 수를 적용 / fix: 락에서 대기
    finally:
        gate.release.set()
        w1.join(20)
    w2.join(20)

    results = [w.result for w in (w1, w2)]
    context = (f"ai results={[(r and r.get('success'), r and r.get('error')) for r in results]}, "
               f"exc={[repr(w.exc) for w in (w1, w2)]}")
    _assert_record_alternates(game, context)
    assert game.move_count == 4, "exactly one AI move must be applied — " + context
    assert sum(1 for r in results if r and r.get("success")) == 1, context
