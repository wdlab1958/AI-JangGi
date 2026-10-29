# Scope: ai-move-undo-race

- Project / Module: JangGi / `backend/orchestrator/orchestrator.py`, `backend/engine/game.py`, `backend/api/{routes,websocket_handler}.py`
- Verification Level Target: **L2** (TLA+/TLC bounded model check)
- Concern (한 문장): 워커 스레드에서 돌아가는 AI 수(`ai_move`: 턴 확인 → 원본 보드 위 투기적 탐색 → 수 적용)와, 이벤트 루프 스레드에서 들어오는 사람의 `undo`/`move`/추가 `ai-move` 요청이 락 없이 같은 `Game`을 변경할 때 턴 교대·기보(수 기록) 불변식이 깨지는가.
- Rank: blast radius **H** × concurrency **H** (CANDIDATES.md #1)
- 검사 commit: `08f7acd0ee80da70d061b3f468055aaf9747da2b`

## In scope
- `Game.current_turn`, `Game.move_count`, `Board.move_history` (수 스택) — 세 변수의 일관성.
- 핸들러: `Game.make_human_move`(game.py:82-127), `Game.undo_move`(game.py:195-227), `JanggiOrchestrator.ai_move`(orchestrator.py:66-250: 턴 확인 :73-76, 탐색 push/pop search.py:195-211, 적용 :145-197), 그리고 `/ai-move`·`/move` 두 경로에서 `ai_move` 가 동시에 두 번 호출되는 경우.
- 투기적 탐색이 `game.board` 원본을 변경한다는 사실(strategy_analyst.py:44, search.py:195/211).

## Abstracted (버그를 숨길 수 있는 추상화 명시)
- **보드 = 수 스택** `hist \in Seq({"H","A","S"})`. 기물 좌표·합법성·포획은 모델링하지 않음. 따라서 "AI가 다른 포지션용으로 계산한 수를 적용한다"는 품질 문제는 보이지 않고, 기록의 교대/길이/턴 패리티만 본다.
- **AI 탐색 = push 1회 + pop 1회** (`AiSearchPush`/`AiSearchPop`). 실제 탐색은 수천 번 push/pop 하지만 각 쌍은 균형이며 하나의 쌍으로 경합을 재현할 수 있다. 중첩 깊이에 따른 다른 손상 모양은 숨겨질 수 있음.
- **Undo 는 원자적 1 action** (실코드는 pop, pop, mc-=2, turn=human 의 4개 쓰기). 더 세분화하면 인터리빙이 늘어나 위반이 더 많아질 수만 있고 줄지 않는다(under-approximation). 수정 ON 에서는 락으로 실제 원자화되므로 정확.
- **HumanMove 는 원자적 1 action** (같은 이유; 수정 ON 에서 락으로 원자화).
- 사람 = 선수(CHO), AI = 후수(HAN). AI 선수 게임(`ai_team="cho"`)은 패리티가 반대이지만 구조는 동일 — 모델링하지 않음.
- 게임 종료(`status`), 빅장/반복/200수 무승부, 평가·메모리·5-에이전트 파이프라인(탐색 이외), WebSocket 전송, 다중 게임: **없음**으로 가정.
- GIL/메모리 모델: 각 action 을 원자적으로 봄(CPython GIL 하에서 단일 속성 쓰기는 원자적).

## Out of scope
- 장기 규칙 자체의 정확성(기물 이동 규칙, 외통 판정) — 기존 단위 테스트 영역.
- 탐색 엔진 알고리즘 정확성, 평가 함수.
- 다중 게임 간 공유 싱글턴(CANDIDATES #3), finalize 멱등성(#4), 읽기 경합(#5) — 부수 finding 으로만 기록.

## Tool choice & rationale
- **TLA+ / TLC** (G3): 두 스레드(이벤트 루프 vs 워커, 또는 워커 2개)의 인터리빙이 핵심이며 상태 공간이 작다(아래 경계). Lean 미설치 → L3 는 후속 제안(W7)으로만.
- 패턴 출발점: `LostUpdate`(check-then-act + fix toggle + 3-config 구조) + `OrderStateMachine`(action property 형태).

## Bounds
- `AiThreads = {a1, a2}` (동시 `ai_move` 호출 최대 2개 in flight), `MaxHuman = 3`, `MaxAiCalls = 3`, `MaxUndo = 2`.
- fix toggle: `UseLock` (게임별 뮤텍스, orchestrator), `UndoTurnGuard` (AI 차례에 undo 거부, game.py). `MC.cfg` = 둘 다 TRUE.
- 결과(states/depth)는 evidence/ 로그와 findings.json 에 기록.

## Properties (G2 수확·동결) — Properties.tla

| ID | Property | Level | Source | Frozen |
|---|---|---|---|---|
| P1 | `TurnParity`: `turn = "H" <=> mc % 2 = 0` — 선수(사람)가 먼저 두고 교대로 둔다. `current_turn` 은 `move_count` 패리티와 항상 일치 | protocol (invariant) | `game.py:41` (`current_turn = Team.CHO`), `game.py:125-126`/`191-192`, `orchestrator.py:196-197` (성공한 수마다 턴 전환), 장기 규칙 "교대로 둔다" | ✅ |
| P2 | `RecordAlternates`: 정지 상태(AI 스레드 없음)에서 수 기록은 투기적 수가 없고 홀수 번째 = 사람, 짝수 번째 = AI (`H,A,H,A,...`), 길이 = `move_count` | protocol (invariant, quiescent) | `board.py:161` (실수마다 1 push), `search.py:195-211,318-337` (`try/finally` 로 push/pop 균형 — README.md:592 "SearchTimeout Board Corruption" 수정 이력), `README.md:244` "Undo last move pair (human + AI)" | ✅ |
| P3 | `MoverIsSideToMove`: 기록에 추가되는 모든 실수는 그 순간의 `current_turn` 측이 둔 것 | protocol (action property) | `game.py:86` (`current_turn != human_team → "Not your turn"`), `orchestrator.py:75` (`current_turn != ai_team → "Not AI's turn"`) | ✅ |
| C1 | `TypeOK` | code | 모델 변수 타입 | — |
| S1 | `NeverUndone` (sanity, 반드시 FAIL) | sanity | — | — |

HITL: `hitl_approvals: ["G2: pending Brian review"]` — 동결 승인 대기.
