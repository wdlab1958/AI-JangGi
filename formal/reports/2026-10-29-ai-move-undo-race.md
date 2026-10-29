# JangGi 형식 검증 보고서 (WDLAB-STD-VERIFY-001)

- 프로젝트: **JangGi — Janggi Champion AI** (`~/ai_project/JangGi`, GitHub `wdlab1958/AI-JangGi`, branch `main`)
- 표준: Unified WDLAB Proof-Skills Standard v1.0 (WDLAB-STD-VERIFY-001), 워크플로 **W1 Bug hunt**
- 도구: proof-skills v0.1.1 · TLA+/TLC (tla2tools v1.8.0, TLC2 2026.10.28.014557) · OpenJDK 21.0.12.1 · Lean 4 미설치
- 날짜: **2026-10-29** · 검사한 commit: `08f7acd0ee80da70d061b3f468055aaf9747da2b` · 작성: Claude (claude-fable-5-1), HITL 승인 대기
- 산출물: `JangGi/formal/` (CANDIDATES, SCOPE, Properties/Spec, CORRESPONDENCE, evidence, findings.json, run_all.sh), 재현 테스트 `tests/test_ai_move_undo_race.py`, 본 보고서 사본 `formal/reports/2026-10-29-ai-move-undo-race.md`

---

## ① 판정 요약

| 항목 | 값 |
|---|---|
| concern | `ai-move-undo-race` — 워커 스레드의 AI 수(`ai_move`: 턴 확인 → **원본 보드** 위 투기적 탐색 → 수 적용)와 이벤트 루프 스레드의 `undo` / `move` / 추가 `ai-move` 요청이 락 없이 같은 `Game` 을 변경하는 경합 |
| **Verdict** | **FIXED** (F1: CONFIRMED → 수정 → 모델·테스트 재통과 + mutation 확인) 및 수정 후 **BOUNDED-PASS** |
| 달성 레벨 | **L2** (TLC 유한 경계 전수 탐색). L3(Lean) 미시도 |
| 경계 (수정 ON, `MC.cfg`) | `AiThreads={a1,a2}`, `MaxHuman=3`, `MaxAiCalls=3`, `MaxUndo=2`, `UseLock=UndoTurnGuard=TRUE` → **126 states generated, 95 distinct, depth 18, 반례 없음** |
| 위반 (수정 OFF, `MC_bug.cfg`) | `TurnParity` 위반, **8 step** 트레이스 (132 generated / 91 distinct / depth 9) |
| 실코드 재현 | `tests/test_ai_move_undo_race.py` 3건 — 수정 전 **3 failed**(속성 단언에서), 수정 후 **3 passed** |
| mutation | 모델에서 fix OFF → 다시 FAIL(exit 12). 락만/가드만 켠 변이도 각각 다른 트레이스로 FAIL → 두 요소 모두 필요 |
| 신뢰 기반 | TLC + 추상화(보드 = 수 스택 H/A/S, 탐색 = push 1회+pop 1회, undo/human_move/apply 원자적, 사람=CHO 선수, 게임 종료 없음) — §⑤ |
| findings | **F1 FIXED(high)**, F2 CONFIRMED(critical, 환경 결함·미수정), F3 SUSPECTED(medium), F4/F5 SUSPECTED(low), F6/F7 CONFIRMED(low, 미수정) |

> "검증됨"의 의미: 위 경계와 추상화 **안에서** 동결 속성 P1·P2·P3 의 반례가 없다는 것이지, 코드가 정확하다는 뜻이 아니다. 기물 합법성·다중 게임·읽기 경합·게임 종료 전이는 이 모델 밖이다.

---

## ② 프로젝트 개요와 G0 후보표

