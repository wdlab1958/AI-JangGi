------------------------------- MODULE Spec -------------------------------
(* Concern: ai-move-undo-race (JangGi).                                     *)
(* Shared resource: one Game (current_turn, move_count, board.move_history). *)
(* Writers: HumanMove and Undo on the asyncio event-loop thread; one or two  *)
(* orchestrator.ai_move invocations on worker threads (asyncio.to_thread).   *)
(* The search engine pushes/pops speculative moves on the REAL board.        *)
(* Fix toggles: UseLock (per-game mutex in orchestrator), UndoTurnGuard      *)
(* (Game.undo_move rejects while it is the AI's turn).                        *)
EXTENDS Naturals, Sequences, FiniteSets

CONSTANTS AiThreads,      \* model values, e.g. {a1, a2}: concurrent ai_move invocations
          MaxHuman,       \* bound on human moves
          MaxAiCalls,     \* bound on ai_move invocations (incl. rejected ones)
          MaxUndo,        \* bound on undo requests
          UseLock,        \* BOOLEAN fix part 1
          UndoTurnGuard   \* BOOLEAN fix part 2

Free == "free"

VARIABLES turn, mc, hist, aipc, lock, nHuman, nAi, nUndo
vars == <<turn, mc, hist, aipc, lock, nHuman, nAi, nUndo>>

P == INSTANCE Properties

PcSet == {"idle", "search", "unsearch", "apply"}
MaxLen == MaxHuman + 2 * MaxAiCalls

TypeOK ==
    /\ turn \in {"H", "A"}
    /\ mc \in 0..MaxLen
    /\ hist \in Seq({"H", "A", "S"}) /\ Len(hist) <= MaxLen
    /\ aipc \in [AiThreads -> PcSet]
    /\ lock \in AiThreads \cup {Free}
    /\ nHuman \in 0..MaxHuman /\ nAi \in 0..MaxAiCalls /\ nUndo \in 0..MaxUndo

Init ==
    /\ turn = "H" /\ mc = 0 /\ hist = <<>>
    /\ aipc = [t \in AiThreads |-> "idle"]
    /\ lock = Free
    /\ nHuman = 0 /\ nAi = 0 /\ nUndo = 0

Pop(s) == IF Len(s) > 0 THEN SubSeq(s, 1, Len(s) - 1) ELSE s

\* src: backend/engine/game.py:82-127 make_human_move (turn check :86, push :99, mc :100, flip :125-126)
\*      called synchronously on the event loop: routes.py:86, websocket_handler.py:107
\*      fix: orchestrator.human_move acquires the per-game lock non-blocking (held for the whole call)
HumanMove ==
    /\ nHuman < MaxHuman
    /\ turn = "H"
    /\ UseLock => lock = Free
    /\ hist' = Append(hist, "H")
    /\ mc' = mc + 1
    /\ turn' = "A"
    /\ nHuman' = nHuman + 1
    /\ UNCHANGED <<aipc, lock, nAi, nUndo>>

\* src: backend/orchestrator/orchestrator.py:66-76 ai_move entry: turn check passes (:75)
\*      started via asyncio.to_thread at routes.py:92,112 and websocket_handler.py:133
\*      fix: lock acquired (blocking) before the check and held until AiApply
AiStartOk(t) ==
    /\ aipc[t] = "idle" /\ nAi < MaxAiCalls
    /\ UseLock => lock = Free
    /\ turn = "A"
    /\ lock' = (IF UseLock THEN t ELSE lock)
    /\ aipc' = [aipc EXCEPT ![t] = "search"]
    /\ nAi' = nAi + 1
    /\ UNCHANGED <<turn, mc, hist, nHuman, nUndo>>

\* src: orchestrator.py:75-76 "Not AI's turn" -> returns error (lock acquired and released)
AiStartRejected(t) ==
    /\ aipc[t] = "idle" /\ nAi < MaxAiCalls
    /\ UseLock => lock = Free
    /\ turn # "A"
    /\ nAi' = nAi + 1
    /\ UNCHANGED <<turn, mc, hist, aipc, lock, nHuman, nUndo>>

\* src: strategy_analyst.py:44 -> search.py:195 board.move_piece (speculative push on the REAL board)
AiSearchPush(t) ==
    /\ aipc[t] = "search"
    /\ hist' = Append(hist, "S")
    /\ aipc' = [aipc EXCEPT ![t] = "unsearch"]
    /\ UNCHANGED <<turn, mc, lock, nHuman, nAi, nUndo>>

\* src: search.py:210-211 finally: board.undo_move()  -- pops WHATEVER is on top of the stack
AiSearchPop(t) ==
    /\ aipc[t] = "unsearch"
    /\ hist' = Pop(hist)
    /\ aipc' = [aipc EXCEPT ![t] = "apply"]
    /\ UNCHANGED <<turn, mc, lock, nHuman, nAi, nUndo>>

\* src: orchestrator.py:145-197 apply: move_piece :145, mc :146, flip to human :196-197 (no re-check of turn)
\*      fix: lock released here
AiApply(t) ==
    /\ aipc[t] = "apply"
    /\ hist' = Append(hist, "A")
    /\ mc' = mc + 1
    /\ turn' = "H"
    /\ aipc' = [aipc EXCEPT ![t] = "idle"]
    /\ lock' = (IF UseLock THEN Free ELSE lock)
    /\ UNCHANGED <<nHuman, nAi, nUndo>>

\* src: game.py:195-227 undo_move via orchestrator.py:252-256 (routes.py:139-146, websocket_handler.py:87-90)
\*      pops 2 (:199-200), mc -= 2 (:201), turn := human (:202); only guard is mc >= 2 (:196)
\*      fix: UndoTurnGuard -> reject when turn # human (game.py); UseLock -> non-blocking lock (orchestrator)
Undo ==
    /\ nUndo < MaxUndo
    /\ mc >= 2
    /\ UseLock => lock = Free
    /\ UndoTurnGuard => turn = "H"
    /\ hist' = Pop(Pop(hist))
    /\ mc' = mc - 2
    /\ turn' = "H"
    /\ nUndo' = nUndo + 1
    /\ UNCHANGED <<aipc, lock, nHuman, nAi>>

AiStep(t) == AiStartOk(t) \/ AiStartRejected(t) \/ AiSearchPush(t) \/ AiSearchPop(t) \/ AiApply(t)

Next == HumanMove \/ Undo \/ \E t \in AiThreads : AiStep(t)

Spec == Init /\ [][Next]_vars

----------------------------------------------------------------------------
\* Frozen properties (Properties.tla), re-exported for the .cfg files
TurnParity        == P!TurnParity
RecordAlternates  == P!RecordAlternates
MoverIsSideToMove == P!MoverIsSideToMove

\* Sanity (must FAIL): an undo is reachable at all, so the undo-related properties are not vacuous.
NeverUndone == nUndo = 0
\* Sanity 2 (must FAIL): two ai_move invocations can be in flight at once (double /ai-move).
NeverTwoAiInFlight == ~(\E a, b \in AiThreads : a # b /\ aipc[a] # "idle" /\ aipc[b] # "idle")
=============================================================================
