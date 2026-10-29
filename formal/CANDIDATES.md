# G0 후보 선정 — JangGi (Janggi Champion AI)

- 기준: WDLAB-STD-VERIFY-001 v1.0 §5 G0 (blast radius × concurrency)
- 검사 commit: `08f7acd0ee80da70d061b3f468055aaf9747da2b` (branch `main`)
- 코드 규모: Python 33 파일(backend/engine, agents, orchestrator, api, memory), TS/TSX 9 파일(frontend), pytest 3 + integration 3

## 동시성 구조 요약

- FastAPI 단일 프로세스. `human_move` / `undo_move` / `get_*` 는 **이벤트 루프 스레드**에서 동기 실행.
- `ai_move` 는 `asyncio.to_thread(orchestrator.ai_move, game_id)` 로 **워커 스레드**에서 수 초간 실행 (`backend/api/routes.py:92,112`, `backend/api/websocket_handler.py:133`).
- 탐색 엔진은 `game.board` **원본**에 `move_piece`/`undo_move` 를 투기적으로 push/pop 한다 (`backend/agents/strategy_analyst.py:44`, `backend/engine/search.py:195-211,318-337`).
- `Game`/`Board`/`JanggiOrchestrator.games` 어디에도 락이 없다. 프론트 "무르기" 버튼은 AI 사고 중에도 활성 (`frontend/components/LeftPanel.tsx:245-247`, 보드만 `disabled={aiThinking}` `pages/index.tsx:158`).

## 후보 (순위순)

| # | 후보 concern | 위치 | blast radius | concurrency | 순위 근거 |
|---|---|---|---|---|---|
| 1 | **AI 탐색(워커 스레드) vs 사람 undo/move/2중 ai_move 경합** — 턴 상태기계·보드 기록 손상 | `orchestrator.py:46-256`, `game.py:82-227`, `routes.py:80-116,139-146`, `websocket_handler.py:87-166` | **H** (게임 규칙 위반: 한쪽이 연속 2수, 사람 수 소실, AI 2중 수; 모든 게임에 영향) | **H** (매 수마다 수 초의 창; 사용자 클릭 1회로 유발 가능) | **선정** |
| 2 | 게임 종료 상태기계 (`_check_game_end` 순서, 3회 반복 off-by-one, 시작 포지션 키 side 불일치) | `game.py:69-80,254-279` | M (무승부 판정 1수 지연) | L (순차) | 부수 finding으로 기록 |
| 3 | 오케스트레이터 전역 싱글턴(`strategy_analyst.search_engine` TT/position_history, `memory`, `winloss_analyst`)의 게임 간 공유 | `orchestrator.py:23-43` | M (다중 게임 시 평가·기억 혼선) | M (게임 2개 이상일 때만) | "단일 사용자 설계" 문서화됨(`Self_test_report.md:219`) → 범위 외 |
| 4 | `finalize_game` 비멱등: WS `game:end` 경로가 직접 호출 후 `GET /report` 가 재호출 → 장기기억 통계 2중 집계 | `websocket_handler.py:128,165`, `orchestrator.py:288-310`, `long_term_memory.py:59-80` | M (Elo/total_games 오염) | L | 부수 finding(F2) |
| 5 | 읽기 경합: AI 탐색 중 `GET /state`·`valid-moves` 가 투기적 수가 올라간 보드를 노출 | `routes.py:119-126`, `game.py:281-297` | L (표시 오류, 상태 변경 없음) | H | 부수 finding(F3) |
| 6 | WebSocket `ConnectionManager` 연결 목록 변경 중 순회 | `websocket_handler.py:43-54` | L | L (단일 루프, 복사 후 제거) | 제외 |

## 선정: `ai-move-undo-race`

후보 1. 하나의 공유 자원(`Game` 객체 = turn/move_count/board.move_history)에 세 종류의 핸들러
(HumanMove, Undo, AiMove 워커)가 락 없이 check-then-act 한다. 패턴은 `LostUpdate`(check-then-act) + `OrderStateMachine`(상태기계 action property) 혼합.
