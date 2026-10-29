---------------------------- MODULE Properties ----------------------------
(* FROZEN protocol-level properties for concern ai-move-undo-race.         *)
(* Harvested 2026-10-29 from game.py / orchestrator.py / board.py / README. *)
(* Do NOT weaken without explicit HITL approval (WDLAB-STD-VERIFY-001 §6.3). *)
(* This module declares only the state it reads; Spec.tla instantiates it.  *)
EXTENDS Naturals, Sequences

CONSTANTS AiThreads
VARIABLES turn,   \* Game.current_turn            : "H" (human, CHO, moves first) | "A" (ai, HAN)
          mc,     \* Game.move_count
          hist,   \* Board.move_history as movers : Seq of "H" | "A" | "S" (S = speculative search push)
          aipc    \* per-thread pc of orchestrator.ai_move invocations

pvars == <<turn, mc, hist, aipc>>

AtRest == \A t \in AiThreads : aipc[t] = "idle"

\* P1  src: game.py:41 (CHO first), game.py:125-126, 191-192, orchestrator.py:196-197 (turn flips per move)
TurnParity == (turn = "H") <=> (mc % 2 = 0)

\* P2  src: board.py:161 (one push per real move), search.py:195-211 (push/pop balanced), README.md:244
RecordAlternates ==
    AtRest =>
        /\ Len(hist) = mc
        /\ \A i \in 1..Len(hist) : hist[i] = (IF i % 2 = 1 THEN "H" ELSE "A")

\* P3  src: game.py:86, orchestrator.py:75 (mover must be the side to move when the move is applied)
MoverIsSideToMove ==
    [][ (Len(hist') = Len(hist) + 1 /\ hist'[Len(hist')] # "S")
            => hist'[Len(hist')] = turn ]_pvars
=============================================================================