**JangGi** 는 FastAPI(백엔드) + Next.js(프론트) 로 된 인간 대 AI 장기 게임이다. 사람의 수는 REST `POST /api/game/{id}/move`(또는 WS `game:move`)로 들어오고, 서버는 `human_move` 를 이벤트 루프에서 동기 실행한 뒤 `await asyncio.to_thread(orchestrator.ai_move, game_id)` 로 수 초짜리 AI 탐색을 **워커 스레드**에서 돌린다(`routes.py:92`, `websocket_handler.py:133`). 탐색 엔진은 `game.board` **원본**에 `move_piece`/`undo_move` 를 투기적으로 push/pop 한다(`strategy_analyst.py:44`, `search.py:195-211`). `Game`, `Board`, `orchestrator.games` 어디에도 락이 없고, 프론트의 "무르기" 버튼은 AI 사고 중에도 활성이다(`LeftPanel.tsx:245-247`).

| # | 후보 | 위치 | blast radius | concurrency | 결정 |
|---|---|---|---|---|---|
| 1 | AI 탐색 vs undo/move/2중 ai_move 경합 (턴 상태기계·수 기록) | orchestrator.py, game.py, routes.py, websocket_handler.py | H | H | **선정** |
| 2 | 게임 종료 상태기계(반복 off-by-one, 시작 키 side) | game.py:69-80,254-279 | M | L | F5 기록 |
| 3 | 게임 간 공유 싱글턴(TT, memory, winloss) | orchestrator.py:23-43 | M | M | 범위 외(단일 사용자 설계 문서화) |
| 4 | `finalize_game` 비멱등(WS 경로 + GET /report) | websocket_handler.py:128,165; orchestrator.py:288-310 | M | L | F3 기록 |
| 5 | 읽기 경합(탐색 중 GET /state) | routes.py:119-126; game.py:281-297 | L | H | F4 기록 |
| 6 | WS 연결 목록 순회 중 변경 | websocket_handler.py:43-54 | L | L | 제외 |

---

## ③ Finding 별 섹션

### F1 — AI 탐색 중 undo / 사람 수 / 2중 ai_move 경합 → 턴 패리티·기보 교대 위반 (**FIXED**, severity high)

#### 위반 속성 (동결, `formal/ai-move-undo-race/tla/Properties.tla`)

| ID | 속성 | 의미 | 출처 |
|---|---|---|---|
| P1 `TurnParity` | `(turn = "H") <=> (mc % 2 = 0)` | 선수(사람)가 먼저, 교대로 → `current_turn` 은 `move_count` 패리티와 항상 일치 | `game.py:41,125-126,191-192`, `orchestrator.py:196-197` |
| P2 `RecordAlternates` | `AtRest => Len(hist)=mc ∧ ∀i: hist[i] = (i 홀수 ? "H" : "A")` | AI 스레드가 없을 때 수 기록에 투기적 수가 없고 사람/AI 가 교대 | `board.py:161`, `search.py:195-211`, `README.md:244` |
| P3 `MoverIsSideToMove` | `[][실수 추가 ⇒ 추가된 수의 주체 = turn]_pvars` | 적용되는 모든 수는 그 순간 차례인 쪽의 것 | `game.py:86`, `orchestrator.py:75` |

#### 최소 트레이스 1 — `MC_bug.cfg` (P1 위반, 8 steps; `evidence/tlc_bug_trace.md`)

| # | Action | 코드 | 변경 |
|---|---|---|---|
| 1 | `Init` | — | `turn=H, mc=0, hist=<<>>` |
| 2 | `HumanMove` (H1) | game.py:82-127 | `mc=1, hist=<<H>>, turn=A` |
| 3 | `AiStartOk(a1)` 턴 확인 통과 | orchestrator.py:66-76 | `aipc[a1]=search` |
| 4 | `AiSearchPush(a1)` 투기적 수 push | strategy_analyst.py:44 → search.py:195 | `hist=<<H,S>>` |
| 5 | `AiSearchPop(a1)` finally pop | search.py:210-211 | `hist=<<H>>` |
| 6 | `AiApply(a1)` (A1) | orchestrator.py:145-197 | `mc=2, hist=<<H,A>>, turn=H` |
| 7 | `HumanMove` (H2) | game.py:82-127 | `mc=3, hist=<<H,A,H>>, turn=A` |
| 8 | **`Undo`** — AI 차례인데 수락 | game.py:195-227 (routes.py:139-146) | `mc=1, hist=<<H>>, turn=H` → **P1 위반** (mc 홀수인데 사람 차례) |

