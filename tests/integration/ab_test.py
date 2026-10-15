"""A/B Test: 탐색 깊이가 다른 두 AI 설정을 AI-vs-AI 로 대결시켜 강도 차이를 검증.

가설(H1): 더 깊게 탐색하는 설정 A 가 얕게 탐색하는 설정 B 보다 승률이 높다.
귀무가설(H0): 두 설정의 승률에 차이가 없다.

선후공 효과를 제거하기 위해 매 게임마다 A/B 가 번갈아 초(CHO)/한(HAN)을 잡는다.
"""
import sys
import os
import json
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from backend.engine.board import Board
from backend.engine.pieces import Team
from backend.engine.evaluator import Evaluator
from backend.engine.search import SearchEngine

CONFIG_A = {"name": "A(deep d4/t1.0)", "max_depth": 4, "time_limit": 1.0}
CONFIG_B = {"name": "B(shallow d1/t0.3)", "max_depth": 1, "time_limit": 0.3}

PLY_CAP = 70
N_GAMES = 4


def is_no_moves(board, team):
    return len(board.get_all_valid_moves(team)) == 0


def play_game(engine_cho, engine_bcho_label, engine_han, cfg_cho_name, cfg_han_name):
    """한 게임 진행. 반환: ('cho'|'han'|'draw', stats dict)"""
    board = Board()
    board.setup_initial_position("내상외마", "내상외마")
    evaluator = Evaluator()
    turn = Team.CHO
    move_count = 0
    pos_hist = {}
    node_total = {"cho": 0, "han": 0}
    move_total = {"cho": 0, "han": 0}
    time_total = {"cho": 0.0, "han": 0.0}

    def phase_of():
        n = board.count_pieces()
        return "opening" if n >= 28 else ("midgame" if n >= 16 else "endgame")

    while move_count < PLY_CAP:
        engine = engine_cho if turn == Team.CHO else engine_han
        side = "cho" if turn == Team.CHO else "han"

        # 합법수 없음 → 진 것 (장기: 외통/무빙 = 패)
        if is_no_moves(board, turn):
            winner = "han" if turn == Team.CHO else "cho"
            return winner, _mk_stats(node_total, move_total, time_total, move_count, "no_moves")

        res = engine.find_best_move(board, turn, phase=phase_of(), move_count=move_count)
        mv = res.get("move")
        if mv is None:
            winner = "han" if turn == Team.CHO else "cho"
            return winner, _mk_stats(node_total, move_total, time_total, move_count, "null_move")
        node_total[side] += res.get("nodes", 0)
        time_total[side] += res.get("time", 0.0)
        move_total[side] += 1

        fr, fc = mv["from"]
        tr, tc = mv["to"]
        board.move_piece(fr, fc, tr, tc)
        engine_cho.record_position(board, turn)
        engine_han.record_position(board, turn)
        move_count += 1

        # 왕이 잡혔으면 즉시 종료(엔진이 왕 포획 수를 둘 수 있는 단순 어드주디케이션)
        if board.get_king(Team.CHO) is None:
            return "han", _mk_stats(node_total, move_total, time_total, move_count, "king_captured")
        if board.get_king(Team.HAN) is None:
            return "cho", _mk_stats(node_total, move_total, time_total, move_count, "king_captured")

        # 3회 반복 무승부
        nxt = Team.HAN if turn == Team.CHO else Team.CHO
        key = board.hash_with_side(nxt)
        pos_hist[key] = pos_hist.get(key, 0) + 1
        if pos_hist[key] >= 3:
            return "draw", _mk_stats(node_total, move_total, time_total, move_count, "repetition")

        turn = nxt

    # 수 제한 도달 → 재료/평가로 어드주디케이션 (CHO 관점)
    score = evaluator.evaluate(board, Team.CHO, phase_of())
    if score > 3:
        result = "cho"
    elif score < -3:
        result = "han"
    else:
        result = "draw"
    return result, _mk_stats(node_total, move_total, time_total, move_count, f"ply_cap(eval={score:.1f})")


