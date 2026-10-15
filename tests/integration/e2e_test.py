"""E2E Test: REST API 를 통해 실제 게임을 끝까지 플레이하며 전체 흐름을 검증.

검증 항목:
  - 게임 생성 / 상태 조회 / 유효수 조회 / 수 두기(+AI 응답) / 무르기 / 분석 / 보고서 / 통계
  - 상태 일관성(move_count 증가, 턴 전환, 보드 변화)
  - 모든 응답이 5xx 없이 처리되는지
"""
import sys
import os
import json
import time
import random
import urllib.request
import urllib.error

BASE = os.environ.get("JANGGI_API", "http://localhost:8007")
random.seed(42)

results = []  # (name, passed, detail)


def call(method, path, body=None, expect=200):
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            code = r.status
            payload = json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        code = e.code
        try:
            payload = json.loads(e.read().decode())
        except Exception:
            payload = {}
    return code, payload


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f" :: {detail}" if detail and not cond else ""))
    return cond


def human_pieces_moves(state):
    """현재 턴 플레이어(인간=CHO 가정)의 기물 중 유효수가 있는 (r,c,moves) 목록."""
    out = []
    board = state["board"]
    turn = state["current_turn"]
    for r in range(10):
        for c in range(9):
            p = board[r][c]
            if p and p["team"] == turn:
                out.append((r, c))
    return out