이 트레이스는 `ai_move` 워커가 아직 시작하지 않은 틈(`websocket_handler.py:117` 의 `await send_to_game` 또는 `to_thread` 스케줄 직후)에도 성립한다. 즉 **락만으로는 막히지 않는다**(`MC_lock_only.cfg` 도 같은 8-step 으로 FAIL).

#### 최소 트레이스 2 — `MC_bug_record.cfg` (P2 위반, 9 steps; `evidence/tlc_bug_record_trace.md`)

| # | Action | 변경 |
|---|---|---|
| 1–7 | 위와 동일 | `mc=3, hist=<<H,A,H>>, turn=A` |
| 8 | `Undo` 수락 | `mc=1, hist=<<H>>, turn=H` |
| 9 | **`HumanMove`** — 사람이 연속 2수 | `mc=2, hist=<<H,H>>` → **P2 위반** |

실코드에서는 멈춰 있던 탐색의 `finally: board.undo_move()` 가 이 사람 수를 보드에서 지우고 AI 가 수를 적용해 기록이 `<<H, A, A>>` 가 된다(아래 재현 F1b).

#### 최소 트레이스 3 — `MC_guard_only.cfg` (undo 가드만 있을 때, 10 steps; `evidence/tlc_mutation_guard_only_trace.md`)

| # | Action | 변경 |
|---|---|---|
| 2 | `HumanMove` | `mc=1, hist=<<H>>, turn=A` |
| 3–5 | `AiStartOk(a1)`, `AiSearchPush(a1)`, `AiSearchPop(a1)` | `hist=<<H>>`, `aipc[a1]=apply` |
| 6 | **`AiStartOk(a2)`** — 두 번째 `POST /ai-move` 도 턴 확인 통과 | `aipc[a2]=search` |
| 7 | `AiSearchPush(a2)` | `hist=<<H,S>>` |
| 8 | `AiApply(a1)` | `mc=2, hist=<<H,S,A>>, turn=H` |
| 9 | `AiSearchPop(a2)` — **a1 의 실수를 pop** | `hist=<<H,S>>` |
| 10 | `AiApply(a2)` | `mc=3, hist=<<H,S,A>>` → **P2 위반**: 투기적 수가 보드에 영구 잔류, AI 연속 2수 |

#### 코드 매핑 (`CORRESPONDENCE.md`)

| 모델 | 코드 | 비고 |
|---|---|---|
| `AiStartOk` 턴 확인 | `orchestrator.py:73-76` | 확인만 하고 락 없음 → check-then-act |
| `AiSearchPush/Pop` | `strategy_analyst.py:44` → `search.py:195` / `:210-211` | `game.board` 원본을 변경 (`risk_assessor` 만 `board.copy()` 사용) |
| `AiApply` | `orchestrator.py:145-197` | 적용 전 기물·합법성은 재검증(:130-142)하지만 **턴은 재확인하지 않음** |
| `Undo` | `game.py:195-202` | 유일한 가드 `move_count >= 2`; `current_turn = human_team` 으로 무조건 덮어씀 |
| 호출 경로 | `routes.py:86,92,112,139-146`, `websocket_handler.py:87-90,107,133` | 이벤트 루프 스레드 vs `asyncio.to_thread` 워커 |
| 사용자 유발 경로 | `frontend/components/LeftPanel.tsx:245-247` | "무르기" 버튼이 `aiThinking` 을 보지 않음 (F6) |

#### 재현 테스트와 수정 전 실패 로그 (`tests/test_ai_move_undo_race.py`, `evidence/test_before.log`)

