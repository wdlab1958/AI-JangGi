# Janggi Champion AI — Gap List (감사 결과)

작성일: 2026-06-06
근거: 영역별 병렬 감사 에이전트 3종 + 직접 grep 교차검증 + A/B·E2E·Chaos 테스트 관찰.
범례: **상태** = OPEN(미해결) / FIXED(해결) / ACCEPTED(현행 유지 + 근거).
분류: **[기능누락]** = 구현되어야 하나 없는 기능 / **[불일치]** = 문서·메모리 주장 vs 실제 / **[버그]** / **[스텁]** / **[폴백]** = 사일런트 폴백 / **[하드코딩]** / **[정리]** = 데드코드·의존성.

---

## A. 기능 누락 (Missing Features)

- **G1 [기능누락]** — UI에 게임 설정 컨트롤 없음. `/api/game/new`는 `ai_team`/`cho_formation`/`han_formation`/`ai_depth`/`ai_time_limit`를 받지만 프론트는 전부 하드코딩 기본값만 전송(`index.tsx`의 `humanTeam='cho'` 고정, `createGame()` 인자 없음). 사용자가 진영·난이도·제한시간을 고를 수 없음.
- **G2 [기능누락]** — 게임 종료 보고서(`GET /api/game/{id}/report`)가 UI에 전혀 노출되지 않음. 백엔드는 생성하나 프론트가 호출하지 않음.
- **G3 [기능누락]** — 전체 통계(`GET /api/stats`: 전적/ELO/연승)가 UI에 노출되지 않음.
- **G4 [기능누락]** — `LeftPanel`의 "경기 기록" 패널이 제목만 있고 실제 기보(수 목록)를 렌더링하지 않는 빈 플레이스홀더. 상태 문자열만 표시.
- **G5 [기능누락]** — 프론트 에러 표면화 부재. `useGame.ts`의 createGame/makeMove/getValidMoves/undo는 실패 시 `console.error`만 하고 UI에 아무 표시 없음(보드가 조용히 멈춤).

## B. 멀티에이전트·메모리 (claims vs 실제)

- **G6 [버그]** — `evaluator.evaluate_detailed`의 `mobility`가 **항상 0.0 하드코딩**. 이로 인해 WinLossAnalyst 승률식의 `ΔMobility*0.2` 항, StrategyAnalyst/UseCaseDesigner의 mobility 추론이 전부 무력화. (engine·agent 감사 공통 지적)
- **G7 [스텁]** — `UseCaseDesigner`가 정적 `STRATEGY_TEMPLATES` 룩업 + 하드코딩 턴범위 문자열(`_predict_win_path`)만 반환. 보드/수 계산 없음.
- **G8 [하드코딩]** — `ReportGenerator`의 `confidence` 값이 `0.8`/`0.85` 등 날조 상수. 실제 데이터(승률 확신도·탐색깊이)와 무관.
- **G9 [불일치]** — 장기 메모리가 write-mostly. `get_player_profile`/`get_recent_games`/`get_strategy_patterns`/`save_strategy_pattern`이 **호출처 없음** → 상대 프로파일이 게임에 환류되지 않음("3-Layer Memory" 주장의 핵심 읽기 경로 사문화).
- **G10 [불일치]** — Working/Short-term 일부가 항상 비어 있음. `working_memory.set_candidates`/`set_threats`, `short_term_memory.record_strategy_result`가 호출처 없음 → `threats`/`candidates`/`phase_strategies`가 영구 공백.
- **G11 [버그]** — Short-term 평가 추세의 스케일 불일치. 인간 수는 `evaluate()` 스칼라, AI 수는 `evaluate_detailed()['total']`을 같은 `evaluation_history`에 혼입 → `critical_turns` 오탐.
- **G12 [정리]** — 데드 의존성. `requirements.txt`의 `anthropic`/`chromadb`/`redis`/`psycopg2-binary`가 어디서도 import 안 됨(LLM 호출 0건). `package.json`의 `react-konva`/`konva`/`chart.js`/`react-chartjs-2`도 미사용(실제로는 순수 Canvas API).

## C. 엔진·규칙 (correctness)

- **G13 [버그]** — 궁성 내 졸(卒/兵) 대각 이동 생성 로직이 깨짐(`board.py`의 `(dr-r)==fwd or (dr-r)*fwd>0` — 변수 `dr`은 절대행, 바깥 `or` 가지 도달 불가).
- **G14 [버그/규칙]** — 궁 중앙(1,4)/(8,4)에 있는 포의 대각 점프가 생성 불가(`PALACE_SLIDE` 중앙 항목 길이 1 → `len(path)>=2` 조건 미충족).
- **G15 [폴백]** — `search.find_best_move`의 랜덤수 폴백(`random.choice`)과 `_validate_move`의 랜덤 치환이 **무로그**로 탐색/생성 버그를 은폐.
- **G16 [불일치]** — `opening_book` docstring은 `{(board_hash, team_hash): ...}` 해시 키 O(1)이라 주장하나 실제는 수순번호 인덱싱. 포지션 무관.
- **G17 [불일치]** — evaluator "단일 패스" 주장하나 종반 분기에서 졸 전진용 **2차 전체 그리드 스캔** 수행.

## D. 프론트·API·WebSocket