def _mk_stats(node_total, move_total, time_total, plies, reason):
    def nps(side):
        return node_total[side] / time_total[side] if time_total[side] > 0 else 0
    return {
        "plies": plies,
        "reason": reason,
        "cho_nodes": node_total["cho"], "han_nodes": node_total["han"],
        "cho_moves": move_total["cho"], "han_moves": move_total["han"],
        "cho_nps": round(nps("cho")), "han_nps": round(nps("han")),
    }


def main():
    print("=" * 60)
    print("A/B TEST: 탐색 깊이 강도 비교 (AI vs AI)")
    print(f"  Config A = {CONFIG_A}")
    print(f"  Config B = {CONFIG_B}")
    print(f"  게임 수={N_GAMES}, 플라이 상한={PLY_CAP}")
    print("=" * 60)

    tally = {"A": 0, "B": 0, "draw": 0}
    games_log = []
    t0 = time.time()

    for g in range(N_GAMES):
        # 짝수 게임: A=CHO, B=HAN / 홀수 게임: B=CHO, A=HAN
        a_is_cho = (g % 2 == 0)
        engine_a = SearchEngine(CONFIG_A["max_depth"], CONFIG_A["time_limit"])
        engine_b = SearchEngine(CONFIG_B["max_depth"], CONFIG_B["time_limit"])
        if a_is_cho:
            engine_cho, engine_han = engine_a, engine_b
            cho_name, han_name = "A", "B"
        else:
            engine_cho, engine_han = engine_b, engine_a
            cho_name, han_name = "B", "A"

        winner_side, stats = play_game(engine_cho, None, engine_han, cho_name, han_name)
        if winner_side == "draw":
            winner_cfg = "draw"
        else:
            winner_cfg = cho_name if winner_side == "cho" else han_name
        tally[winner_cfg if winner_cfg != "draw" else "draw"] += 1

        line = (f"  Game {g+1}: CHO={cho_name} HAN={han_name} -> winner={winner_cfg} "
                f"({stats['reason']}, plies={stats['plies']}, "
                f"A_nps={stats['cho_nps'] if a_is_cho else stats['han_nps']}, "
                f"B_nps={stats['han_nps'] if a_is_cho else stats['cho_nps']})")
        print(line)
        games_log.append({"game": g + 1, "cho": cho_name, "han": han_name,
                          "winner": winner_cfg, **stats})

    elapsed = round(time.time() - t0, 1)
    print("-" * 60)
    print(f"결과: A={tally['A']}승  B={tally['B']}승  무={tally['draw']}  (총 {elapsed}s)")
    a_decisive = tally["A"]
    b_decisive = tally["B"]
    verdict = ("A_STRONGER" if a_decisive > b_decisive
               else "B_STRONGER" if b_decisive > a_decisive else "INCONCLUSIVE")
    hypothesis = "SUPPORTED (deeper search wins more)" if verdict == "A_STRONGER" else \
                 "NOT_SUPPORTED" if verdict == "B_STRONGER" else "INCONCLUSIVE"
    print(f"판정: {verdict}  |  가설(H1: 깊은 탐색 우세): {hypothesis}")

    result = {
        "test": "A/B",
        "config_a": CONFIG_A, "config_b": CONFIG_B,
        "n_games": N_GAMES, "ply_cap": PLY_CAP,
        "tally": tally, "verdict": verdict, "hypothesis": hypothesis,
        "elapsed_s": elapsed, "games": games_log,
    }
    out = os.path.join(os.path.dirname(__file__), "..", "..", "reports", "ab_result.json")
    with open(out, "w") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"저장: {os.path.abspath(out)}")
    # A/B 자체는 크래시 없이 완료되면 PASS
    return 0


if __name__ == "__main__":
    sys.exit(main())