게이트(`threading.Event`)를 모델의 action 경계와 같은 지점 — `SearchEngine._negamax` **첫 호출**(= `_search_root` 가 투기적 수 1개를 실제 보드에 push 한 직후) — 에 꽂아 워커 스레드를 세워 두고, 이벤트 루프 스레드가 하던 일을 메인 스레드에서 수행한다. `ai_move` 는 서버와 동일하게 별도 스레드에서 실행한다. 외부 서비스 없음(장기기억은 `tmp_path`).

```text
tests/test_ai_move_undo_race.py::test_F1a_undo_during_ai_search_breaks_turn_parity FAILED
E  AssertionError: P1 TurnParity violated — right after undo during AI search (undo={'success': True, ...}):
   move_count=1, current_turn=cho, expected=han

tests/test_ai_move_undo_race.py::test_F1b_undo_then_human_move_during_ai_search_corrupts_record FAILED
WARNING backend.engine.search:search.py:515 _validate_move: search returned ILLEGAL move (9, 1, 7, 2) (team=Team.HAN)
        — substituting a legal move; this indicates a move-gen/search bug
E  AssertionError: P2 violated (record does not alternate CHO/HAN): after undo=True (None), extra human move=True (None),
   ai=True (None), exc=None: move_count=3, len(move_history)=3, movers=['cho', 'han', 'han'], current_turn=cho

tests/test_ai_move_undo_race.py::test_F1c_concurrent_ai_move_calls_apply_two_ai_moves FAILED
E  AssertionError: P2 violated (record does not alternate CHO/HAN): ai results=[(True, None), (True, None)], exc=['None', 'None']:
   move_count=5, len(move_history)=5, movers=['cho', 'han', 'cho', 'han', 'han'], current_turn=cho
============================== 3 failed in 0.16s ===============================
```

세 실패 모두 **속성 단언**에서 발생했다(API/시그니처 변경 아님). F1b 의 경고는 undo 로 뒤바뀐 보드 위에서 탐색이 불법수를 내놓았음을 엔진 스스로 감지한 것이다(엔진의 자체 방어선이 동작했지만 상태기계 위반은 막지 못함).

#### 수정 diff (`evidence/patches/F1-ai-move-undo-race.diff`, 3 파일 +60/−15)

1. `backend/orchestrator/orchestrator.py` — 게임별 `threading.Lock`
   - `__init__`: `self._game_locks = {}`; `create_game`: 락 생성; `_lock_for(game_id)`.
   - `human_move`: `lock.acquire(blocking=False)` 실패 시 `{"success": False, "error": "AI is thinking"}` (이벤트 루프를 막지 않음), 본문은 `try/finally release`.
   - `ai_move`: `with self._lock_for(game_id): return self._ai_move_locked(game)` — 턴 확인 → 탐색 → 적용 전체가 임계 구역(워커 스레드이므로 블로킹 획득; 두 번째 호출은 첫 호출이 끝난 뒤 턴 확인에서 `"Not AI's turn"`).
   - `undo_move`: 비블로킹 획득 실패 시 `"Cannot undo while AI is thinking"`.
2. `backend/engine/game.py` `undo_move` — `if self.status == GameStatus.PLAYING and self.current_turn != self.human_team: return {"success": False, "error": "Cannot undo while AI is thinking"}` (종료된 게임의 undo 는 기존대로 허용).
3. `backend/api/websocket_handler.py` `game:undo` — 실패 시 `game:error` 로 사유 통지(기존엔 무시).

```diff
-    def ai_move(self, game_id: str) -> dict:
-        """AI 수 실행 - 5개 에이전트 파이프라인 (탐색 엔진 결과 최우선)"""
-        game = self.games.get(game_id)
-        if not game:
-            return {"success": False, "error": "Game not found"}
-
-        # 턴/상태 확인
+    def ai_move(self, game_id: str) -> dict:
+        ...
+        game = self.games.get(game_id)
+        if not game:
+            return {"success": False, "error": "Game not found"}
+        with self._lock_for(game_id):
+            return self._ai_move_locked(game)
+
+    def _ai_move_locked(self, game: Game) -> dict:
+        # 턴/상태 확인
```
```diff
     def undo_move(self) -> dict:
         if self.move_count < 2:
             return {"success": False, "error": "Not enough moves to undo"}
+        if self.status == GameStatus.PLAYING and self.current_turn != self.human_team:
+            return {"success": False, "error": "Cannot undo while AI is thinking"}
```