- **G18 [버그]** — `useWebSocket.ts`가 백엔드 포트 `:8001` 하드코딩(실제 8007). 프록시도 우회. (단, 현재 미사용 — G19)
- **G19 [정리]** — `useWebSocket` 훅 전체가 데드코드(어디서도 import 안 됨). 백엔드 WebSocket 핸들러도 UI에서 도달 불가(앱은 REST 전용).
- **G20 [불일치]** — `websocket_handler` docstring의 이벤트 페이로드 계약(`analysis_result`/`confidence`/`{from,to,...}`)이 실제 emit(`{agent_id,status,time}`, `move`/`analysis`)과 불일치.
- **G21 [버그]** — `index.tsx:55` AI 수 하이라이트가 `m.piece?.team || 'han'`으로 팀을 무조건 'han' 가정(AI가 CHO일 때 깨지는 잠복 버그).
- **G22 [버그]** — `RightPanel` 승률 히스토리(`winHistoryRef`)가 "새 게임" 시 초기화되지 않아 이전 게임 곡선이 잔존.
- **G23 [불일치]** — `useGame.ts:3` 주석이 프록시 대상을 `:8001`로 잘못 표기(실제 8007).
- **G24 [버그/UX]** — "무르기"가 한 번에 2플라이(인간+AI)를 되돌리지만 UI 표시 없음. 400 응답을 조용히 무시.

## E. 검증/허용 항목 (조사 후 현행 유지)

- **G25 [ACCEPTED]** — `get_win_probability`의 `OverflowError` 처리: 좁은 범위 정상 방어. 유지.
- **G26 [ACCEPTED]** — `_get_raw_moves`/`ZOBRIST_PIECE.get(...,0)`의 빈/0 폴백: 실 도달 불가(좌표는 호출 전 검증). 유지.
- **G27 [ACCEPTED]** — `RiskAssessor`의 보수적 거부(score≥80 + 근접대안)로 인해 출력이 거의 채택되지 않음: AI 강도 보호를 위한 설계상 의도. threats 환류(G10)로 가시성만 개선.

## F. 테스트 중 발견된 추가 결함

- **G28 [버그]** — 탐색 경계로 `±math.inf` 사용 시, Null-Move 가지치기의 `-beta + 0.01` 연산이 `±inf`/NaN 을 만들어 후보수·분석 `score` 에 새어 들어가고, FastAPI 의 표준 `json.dumps` 가 이를 거부하여 **500 Internal Server Error** 발생(드물게, 탐색 타임아웃 타이밍 의존). E2E 장기 플레이에서 재현됨.

---

## 해결 상태 (Resolution Status)

| Gap | 상태 | 핵심 조치 |
|-----|------|-----------|
| G1 | FIXED | LeftPanel 설정 UI(진영·난이도·제한시간·초/한 차림) + `POST /game/{id}/ai-move`(AI 선수) + 보드 방향 humanTeam 연동 |
| G2 | FIXED | RightPanel '경기 종료 보고서' 카드 + 종료 시 `/report` 자동 조회 |
| G3 | FIXED | LeftPanel '누적 전적'(전적·ELO·승률·연승) + `/stats` 조회 |
| G4 | FIXED | LeftPanel '경기 기록' 실제 기보 렌더링 + useGame moveHistory 추적 |
| G5 | FIXED | useGame error 상태 + 중앙 에러 배너(클릭 닫기) |
| G6 | FIXED | evaluator 실제 mobility 계산(`(내-상대 합법수)*0.1`) + mobility_detail |
| G7 | FIXED | UseCaseDesigner 예상수순을 보드 상태(잔여 기물)에서 동적 산출 |
| G8 | FIXED | ReportGenerator confidence 를 승리경로 신뢰도·risk_score 확신도에서 도출 |
| G9 | FIXED | LongTermMemory.get_context 가 상대 프로파일/최근 경기/전략 패턴 실제 읽기 + finalize 시 패턴 저장 |
| G10 | FIXED | orchestrator 에서 working candidates/threats, short_term phase_strategies 실제 채움 |
| G11 | ACCEPTED | 인간/AI 평가 모두 AI 관점 `evaluate()` 동일 스케일(`evaluate_detailed.total==evaluate()`) — 불일치 아님 확인 |
| G12 | FIXED | requirements.txt/package.json 미사용 의존성 제거(anthropic/chromadb/redis/psycopg2, konva/chart.js 등) |
| G13 | FIXED | 궁성 졸 대각 이동 로직 정리(데드 분기 제거, 동작 동일) |
| G14 | ACCEPTED | 궁 중앙 포의 대각 점프 불가 = 스크린 칸이 없어 기하학적으로 정상 |
| G15 | FIXED | 랜덤/치환 폴백에 경고 로그 추가(무로그 은폐 제거) |
| G16 | FIXED | opening_book docstring 을 실제(수순번호 인덱싱)와 일치하도록 수정 |
| G17 | FIXED | 종반 졸 전진 보너스를 단일 패스에 통합(2차 스캔 제거) |
| G18 | FIXED | useWebSocket same-origin 연결(`window.location.host`)로 포트 하드코딩 제거 |
| G19 | ACCEPTED | 포트 버그 해소 후 동작 가능한 선택적 기능으로 유지(REST 경로가 주 경로) |
| G20 | FIXED | websocket_handler docstring 을 실제 이벤트 계약과 일치하도록 수정 |
| G21 | FIXED | index.tsx AI 수 팀을 설정상 AI 팀에서 도출(‘han’ 가정 제거) |
| G22 | FIXED | RightPanel game_id 변경 시 승률 히스토리 초기화 |
| G23 | FIXED | useGame 주석을 8007 로 정정 |
| G24 | FIXED | undo 400 표면화 + ‘한 턴(2수) 되돌림’ 명시 + 기보 동기화 |
| G25-27 | ACCEPTED | 조사 결과 정상/설계 의도 — 근거 명시 |
| G28 | FIXED | 탐색 경계 유한 sentinel(`INF=60000`) 사용 + 응답 직렬화 안전망(SafeJSONResponse, inf/NaN 치환·로그) |
