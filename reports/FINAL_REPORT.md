# 장기 챔피언 AI — 종합 보고서 (A/B · E2E · Chaos + 감사/수정)

작성일: 2026-06-06
작성자: 자동화 에이전트(Claude Code)
대상 커밋 기준: `ab490d8` 이후 작업 트리

---

## 0. 요약 (Executive Summary)

- **서버 기동·라우팅·브라우저 오픈 완료.** 포트 충돌을 피해 백엔드 `:8007`, 프론트엔드 `:3005` 로 구동, 9개 REST 엔드포인트 전부 라우팅 확인, Chrome 으로 앱 오픈.
- **A/B · E2E · Chaos 테스트를 순차 수행**하고, 그 결과를 바탕으로 결함을 체계적으로 감사.
- **영역별 병렬 감사 에이전트 3종 + 직접 grep 교차검증**으로 문서·메모리 주장 대비 실제 구현의 불일치/스텁/사일런트 폴백/하드코딩/버그를 **28건(G1–G28)** 도출.
- **전부 단계적으로 해결**(24건 수정, 4건은 조사 결과 정상/설계의도로 ACCEPTED).
- **수정 후 최종 테스트 전부 GREEN**: E2E 68/68(스트레스 반복 포함 88/104 등 전부 통과), Chaos 18/18, A/B 깊은 탐색 우세 가설 SUPPORTED.

> ⚠️ 환경 메모: 이 머신의 pyenv Python 3.12.11 은 `asyncio.run()` 자체가 **세그폴트**한다(이벤트 루프 손상). 백엔드는 정상 동작하는 시스템 파이썬 `/usr/bin/python3`(3.12.3)로 구동해야 한다. (실행 스크립트/문서에 반영 권장)

---

## 1. 서버 기동 · 엔드포인트 라우팅 (요청 1)

| 항목 | 값 |
|------|----|
| 백엔드 | `uvicorn backend.main:app` @ `0.0.0.0:8007` (시스템 파이썬) |
| 프론트엔드 | `next dev -p 3005` (개발), `next build`→`out/` 정적 export(프로덕션은 FastAPI 가 서빙) |
| 프록시 | next.config.js dev rewrite `/api/*`,`/ws/*` → `:8007` |
| 브라우저 | DISPLAY=:1 에 Chrome 으로 `http://localhost:3005/` 오픈 |

**라우팅 확인된 엔드포인트(9):**
`POST /api/game/new`, `POST /api/game/{id}/move`, **`POST /api/game/{id}/ai-move`(신규)**,
`GET /api/game/{id}/state`, `GET /api/game/{id}/analysis`, `POST /api/game/{id}/undo`,
`POST /api/game/{id}/valid-moves`, `GET /api/game/{id}/report`, `GET /api/stats`,
그리고 `GET /health`, `WS /ws/{game_id}`.

---

## 2. 테스트 보고서 (요청 2)

세 테스트를 **A/B → E2E → Chaos** 순서로 수행. 스크립트는 `tests/integration/` 에, 원시 결과 JSON 은 `reports/` 에 저장.

### 2.1 A/B 테스트 — `tests/integration/ab_test.py`
- **설계:** 탐색 강도 차이 검증. A(깊이4/1.0s) vs B(깊이1/0.3s) 를 AI-vs-AI 로 대결. 선후공 효과 제거를 위해 매 게임 초/한을 교대. 70플라이 상한, 초과 시 평가로 어드주디케이션.
- **가설 H1:** 더 깊은 탐색(A)이 더 자주 이긴다.

| 시점 | 결과 | 판정 |
|------|------|------|
| 수정 전(baseline) | A 4승 / B 0승 / 무 0 | A_STRONGER · H1 SUPPORTED |
| 수정 후(final) | A 3승 / B 0승 / 무 1 | A_STRONGER · H1 SUPPORTED |

- NPS(노드/초) ≈ **33,000–37,000** (메모리의 "~37,000" 주장과 부합).
- 엔진 수정(mobility·단일패스·INF sentinel) 후에도 강도/속도 회귀 없음.

### 2.2 E2E 테스트 — `tests/integration/e2e_test.py`
- **설계:** REST API 로 실제 게임을 진행하며 생성→유효수→수두기(+AI응답)→상태일관성→무르기→분석→보고서→통계 전 흐름 + 신규 검증(mobility 실측, 인간=한 AI 선수 플로우) 검증.

| 시점 | 결과 |
|------|------|
| 수정 전 | 60/60 PASS |
| 수정 중 | 95/98 (장기 플레이에서 `inf` JSON 직렬화 500 노출 → G28) |
| 수정 후 | **68/68 PASS** (스트레스 반복: 88/88, 104/104 등 전부 통과, 500/inf 0건) |

### 2.3 Chaos 테스트 — `tests/integration/chaos_test.py`
- **설계:** 존재하지 않는 게임, 좌표 범위 초과, 상대/빈칸 기물 이동, 누락필드·깨진 JSON, 검증기 범위 밖, 시작시점 undo, 대량 게임 50개, 동시요청 경쟁, 문자열 좌표 등 비정상 입력 주입 → 서버는 **5xx 로 죽지 않고** 적절한 4xx/정상 응답, 종료 후 `/health` 생존.