Anti-Reward-Hacking(§6.6) 점검: 기능 제거·무조건 early-return 없음. 바뀌는 입력 범위 = "AI 차례(사고 중)에 들어온 undo/move, 그리고 겹치는 두 번째 ai_move" 만 거부(400). 공개 API 시그니처 변경 없음(에러 문자열 2종 추가).

#### 수정 후 통과·mutation 증거

| 검사 | 결과 | 증거 |
|---|---|---|
| 재현 테스트 (수정 후) | **3 passed** in 4.14s | `evidence/test_after.log` |
| 관련 기존 테스트 `test_engine.py` + `test_orchestrator.py` | 13 passed | `evidence/test_regression.log` |
| `python3 -m tests.test_ai_diagnostic` (자가 대국·합법수) | exit 0, "30수 중 불법수 0개 ✓ ALL VALID" | `evidence/test_regression_ai_diagnostic.log` |
| 모델 `MC.cfg` (fix ON) | PASS, 95 distinct / depth 18 | `evidence/tlc_fixed.log`, `tlc_fixed_after.log` |
| 모델 mutation `MC_bug.cfg` (fix OFF) | **FAIL exit 12** `TurnParity` | `evidence/mutation.log` |
| 변이 `MC_lock_only.cfg` / `MC_guard_only.cfg` | 각각 FAIL exit 12 (서로 다른 트레이스) | `evidence/tlc_mutation_*.log` |
| 게이트 러너 `./formal/run_all.sh --tests` | `RESULT: ALL EXPECTATIONS MET` | `evidence/run_all.log` |

### F2 — [환경] 호스트 기본 `python3`(pyenv 3.12.11 디렉터리, 실제 3.12.3 혼합 빌드)가 `asyncio.to_thread` 에서 세그폴트 (**CONFIRMED**, critical, 미수정·HITL)

- 발견 경위: 재현 테스트 중 워커 스레드의 `logger.warning()` → `logging.LogRecord.__init__` → `asyncio.current_task()` 에서 pytest 프로세스가 세그폴트.
- 확인(`evidence/F2_segv_probe.log`, 스크립트 `formal/ai-move-undo-race/repro/F2_segv_probe_worker_logging.py`): `~/.pyenv/versions/3.12.11/bin/python3` 는 `sys.version = 3.12.3 (Aug 31 2026)` 이고 `lib-dynload/_asyncio*.so` 는 2026-04-09 빌드 → ABI 불일치.
  - probe A `asyncio.run(asyncio.to_thread(lambda: 'ok'))` → **exit 139**
  - probe B 스레드에서 `asyncio.current_task()` → exit 139
  - probe C/D `to_thread` + `logger.warning` (서버 패턴 `routes.py:92` → `search.py:171,515`) → exit 139 (`logAsyncioTasks=False` 로도 불충분)
  - probe E `/usr/bin/python3` 3.12.3 → **정상**
- 영향: 이 인터프리터로 서버를 띄우면 `/move`, `/ai-move`, WS `game:move` **매 호출마다** 프로세스 크래시. 과거 통합 테스트(E2E 68/68) 는 다른 인터프리터였거나 빌드 변경(2026-08-31) 이전으로 추정.
- 조치(HITL): pyenv 3.12.11 재설치 또는 `run.sh`/docker 에서 `/usr/bin/python3` 고정. 코드 변경 없음. 재현 테스트는 하네스 크래시만 피하도록 `logging.logAsyncioTasks = False` 를 설정(속성 검증과 무관).

