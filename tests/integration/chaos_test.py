"""Chaos Test: 비정상 입력/경쟁 조건/경계값을 주입하여 서버 견고성을 검증.

원칙: 어떤 입력에도 서버는 5xx(미처리 예외)로 죽지 않고,
      적절한 4xx 또는 정상 응답을 반환해야 하며, 테스트 종료 후 /health 가 살아있어야 한다.
"""
import sys
import os
import json
import threading
import urllib.request
import urllib.error

BASE = os.environ.get("JANGGI_API", "http://localhost:8007")
results = []


def call(method, path, body=None, raw_body=None):
    url = BASE + path
    if raw_body is not None:
        data = raw_body.encode()
    else:
        data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except Exception as e:
        return -1, str(e)


def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))
    mark = "PASS" if cond else "FAIL"
    print(f"  [{mark}] {name}" + (f" :: {detail}" if detail and not cond else ""))


def no_5xx(code):
    return not (500 <= code < 600) and code != -1


def main():
    print("=" * 60)
    print("CHAOS TEST: 비정상 입력/경쟁 조건/경계값 견고성")
    print(f"  대상: {BASE}")
    print("=" * 60)

    # 정상 게임 하나 생성 (일부 케이스에 사용)
    code, body = call("POST", "/api/game/new", {})
    gid = json.loads(body)["game_id"] if code == 200 else "x"

    # 1. 존재하지 않는 게임에 수 두기
    code, _ = call("POST", "/api/game/NOPE/move",
                   {"from_row": 3, "from_col": 0, "to_row": 4, "to_col": 0})
    check("nonexistent game move -> 4xx, not 5xx", no_5xx(code) and code >= 400, f"code={code}")

    # 2. 좌표 범위 초과 (음수/거대값)
    code, _ = call("POST", f"/api/game/{gid}/move",
                   {"from_row": -5, "from_col": 99, "to_row": 999, "to_col": -1})
    check("out-of-range coords -> no 5xx", no_5xx(code), f"code={code}")

    # 3. 내 기물이 아닌 수 (인간=CHO 상단, HAN 기물은 하단 (9,0)). 새 게임 사용.
    code, fbody = call("POST", "/api/game/new", {})
    fresh_gid = json.loads(fbody)["game_id"] if code == 200 else gid
    code, _ = call("POST", f"/api/game/{fresh_gid}/move",
                   {"from_row": 9, "from_col": 0, "to_row": 8, "to_col": 0})
    check("move opponent piece -> 4xx", no_5xx(code) and code >= 400, f"code={code}")
    # 3b. 빈 칸 기물 이동
    code, _ = call("POST", f"/api/game/{fresh_gid}/move",
                   {"from_row": 5, "from_col": 4, "to_row": 4, "to_col": 4})
    check("move from empty square -> 4xx", no_5xx(code) and code >= 400, f"code={code}")

    # 4. 누락 필드 (malformed)
    code, _ = call("POST", f"/api/game/{gid}/move", {"from_row": 3})
    check("missing fields -> 422", code == 422, f"code={code}")

    # 5. 깨진 JSON
    code, _ = call("POST", f"/api/game/{gid}/move", raw_body="{not json")
    check("broken JSON -> no 5xx", no_5xx(code), f"code={code}")

    # 6. ai_depth 검증기 (범위 밖)
    code, _ = call("POST", "/api/game/new", {"ai_depth": 999})
    check("ai_depth>30 -> 422", code == 422, f"code={code}")
    code, _ = call("POST", "/api/game/new", {"ai_time_limit": 0.0})
    check("ai_time_limit<0.1 -> 422", code == 422, f"code={code}")

    # 7. 빈 칸 valid-moves -> 200 + 빈 목록
    code, body = call("POST", f"/api/game/{gid}/valid-moves", {"row": 5, "col": 4})
    ok = code == 200 and json.loads(body).get("valid_moves") == []
    check("valid-moves on empty square -> 200 []", ok, f"code={code}")

    # 8. valid-moves 좌표 초과
    code, _ = call("POST", f"/api/game/{gid}/valid-moves", {"row": 50, "col": 50})
    check("valid-moves out-of-range -> no 5xx", no_5xx(code), f"code={code}")

    # 9. 시작 시점 undo (수가 없는 새 게임)
    code, ubody = call("POST", "/api/game/new", {})
    undo_gid = json.loads(ubody)["game_id"] if code == 200 else gid
    code, _ = call("POST", f"/api/game/{undo_gid}/undo")
    check("undo at start -> 4xx", no_5xx(code) and code >= 400, f"code={code}")

    # 10. 존재하지 않는 게임 보고서/상태/분석
    for ep in ("state", "analysis", "report"):
        code, _ = call("GET", f"/api/game/NOPE/{ep}")
        check(f"GET {ep} nonexistent -> 404", code == 404, f"code={code}")

    # 11. 대량 게임 생성 (자원 누수/크래시 점검)
    created = 0
    for _ in range(50):
        code, _ = call("POST", "/api/game/new", {})
        if code == 200:
            created += 1
    check("bulk create 50 games", created == 50, f"created={created}")

    # 12. 동시 요청 경쟁 조건 (같은 게임에 병렬 수)
    codes = []
    lock = threading.Lock()

    def worker():
        c, _ = call("POST", f"/api/game/{gid}/move",
                    {"from_row": 3, "from_col": 0, "to_row": 4, "to_col": 0})
        with lock:
            codes.append(c)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    check("concurrent moves -> no 5xx (server survives)",
          all(no_5xx(c) for c in codes), f"codes={codes}")

    # 13. 잘못된 타입 (문자열 좌표)
    code, _ = call("POST", f"/api/game/{gid}/move",
                   {"from_row": "a", "from_col": "b", "to_row": 1, "to_col": 1})
    check("string coords -> 422", code == 422, f"code={code}")

    # 14. 최종 헬스 체크 (서버 생존)
    code, _ = call("GET", "/health")
    check("server still healthy after chaos", code == 200, f"code={code}")

    passed = sum(1 for _, ok, _ in results if ok)
    total = len(results)
    print("-" * 60)
    print(f"CHAOS 결과: {passed}/{total} PASS")
    for n, ok, d in results:
        if not ok:
            print(f"   FAIL: {n} :: {d}")
    out = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "chaos_result.json")
    with open(out, "w") as f:
        json.dump({"test": "Chaos", "passed": passed, "total": total,
                   "checks": [{"name": n, "passed": ok, "detail": d} for n, ok, d in results]},
                  f, ensure_ascii=False, indent=2)
    print(f"저장: {os.path.abspath(out)}")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
