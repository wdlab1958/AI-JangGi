# Correspondence: ai-move-undo-race

Spec commit: `08f7acd0ee80da70d061b3f468055aaf9747da2b` (JangGi `main`, 2026-10-29)
Line numbers refer to the **pre-fix** code at that commit. After the fix (patch `evidence/patches/F1-ai-move-undo-race.diff`) `orchestrator.py` lines shift by the lock wrapper; the `src:` tags in `Spec.tla` are kept at the pre-fix lines and the post-fix locations are listed in the last table.

## Map

| Model element | Code | Kind | Abstraction | Notes |
|---|---|---|---|---|
| `turn` | `backend/engine/game.py:41` `self.current_turn` | variable | `Team.CHO` → `"H"` (human, moves first), `Team.HAN` → `"A"` (ai) | human=CHO/AI=HAN default (`game.py:35,45`) |
| `mc` | `game.py:43` `self.move_count` | variable | `0..MaxLen` | |
| `hist` | `backend/engine/board.py:55` `self.move_history` | variable | tuple `(fr,fc,tr,tc,captured)` → mover tag `"H"`/`"A"`; speculative pushes by the search → `"S"` | squares/legality dropped |
| `aipc[t]` | program counter of one `JanggiOrchestrator.ai_move` invocation (`orchestrator.py:66-250`) running in `asyncio.to_thread` (`routes.py:92,112`, `websocket_handler.py:133`) | variable | `idle / search / unsearch / apply` | `AiThreads={a1,a2}` = at most two invocations in flight |
| `lock` | (fix) `orchestrator.py` `self._game_locks[game_id]` (`threading.Lock`) | variable | `Free` or holder thread | absent in pre-fix code (`UseLock=FALSE`) |
| `nHuman`, `nAi`, `nUndo` | — | bound counters | request counts | model bounds only |
| `HumanMove` | `game.py:82-127` `Game.make_human_move`: turn check `:86`, `board.move_piece` `:99`, `move_count += 1` `:100`, `current_turn = ai_team` `:125-126`; entry `orchestrator.py:46-64`; callers `routes.py:86`, `websocket_handler.py:107` | action | whole call atomic (runs synchronously on the event-loop thread) | fix: non-blocking per-game lock around `orchestrator.human_move` |
| `AiStartOk(t)` | `orchestrator.py:66-76` (status/turn check `:73-76` passes) | action | lock acquire + check atomic under fix | |
| `AiStartRejected(t)` | `orchestrator.py:75-76` `"Not AI's turn"` | action | | also `game.py:132-133` for the fallback path |
| `AiSearchPush(t)` | `backend/agents/strategy_analyst.py:44` → `backend/engine/search.py:135` `find_best_move` → `:195` `board.move_piece` in `_search_root` (also `:318` in `_negamax`, `:396-404` quiescence) | action | thousands of nested push/pop collapsed to one `S` push | the search mutates `game.board` itself (no copy) |
| `AiSearchPop(t)` | `search.py:210-211` `finally: board.undo_move()` (also `:336-337`) | action | pops whatever is on top (`board.py:165-168`) | |
| `AiApply(t)` | `orchestrator.py:145` `game.board.move_piece`, `:146` `move_count += 1`, `:196-197` `current_turn = human_team`; validation `:130-142` checks piece/legality but **not** turn | action | 5-agent pipeline, memory, evaluation omitted | fallback `game.make_ai_move()` `game.py:129-193` has the same shape |
| `Undo` | `game.py:195-227` `Game.undo_move`: guard `move_count >= 2` `:196`, `board.undo_move()` ×2 `:199-200`, `move_count -= 2` `:201`, `current_turn = human_team` `:202`; entry `orchestrator.py:252-256`; callers `routes.py:139-146`, `websocket_handler.py:87-90` | action | 4 writes merged into one atomic step (see Granularity) | fix: `UndoTurnGuard` = reject when `current_turn != human_team` while playing; `UseLock` = non-blocking lock |
| `TurnParity` (P1) | `game.py:41,125-126,191-192`, `orchestrator.py:196-197` | invariant (frozen) | | `Properties.tla` |
| `RecordAlternates` (P2) | `board.py:161` (one push per real move), `search.py:195-211` (balanced push/pop), `README.md:244` "Undo last move pair (human + AI)" | invariant (frozen, quiescent) | checked only when no `ai_move` is in flight | |
| `MoverIsSideToMove` (P3) | `game.py:86`, `orchestrator.py:75` | action property (frozen) | | |
| `NeverUndone`, `NeverTwoAiInFlight` | — | sanity (must fail) | | |

## Assumptions

- A1: CPython GIL — a single attribute assignment (`current_turn = ...`, list `append`/`pop`) is atomic; interleaving happens between statements. The model takes coarser atoms (see Granularity), which only removes interleavings.
- A2: `asyncio.to_thread` really runs `ai_move` concurrently with the event loop (default `ThreadPoolExecutor`). Confirmed by `routes.py:92,112`, `websocket_handler.py:133`.
- A3: The search never raises out of `strategy_analyst.run` (caught by `BaseAgent.run` `base_agent.py:36-45`), and every `move_piece` is paired with an `undo_move` (`try/finally`). If `move_piece` returns early because the source square is empty (`board.py:139-140`), the paired `undo_move` pops a *real* move — a corruption mode the model does not represent (model pops are always paired with a push).
- A4: Game end (`status != playing`), bikjang, repetition and the 200-move rule do not occur within the bound.
- A5: Human is CHO (first mover). For `ai_team="cho"` the parity is mirrored; the fix (turn guard) is side-agnostic.

## Granularity

One action per handler call for the event-loop thread (`HumanMove`, `Undo`) and one action per shared-stack mutation for the worker (`AiStartOk`, `AiSearchPush`, `AiSearchPop`, `AiApply`). Merged steps the code performs separately:

- `Undo`: `board.undo_move()`, `board.undo_move()`, `move_count -= 2`, `current_turn = human_team` (`game.py:199-202`) — 4 writes as one step.
- `HumanMove`: turn check, `move_piece`, `move_count += 1`, `current_turn = ai_team` (`game.py:86-126`) — one step.
- `AiApply`: validation (`orchestrator.py:130-142`), `move_piece`, `move_count += 1`, agents/memory, `current_turn = human_team` (`:145-197`) — one step.

Under `UseLock = TRUE` the real code holds the per-game lock across each of these regions, so the merged atoms are exact. Under `UseLock = FALSE` the model is an under-approximation: it already finds the violations; finer splitting could only add more.

## Post-fix locations (for W6 drift checks)

| Model element | Post-fix code |
|---|---|
| `lock` | `backend/orchestrator/orchestrator.py` `self._game_locks` (init in `__init__`, created in `create_game`, `_lock_for()`) |
| `HumanMove` lock | `orchestrator.py` `human_move`: `lock.acquire(blocking=False)` → `"AI is thinking"` |
| `AiStartOk/AiApply` lock | `orchestrator.py` `ai_move`: `with self._lock_for(game_id): return self._ai_move_locked(game)` |
| `Undo` guards | `game.py` `undo_move`: `status == PLAYING and current_turn != human_team` → reject; `orchestrator.py` `undo_move`: non-blocking lock |
