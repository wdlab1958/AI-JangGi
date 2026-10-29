| # | Action | Code | Changed |
|---|---|---|---|
| 1 | `Init` |  | `mc` = 0; `nHuman` = 0; `lock` = "free"; `hist` = <<>>; `nAi` = 0; `aipc` = (a1 :> "idle" @@ a2 :> "idle"); `turn` = "H"; `nUndo` = 0 |
| 2 | `HumanMove` | backend/engine/game.py:82-127 | `mc` = 1; `nHuman` = 1; `hist` = <<"H">>; `turn` = "A" |
| 3 | `AiStartOk(a1)` | backend/orchestrator/orchestrator.py:66-76 | `nAi` = 1; `aipc` = (a1 :> "search" @@ a2 :> "idle") |
| 4 | `AiSearchPush(a1)` | strategy_analyst.py:44 | `hist` = <<"H", "S">>; `aipc` = (a1 :> "unsearch" @@ a2 :> "idle") |
| 5 | `AiSearchPop(a1)` | search.py:210-211 | `hist` = <<"H">>; `aipc` = (a1 :> "apply" @@ a2 :> "idle") |
| 6 | `AiStartOk(a2)` | backend/orchestrator/orchestrator.py:66-76 | `nAi` = 2; `aipc` = (a1 :> "apply" @@ a2 :> "search") |
| 7 | `AiSearchPush(a2)` | strategy_analyst.py:44 | `hist` = <<"H", "S">>; `aipc` = (a1 :> "apply" @@ a2 :> "unsearch") |
| 8 | `AiApply(a1)` | orchestrator.py:145-197 | `mc` = 2; `hist` = <<"H", "S", "A">>; `aipc` = (a1 :> "idle" @@ a2 :> "unsearch"); `turn` = "H" |
| 9 | `AiSearchPop(a2)` | search.py:210-211 | `hist` = <<"H", "S">>; `aipc` = (a1 :> "idle" @@ a2 :> "apply") |
| 10 | `AiApply(a2)` ⚠ | orchestrator.py:145-197 | `mc` = 3; `hist` = <<"H", "S", "A">>; `aipc` = (a1 :> "idle" @@ a2 :> "idle") |