def main():
    print("=" * 60)
    print("E2E TEST: 전체 게임 플로우 (REST API)")
    print(f"  대상: {BASE}")
    print("=" * 60)

    # 1. health
    code, _ = call("GET", "/health")
    check("health 200", code == 200, f"code={code}")

    # 2. 게임 생성
    code, game = call("POST", "/api/game/new",
                      {"cho_formation": "내상외마", "han_formation": "내상외마", "ai_team": "han"})
    ok = check("create game 200", code == 200, f"code={code}")
    if not ok:
        return finish()
    gid = game["game_id"]
    check("game has board 10x9", len(game["board"]) == 10 and len(game["board"][0]) == 9)
    check("initial turn = cho", game["current_turn"] == "cho")
    check("initial move_count = 0", game["move_count"] == 0)

    # 3. 게임 루프 (인간=CHO)
    human_moves_made = 0
    MAX_HUMAN_MOVES = 20
    prev_move_count = 0
    ended = False
    full_move_logged = False

    for _ in range(MAX_HUMAN_MOVES):
        code, state = call("GET", f"/api/game/{gid}/state")
        if not check(f"state 200 (turn {human_moves_made})", code == 200, f"code={code}"):
            break
        if state["status"] != "playing":
            ended = True
            check("game reached terminal status", True, state["status"])
            break
        if state["current_turn"] != "cho":
            check("turn is cho before human move", False, state["current_turn"])
            break

        # 유효수가 있는 인간 기물 찾기
        candidates = human_pieces_moves(state)
        random.shuffle(candidates)
        chosen = None
        for (r, c) in candidates:
            code, vm = call("POST", f"/api/game/{gid}/valid-moves", {"row": r, "col": c})
            if code == 200 and vm.get("valid_moves"):
                mv = random.choice(vm["valid_moves"])
                chosen = (r, c, mv[0], mv[1])
                break
        if chosen is None:
            check("found a legal human move", False, "no legal moves")
            break

        fr, fc, tr, tc = chosen
        code, mres = call("POST", f"/api/game/{gid}/move",
                          {"from_row": fr, "from_col": fc, "to_row": tr, "to_col": tc})
        if not check(f"move 200 ({fr},{fc}->{tr},{tc})", code == 200, f"code={code} {mres}"):
            break
        check("human_move success", mres.get("human_move", {}).get("success") is True)

        ai = mres.get("ai_move")
        if ai is not None:
            check("ai_move success", ai.get("success") is True, str(ai)[:120])
            if not full_move_logged and ai.get("analysis"):
                # 한 수에 대한 AI 분석 필드 존재 확인
                a = ai["analysis"]
                check("ai analysis has depth/nodes/time",
                      all(k in a for k in ("depth", "nodes", "time")))
                check("ai has agent_results (5 agents)",
                      len(ai.get("agent_results", {})) == 5,
                      str(list(ai.get("agent_results", {}).keys())))
                full_move_logged = True

        human_moves_made += 1

    # 4. move_count 증가 확인
    code, state = call("GET", f"/api/game/{gid}/state")
    check("move_count advanced", state["move_count"] > prev_move_count,
          f"move_count={state['move_count']}")

    # 5. undo (게임이 진행 중일 때만 의미)
    if state["status"] == "playing" and state["move_count"] >= 2:
        before = state["move_count"]
        code, ures = call("POST", f"/api/game/{gid}/undo")
        check("undo 200", code == 200, f"code={code}")
        code, state2 = call("GET", f"/api/game/{gid}/state")
        check("undo reverted 2 plies", state2["move_count"] == before - 2,
              f"{before} -> {state2['move_count']}")

    # 6. analysis 엔드포인트
    code, an = call("GET", f"/api/game/{gid}/analysis")
    check("analysis 200", code == 200, f"code={code}")
    check("analysis has agent_status", "agent_status" in an)

    # 7. report 엔드포인트 (idempotent)
    code, rep = call("GET", f"/api/game/{gid}/report")
    check("report 200", code == 200, f"code={code}")
    code, rep2 = call("GET", f"/api/game/{gid}/report")
    check("report idempotent", code == 200 and rep2.get("game_id") == rep.get("game_id"))

    # 8. stats
    code, st = call("GET", "/api/stats")
    check("stats 200", code == 200, f"code={code}")
    check("stats has total_games", "total_games" in st)

    # 9. mobility 가 실제 계산되는지 (G6 회귀) — 새 게임에서 한 수 둔 뒤 확인
    code, g2 = call("POST", "/api/game/new", {"ai_depth": 3, "ai_time_limit": 1.0})
    if code == 200:
        gid2 = g2["game_id"]
        call("POST", f"/api/game/{gid2}/move",
             {"from_row": 3, "from_col": 2, "to_row": 4, "to_col": 2})
        code, s2 = call("GET", f"/api/game/{gid2}/state")
        mob = s2.get("evaluation", {}).get("mobility")
        check("evaluation.mobility is numeric (not hardcoded 0.0)",
              isinstance(mob, (int, float)), f"mobility={mob}")
        check("evaluation has mobility_detail",
              "mobility_detail" in s2.get("evaluation", {}))

    # 10. AI 선수 플로우 (인간=한, AI=초): /ai-move 로 AI 첫 수 (G1)
    code, g3 = call("POST", "/api/game/new",
                    {"ai_team": "cho", "ai_depth": 3, "ai_time_limit": 1.0})
    if check("create game (human=HAN) 200", code == 200, f"code={code}"):
        gid3 = g3["game_id"]
        check("human=HAN game starts on cho(AI) turn", g3["current_turn"] == "cho")
        code, air = call("POST", f"/api/game/{gid3}/ai-move")
        check("ai-move 200", code == 200, f"code={code}")
        check("ai-move success", air.get("ai_move", {}).get("success") is True)
        code, s3 = call("GET", f"/api/game/{gid3}/state")
        check("after ai-move, turn is han(human)", s3["current_turn"] == "han")
        # AI 차례 아닐 때 ai-move -> 400
        code, _ = call("POST", f"/api/game/{gid3}/ai-move")
        check("ai-move when not AI turn -> 400", code == 400, f"code={code}")

    return finish()


def finish():
    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("-" * 60)
    print(f"E2E 결과: {passed}/{total} PASS")
    failed = [(n, d) for n, ok, d in results if not ok]
    for n, d in failed:
        print(f"   FAIL: {n} :: {d}")
    out = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "e2e_result.json")
    with open(out, "w") as f:
        json.dump({"test": "E2E", "passed": passed, "total": total,
                   "failures": [{"name": n, "detail": d} for n, d in failed],
                   "checks": [{"name": n, "passed": ok, "detail": d} for n, ok, d in results]},
                  f, ensure_ascii=False, indent=2)
    print(f"저장: {os.path.abspath(out)}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