### F3 — `finalize_game` 비멱등 (SUSPECTED, medium)
WS `game:end` 경로(`websocket_handler.py:128,165`)가 `finalize_game` 을 직접 호출하고, 이후 `GET /report` 가 `get_or_create_report` 캐시 미스로 재호출 → `long_term.record_game_result` 2회(total_games/Elo 2중 집계, `long_term_memory.py:59-80`). 현재 프론트는 REST 만 사용해 WS 클라이언트에서만 노출. 미재현. 제안: WS 경로도 `get_or_create_report` 사용.

### F4 — 읽기 경합 (SUSPECTED, low)
AI 탐색 중 `GET /state`/`valid-moves` 가 투기적 수가 올라간 원본 보드를 `to_matrix()` 로 노출(`routes.py:119-126`, `game.py:281-297`). 상태 변경 없음. 제안: 탐색을 `board.copy()` 위에서 수행하거나 읽기에도 락/스냅샷.

### F5 — 3회 반복 무승부 off-by-one, 시작 포지션 키 side 불일치 (SUSPECTED, low)
`game.py:254-275` 가 `_record_position` 전에 `_check_repetition(>=3)` 을 평가 → 4번째 출현에서 무승부. `__init__` 의 첫 기록만 side=둘 차례(CHO), 이후는 side=직전 둔 쪽.

### F6 — 프론트 "무르기" 버튼이 AI 사고 중 활성 (CONFIRMED, low, 미수정)
`LeftPanel.tsx:245-247` `disabled={!gameState || gameState.move_count < 2}`. 백엔드 수정으로 이제 400 이 에러 배너로 표시된다. 제안: `aiThinking` 반영 후 `frontend/out` 재빌드.

### F7 — README.md 의 `#` 문자 전부 유실 (CONFIRMED, low, 미수정)
저장소 전 이력(초기 커밋 포함)에서 `^#` 줄 0개. 제목·ToC 앵커 `(1-overview)`·코드블록 셸 주석이 깨짐. 이번 "형식 검증" 절은 올바른 마크다운으로 추가; 전체 복원은 범위 외(HITL).

---

## ④ 검증된 것과 경계

| ID | 속성 | 수준 | 결과(fix ON) | 결과(fix OFF) | 경계 |
|---|---|---|---|---|---|
| P1 | `TurnParity` | protocol invariant (동결) | holds | **violated** (8 steps) | `AiThreads=2, MaxHuman=3, MaxAiCalls=3, MaxUndo=2`; 126/95 states, depth 18 |
| P2 | `RecordAlternates` | protocol invariant, quiescent (동결) | holds | **violated** (9 steps; guard-only 10 steps) | 동일 |
| P3 | `MoverIsSideToMove` | protocol action property (동결) | holds | (P1 이 먼저 위반되어 TLC 가 보고) | 동일 |
| C1 | `TypeOK` | code | holds | holds | 동일 |
| S1 | `NeverUndone` sanity | must fail | **FAIL** (exit 12) | — | undo 도달 가능 증명 |
| S2 | `NeverTwoAiInFlight` sanity | must fail | — | **FAIL** (exit 12) | 2중 ai_move 도달 가능 증명 |
| coverage | `-coverage 1` | — | 모든 action 발화 (HumanMove 16, AiStartOk 20, AiStartRejected 4, Push 20, Pop 20, AiApply 7, Undo 7 distinct) | | `evidence/tlc_coverage.log` |

Three-Config Rule: `MC.cfg` PASS / `MC_bug.cfg` FAIL / `MC_sanity.cfg` FAIL — 모두 충족(`run_all.sh` 가 단언).

---

## ⑤ 신뢰 기반(Trust Base)과 버그를 숨길 수 있는 추상화