| 시점 | 결과 | 비고 |
|------|------|------|
| 1차 | 15/17 | 2건은 **테스트 자체 결함**(자기 기물 이동·선행수로 undo 가능). 서버는 정상 |
| 보정 후 | **18/18 PASS** | 정확한 상대기물/새 게임 케이스로 수정 |

> Chaos 가 노출한 사실: 잘못된 입력에 대한 서버 견고성은 양호(검증기·예외처리 정상). 별도로 **장기 정상 플레이**에서 드물게 발생하던 `inf` 직렬화 500(G28)을 E2E 가 포착하여 근본 수정함.

---

## 3. 기능 누락 Gap — 번호 목록 (요청 3)

UI/기능 차원에서 "구현되어야 하나 없던" 항목:

| # | 누락 기능 | 해결 |
|---|-----------|------|
| **G1** | 게임 설정 컨트롤(진영/난이도/제한시간/차림) — `/game/new` 파라미터가 UI 에서 도달 불가 | 좌측 패널 설정 카드 + AI 선수용 `/ai-move` + 보드 방향 연동으로 구현 |
| **G2** | 게임 종료 보고서 미노출 | 우측 패널 보고서 카드 + 종료 시 `/report` 자동 조회 |
| **G3** | 누적 통계(전적/ELO) 미노출 | 좌측 패널 누적 전적 카드 + `/stats` |
| **G4** | "경기 기록"이 빈 플레이스홀더 | 실제 기보 리스트 렌더링 |
| **G5** | 프론트 에러 표면화 부재 | 에러 배너 + useGame error 상태 |

(상세·근거·코드 위치는 `reports/GAP_LIST.md` 참조)

---

## 4. 감사(Audit) Gap List 및 해결 (요청 4)

문서·메모리 주장 vs 실제 구현의 불일치, 스텁/사일런트 폴백/하드코딩/버그를 영역별 병렬 에이전트(엔진 / 에이전트·메모리 / 프론트·API·WS)로 조사하고 직접 grep 으로 교차검증. **총 28건(G1–G28)**.

핵심 발견 및 해결 하이라이트:

- **메모리 주장 vs 실제:** `anthropic/chromadb/redis/psycopg2` 는 import 0건(LLM/DB 연동 없음) → 의존성 제거(G12). 장기 메모리는 write-only 였고 읽기 API 가 사문화 → 실제 환류(G9). working/short-term 일부가 영구 공백 → 실제 채움(G10).
- **하드코딩/스텁:** evaluator `mobility=0.0` 고정 → 실측(G6). 보고서 confidence 날조 상수 → 데이터 도출(G8). UseCaseDesigner 하드코딩 수순 → 보드 기반 동적화(G7).
- **사일런트 폴백:** 탐색 랜덤/치환 폴백 무로그 → 경고 로그(G15).
- **불일치 문서:** opening_book/websocket docstring 을 실제 구현과 일치(G16,G20). evaluator "단일 패스" 주장을 실제 단일 패스로 정정(G17).
- **버그:** WebSocket 포트 `:8001` 하드코딩(G18), AI 수 팀 `'han'` 가정(G21), 승률 히스토리 미초기화(G22), undo 표면화(G24).
- **테스트로 발견:** 탐색 `±inf` 경계가 Null-Move 연산에서 `inf/NaN` 을 만들어 JSON 직렬화 500 유발 → 유한 sentinel(INF=60000) + 직렬화 안전망(G28).
- **조사 후 정상 판정(ACCEPTED):** 평가 스케일 일치(G11), 궁 중앙 포 대각점프(G14), OverflowError 방어(G25), 좌표 폴백(G26), RiskAssessor 보수성(G27).

> 전체 28건의 분류·근거·상태표는 `reports/GAP_LIST.md` 의 "해결 상태" 표 참조. 24건 FIXED, 4건 ACCEPTED.

---

## 5. 최종 검증 (요청 4 마무리)

수정 완료 후 A/B·E2E 재수행:

```
A/B   : A_STRONGER (A 3승 0패 1무), H1 SUPPORTED, NPS ~33–37k
E2E   : 68/68 PASS (반복 스트레스 88/104 등 전부 통과, inf/500 0건)
Chaos : 18/18 PASS (참고: 안정성 회귀 없음)
```

엔진 정합성 추가 검증:
- `evaluation.mobility` 실측(예: 0.7 = 자기 38수 − 상대 31수, ×0.1) + `mobility_detail` 노출.
- working `candidates`(예: 5개), short-term `phase_strategies`(성공 카운트) 실제 채워짐.
- long-term `persistent_opponent_profile`/`recent_results`/`strategy_patterns` 환류 확인.
- 인간=한 선택 시 `/ai-move` 로 AI(초) 선수 정상, 이후 턴 인간(한)으로 전환.
- 프론트 빌드(type-check 포함) 통과, UI 스크린샷으로 설정·전적·기보·평가(기동성 포함) 렌더 확인.

---

## 6. 산출물

- 테스트 스크립트: `tests/integration/{ab_test,e2e_test,chaos_test}.py`
- 원시 결과: `reports/{ab_result,e2e_result,chaos_result}.json`
- 감사 Gap List(번호·분류·근거·상태): `reports/GAP_LIST.md`
- 본 보고서: `reports/FINAL_REPORT.md`
