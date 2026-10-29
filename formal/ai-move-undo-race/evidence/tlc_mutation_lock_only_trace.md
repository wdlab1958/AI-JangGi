| # | Action | Code | Changed |
|---|---|---|---|
| 1 | `Init` |  | `mc` = 0; `nHuman` = 0; `lock` = "free"; `hist` = <<>>; `nAi` = 0; `aipc` = (a1 :> "idle" @@ a2 :> "idle"); `turn` = "H"; `nUndo` = 0 |
| 2 | `HumanMove` | backend/engine/game.py:82-127 | `mc` = 1; `nHuman` = 1; `hist` = <<"H">>; `turn` = "A" |
| 3 | `AiStartOk(a1)` | backend/orchestrator/orchestrator.py:66-76 | `lock` = a1; `nAi` = 1; `aipc` = (a1 :> "search" @@ a2 :> "idle") |
| 4 | `AiSearchPush(a1)` | strategy_analyst.py:44 | `hist` = <<"H", "S">>; `aipc` = (a1 :> "unsearch" @@ a2 :> "idle") |
| 5 | `AiSearchPop(a1)` | search.py:210-211 | `hist` = <<"H">>; `aipc` = (a1 :> "apply" @@ a2 :> "idle") |
| 6 | `AiApply(a1)` | orchestrator.py:145-197 | `mc` = 2; `lock` = "free"; `hist` = <<"H", "A">>; `aipc` = (a1 :> "idle" @@ a2 :> "idle"); `turn` = "H" |
| 7 | `HumanMove` | backend/engine/game.py:82-127 | `mc` = 3; `nHuman` = 2; `hist` = <<"H", "A", "H">>; `turn` = "A" |
| 8 | `Undo` ⚠ | game.py:195-227 | `mc` = 1; `hist` = <<"H">>; `turn` = "H"; `nUndo` = 1 |