- **도구**: TLC2 2026.10.28 (tla2tools v1.8.0), OpenJDK 21.0.12.1; 재현은 CPython(`/usr/bin/python3` 3.12.3 권장 — F2) + pytest 8.3.
- **추상화**
  1. 보드 = 수 스택 `Seq({H,A,S})`. 기물 좌표·합법성·포획을 안 보므로 "AI 가 다른 포지션용으로 계산한 수를 적용한다"는 품질 문제는 보이지 않는다(실제로 재현 F1b 에서 엔진이 불법수를 내놓고 자체 교체함).
  2. 탐색 = push 1회 + pop 1회. 중첩 깊이에 따른 다른 손상 모양, `move_piece` 가 빈 칸에서 조기 반환하고 `finally` 가 실수를 pop 하는 모드(`board.py:139-140`)는 표현되지 않음.
  3. `Undo`/`HumanMove`/`AiApply` 는 원자적 1 action. 수정 ON 에서는 락으로 실제 원자화되어 정확; 수정 OFF 에서는 under-approximation(위반이 더 많아질 수만 있음).
  4. 사람=CHO 선수 고정. AI 선수(`ai_team="cho"`) 게임은 패리티가 반대이나 가드는 side-agnostic.
  5. 게임 종료(외통·빅장·반복·200수), 평가·메모리·5-에이전트, WS 전송, 다중 게임, GIL 세부 모델 없음.
- **가정 A1–A5** (CORRESPONDENCE.md): GIL 하 단일 속성 쓰기 원자성, `to_thread` 가 실제 동시 실행, 탐색 예외는 `BaseAgent.run` 이 포획, 경계 내 게임 종료 없음.

---

## ⑥ 재실행 명령어

```bash
cd ~/ai_project/JangGi
./formal/run_all.sh --tests                 # 3-config 게이트 + 변이 4종 + 재현 테스트 (TLC_WORKERS=4 기본)
# 개별
cd formal/ai-move-undo-race/tla
java -cp ~/.cache/proof-skills/tla2tools.jar tlc2.TLC -workers 4 -config MC.cfg        Spec.tla   # expect exit 0
java -cp ~/.cache/proof-skills/tla2tools.jar tlc2.TLC -workers 4 -config MC_bug.cfg    Spec.tla   # expect exit 12
java -cp ~/.cache/proof-skills/tla2tools.jar tlc2.TLC -workers 4 -config MC_sanity.cfg Spec.tla   # expect exit 12
cd ~/ai_project/JangGi && /usr/bin/python3 -m pytest tests/test_ai_move_undo_race.py -v              # 3 passed (수정 후)
git stash -- backend/ && /usr/bin/python3 -m pytest tests/test_ai_move_undo_race.py -v; git stash pop  # 수정 전 재현(3 failed)
python3 -I formal/ai-move-undo-race/repro/F2_segv_probe_worker_logging.py              # F2: pyenv 빌드 exit 139, /usr/bin/python3 exit 0
```

---

## ⑦ HITL 승인 이력

| 게이트 | 항목 | 상태 |
|---|---|---|
| G2 | 동결 속성 P1·P2·P3 (Properties.tla) | **pending Brian review** |
| G7 | 수정 설계 선택: (a) 이벤트 루프 측 `human_move`/`undo` 는 비블로킹 거부(큐잉·탐색 취소 대안 있음), (b) `Game.undo_move` 의 AI 차례 거부(종료 게임은 허용), (c) WS `game:undo` 실패 시 `game:error` 송신 추가 | **pending Brian review** — 공개 API 시그니처 변경은 없어 적용 후 보고 |
| F2 | 인터프리터 재설치 / `run.sh` 인터프리터 고정 | pending (코드 미변경) |
| F3–F7 | 부수 발견 수정 여부 | pending (기록만) |

---

## ⑧ 후속 제안

