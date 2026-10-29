# formal/ — JangGi 형식 검증 (WDLAB-STD-VERIFY-001 v1.0)

thin additive shell: 기존 코드를 바꾸지 않고 `formal/` 을 추가한다 (F1 수정 패치는 예외, `evidence/patches/` 에 감사 기록).

## 무엇을 모델링했나

| concern | 수준 | verdict | 모델 | 재현 테스트 |
|---|---|---|---|---|
| `ai-move-undo-race` | L2 (TLA+/TLC) | **FIXED** (F1) + **BOUNDED-PASS** | `ai-move-undo-race/tla/Spec.tla` + 동결 속성 `Properties.tla` | `tests/test_ai_move_undo_race.py` (3건) |

`ai_move`(워커 스레드, `asyncio.to_thread`)가 턴을 확인한 뒤 **원본 `game.board`** 위에서 투기적 탐색(push/pop)을 하고 수를 적용하는 동안,
이벤트 루프 스레드의 `undo` / `move` / 두 번째 `ai-move` 가 락 없이 같은 `Game` 을 변경한다.
모델은 `Game` 하나를 (turn, move_count, 수 스택 hist∈Seq{H,A,S}, AI 스레드 pc, lock) 로 추상화하고,
fix toggle `UseLock`(게임별 뮤텍스) / `UndoTurnGuard`(AI 차례 undo 거부) 를 가진다. 후보 목록·순위는 `CANDIDATES.md`.

## 어떻게 실행하나

```bash
./formal/run_all.sh            # 3-config 게이트: MC=PASS(0) / MC_bug=FAIL(12) / MC_sanity=FAIL(12) + 변이·sanity 추가 4종
./formal/run_all.sh --tests    # + 재현 테스트 (수정된 코드에서 3 passed)
TLC_WORKERS=2 ./formal/run_all.sh   # 워커 수 조정 (기본 4)
```

- 요구: Java 11+, `~/.cache/proof-skills/tla2tools.jar` (또는 `TLA2TOOLS=/path/tla2tools.jar`). 버전은 `TOOLCHAIN.lock`.
- 단일 설정 수동 실행: `cd formal/ai-move-undo-race/tla && java -cp ~/.cache/proof-skills/tla2tools.jar tlc2.TLC -workers 4 -config MC_bug.cfg Spec.tla`
- 재현 테스트만: `python3 -m pytest tests/test_ai_move_undo_race.py -v` (주의: `/usr/bin/python3` 권장 — findings F2 참조)

## 파일

```
formal/
├── README.md, TOOLCHAIN.lock, CANDIDATES.md, findings.json, run_all.sh
├── ai-move-undo-race/
│   ├── SCOPE.md                 범위·추상화·경계·속성 수확표(G1/G2)
│   ├── CORRESPONDENCE.md        모델 요소 ↔ file:line (G4)
│   ├── tla/ Spec.tla Properties.tla MC.cfg MC_bug.cfg MC_sanity.cfg
│   │        MC_bug_record.cfg MC_lock_only.cfg MC_guard_only.cfg MC_sanity2.cfg
│   ├── repro/F2_segv_probe_worker_logging.py   부수 발견 F2 재현 스크립트(환경 결함)
│   └── evidence/  tlc_{bug,fixed,sanity,...}.log, *_trace.md, tlc_coverage.log, mutation.log,
│                  test_before.log, test_after.log, test_regression*.log, run_all.log,
│                  F2_segv_probe.log, patches/F1-ai-move-undo-race.diff, git_commit.log
└── reports/2026-10-29-ai-move-undo-race.md
```

주의: 저장소 `.gitignore` 가 `*.log` 를 무시하므로 evidence 로그는 `git add -f` 로 추가되어 있다.

## 예외 기록 (표준 §9/§14)

- 보고서는 Artifact 대신 docx(`~/ai_project/Proof-Skills/JangGi_ProofSkills_Report_2026-10-29.docx`)와 `formal/reports/*.md` 로 발행 (에이전트 환경 제약).
- Lean 4 미설치 → L3 미시도. W7 승격은 보고서 "후속 제안".
- G2/G7 HITL 승인은 받을 수 없어 `hitl_approvals: ["G2: pending Brian review", "G7: pending Brian review"]` 로 기록.