- **W5 CI 가드**: `./formal/run_all.sh --tests` 를 `paths: [backend/**, formal/**]` 트리거로 등록, 기대값 불일치 시 머지 차단. `CORRESPONDENCE.md` 에 등록된 파일 변경 시 W6 드리프트 리뷰 필수.
- **W4 단순화**: 게임별 락이 증명된 뒤에는 `orchestrator.py` 의 탐색 후 기물/합법성 재검증(:130-142)과 `game.make_ai_move()` 폴백의 턴 재확인 중 일부가 중복일 수 있다 — 제거 전 재검증 필수.
- **W7 Lean 승격**: P1/P2 를 무한 길이 수열에 대한 inductive invariant 로 증명(사람·AI 핸들러 전이 함수 + 락 모델). Lean 4 설치 후.
- 설계 대안: 탐색을 `board.copy()` 위에서 수행하면 F4 와 F1 의 보드 손상 모드가 구조적으로 사라진다(락은 턴 상태기계 보호용으로 여전히 필요).
- F6 프론트 버튼 비활성화, F3 WS 경로 멱등화, F2 인터프리터 정비, F7 README 복원.

---

## ⑨ Definition of Done 체크리스트 (§15)

| 항목 | 상태 |
|---|---|
| SCOPE.md: 단일 concern, 포함/추상화/제외, 경계 명시 | ✅ |
| Properties: 출처 인용, 프로토콜 속성 동결 + HITL 승인 기록 | ✅ 동결·출처 / ⏳ 승인 pending |
| CORRESPONDENCE.md: 모든 action ↔ file:line | ✅ (수정 후 위치표 포함) |
| MC.cfg PASS / MC_bug.cfg FAIL / MC_sanity.cfg FAIL (로그 저장) | ✅ (+ 변이 2종, sanity 2종, coverage) |
| 반례 → 결정적 재현, 수정 전 실패 로그, 속성 단언에서 실패 | ✅ 3 tests, `test_before.log` |
| 수정 후 모델·테스트 통과, mutation check | ✅ `test_after.log`, `mutation.log` |
| (Lean) sorry 0, 표준 공리만 | ➖ 미적용 (Lean 미설치) |
| 패치 감사 기록, 무력화 수정 아님 확인 | ✅ `evidence/patches/F1-ai-move-undo-race.diff` |
| findings.json (wdlab 블록 포함), 판정 어휘 준수 | ✅ (schema valid) |
| Artifact 보고서 발행 + reports/ 로컬 사본 | ✅ docx + `formal/reports/2026-10-29-ai-move-undo-race.md` (Artifact 대신 docx — 환경 제약) |
| W5 CI 가드 등록 여부 결정, W4 단순화 후속 제안 | ⏳ 제안만 (⑧) |

---

## ⑩ 변경 파일 목록과 git commit

| 파일 | 변경 |
|---|---|
| `backend/orchestrator/orchestrator.py` | F1 수정: 게임별 락, `_lock_for`, `human_move`/`undo_move` 비블로킹, `ai_move` → `_ai_move_locked` |
| `backend/engine/game.py` | F1 수정: `undo_move` AI 차례 거부 |
| `backend/api/websocket_handler.py` | F1 수정: `game:undo` 실패 통지 |
| `tests/test_ai_move_undo_race.py` | 신규: 결정적 재현 3건 |
| `README.md` | "형식 검증 — Oct.29, 2026" 절, Updated 날짜, Recent Updates 1행 |
| `formal/**` | CANDIDATES, README, TOOLCHAIN.lock, findings.json, run_all.sh, `ai-move-undo-race/{SCOPE,CORRESPONDENCE}.md`, `tla/*`, `repro/*`, `evidence/*`, `reports/*` |

- 검사 commit: `08f7acd0ee80da70d061b3f468055aaf9747da2b`
- 수정 commit: 아래 "커밋 기록" 참조 (저장소 사본에서는 `git log -1 -- formal/` 로 확인; 사용자의 미커밋 파일 `reports/{ab,chaos,e2e}_result.json`, `task.txt` 는 건드리지 않음)

### 커밋 기록

이 파일을 포함하는 커밋 (`git log -1 -- formal/` 로 확인). 커밋 후 로그 사본: `formal/ai-move-undo-race/evidence/git_commit.log`, `~/ai_project/Proof-Skills/JangGi_git_commit_2026-10-29.log`.
