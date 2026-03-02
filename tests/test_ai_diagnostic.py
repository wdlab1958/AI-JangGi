"""AI 진단 테스트: 평가 대칭성, 탐색 품질, 자가 대전

HAN이 CHO에 체계적으로 패하는 원인을 규명.
"""
import sys, os, time, math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.engine.board import Board
from backend.engine.pieces import Piece, PieceType, Team
from backend.engine.evaluator import Evaluator
from backend.engine.search import SearchEngine


def print_board(board: Board):
    """보드 상태를 시각적으로 출력"""
    symbols = {
        (PieceType.KING, Team.CHO): "楚",
        (PieceType.KING, Team.HAN): "漢",
        (PieceType.CAR, Team.CHO): "車c",
        (PieceType.CAR, Team.HAN): "車h",
        (PieceType.CANNON, Team.CHO): "包c",
        (PieceType.CANNON, Team.HAN): "包h",
        (PieceType.HORSE, Team.CHO): "馬c",
        (PieceType.HORSE, Team.HAN): "馬h",
        (PieceType.ELEPHANT, Team.CHO): "象c",
        (PieceType.ELEPHANT, Team.HAN): "象h",
        (PieceType.GUARD, Team.CHO): "士c",
        (PieceType.GUARD, Team.HAN): "士h",
        (PieceType.PAWN, Team.CHO): "卒c",
        (PieceType.PAWN, Team.HAN): "兵h",
    }
    print("   0    1    2    3    4    5    6    7    8")
    print("  " + "─" * 45)
    for r in range(10):
        row_str = f"{r}│"
        for c in range(9):
            p = board.grid[r][c]
            if p:
                s = symbols.get((p.piece_type, p.team), "??")
                row_str += f" {s:>3} "
            else:
                row_str += "  ·  "
        print(row_str + "│")
    print("  " + "─" * 45)


def test_evaluation_symmetry():
    """테스트 1: 초기 배치에서 양측 평가 대칭성 검증"""
    print("=" * 60)
    print("TEST 1: 평가 대칭성 검증")
    print("=" * 60)

    board = Board()
    board.setup_initial_position()
    evaluator = Evaluator()

    for phase in ["opening", "midgame", "endgame"]:
        cho_eval = evaluator.evaluate_detailed(board, Team.CHO, phase)
        han_eval = evaluator.evaluate_detailed(board, Team.HAN, phase)

        print(f"\n[{phase}]")
        print(f"  CHO 관점: total={cho_eval['total']:+.2f}  material={cho_eval['material']:+.2f}  "
              f"position={cho_eval['position']:+.2f}  king_safety={cho_eval['king_safety']:+.2f}")
        print(f"  HAN 관점: total={han_eval['total']:+.2f}  material={han_eval['material']:+.2f}  "
              f"position={han_eval['position']:+.2f}  king_safety={han_eval['king_safety']:+.2f}")

        # 대칭이면 양측 평가의 합이 0
        total_sum = cho_eval['total'] + han_eval['total']
        print(f"  합계 (0이어야 대칭): {total_sum:+.4f}")

        if abs(total_sum) > 0.01:
            print(f"  ** 비대칭 감지! 차이: {total_sum:+.4f} **")
            # 상세 분석
            _diagnose_asymmetry(board, evaluator, phase)
        else:
            print(f"  ✓ 대칭 OK")


def _diagnose_asymmetry(board, evaluator, phase):
    """비대칭 원인 분석"""
    # Position score 분석
    cho_pos = evaluator._position_score(board, Team.CHO)
    han_pos = evaluator._position_score(board, Team.HAN)
    print(f"    Position: CHO={cho_pos:.2f}  HAN={han_pos:.2f}  diff={cho_pos - han_pos:.2f}")

    # King safety 분석
    cho_ks = evaluator._king_safety(board, Team.CHO)
    han_ks = evaluator._king_safety(board, Team.HAN)
    print(f"    KingSafety: CHO={cho_ks:.2f}  HAN={han_ks:.2f}  diff={cho_ks - han_ks:.2f}")

    # Threats 분석
    cho_thr = evaluator._threat_score(board, Team.CHO, Team.HAN)
    han_thr = evaluator._threat_score(board, Team.HAN, Team.CHO)
    print(f"    Threats: CHO={cho_thr:.2f}  HAN={han_thr:.2f}  diff={cho_thr - han_thr:.2f}")

    # Structure 분석
    cho_str = evaluator._structure_score(board, Team.CHO)
    han_str = evaluator._structure_score(board, Team.HAN)
    print(f"    Structure: CHO={cho_str:.2f}  HAN={han_str:.2f}  diff={cho_str - han_str:.2f}")

    # 각 기물의 위치 점수 비교
    print(f"    --- 기물별 위치 점수 ---")
    from backend.engine.evaluator import POSITION_TABLE
    for pt in PieceType:
        cho_pieces = [p for p in board.get_team_pieces(Team.CHO) if p.piece_type == pt]
        han_pieces = [p for p in board.get_team_pieces(Team.HAN) if p.piece_type == pt]
        table = POSITION_TABLE.get(pt)
        if table is None:
            continue
        cho_sum = sum(table[p.row][p.col] for p in cho_pieces)
        han_sum = sum(table[9 - p.row][p.col] for p in han_pieces)
        if cho_sum != han_sum:
            print(f"    ** {pt.value}: CHO={cho_sum}  HAN={han_sum}  DIFF={cho_sum - han_sum} **")
            for p in cho_pieces:
                print(f"       CHO {pt.value} at ({p.row},{p.col}): table[{p.row}][{p.col}]={table[p.row][p.col]}")
            for p in han_pieces:
                flipped = 9 - p.row
                print(f"       HAN {pt.value} at ({p.row},{p.col}): table[{flipped}][{p.col}]={table[flipped][p.col]}")


def test_search_symmetry():
    """테스트 2: 양측 탐색 결과 비교"""
    print("\n" + "=" * 60)
    print("TEST 2: 탐색 대칭성 검증")
    print("=" * 60)

    board = Board()
    board.setup_initial_position()

    for depth in [1, 2, 3]:
        engine = SearchEngine(max_depth=depth, time_limit=10.0)

        # CHO 탐색
        t0 = time.time()
        cho_result = engine.find_best_move(board, Team.CHO, "opening")
        cho_time = time.time() - t0

        # HAN 탐색
        engine2 = SearchEngine(max_depth=depth, time_limit=10.0)
        t0 = time.time()
        han_result = engine2.find_best_move(board, Team.HAN, "opening")
        han_time = time.time() - t0

        cho_move = cho_result.get("move", {})
        han_move = han_result.get("move", {})

        print(f"\n  depth={depth}:")
        print(f"    CHO: score={cho_result['score']:+.2f}  depth_reached={cho_result['depth']}  "
              f"nodes={cho_result['nodes']:,}  time={cho_time:.3f}s  "
              f"move={cho_move.get('from')}->{cho_move.get('to')}  "
              f"piece={cho_move.get('piece', {}).get('hanja', '?')}")
        print(f"    HAN: score={han_result['score']:+.2f}  depth_reached={han_result['depth']}  "
              f"nodes={han_result['nodes']:,}  time={han_time:.3f}s  "
              f"move={han_move.get('from')}->{han_move.get('to')}  "
              f"piece={han_move.get('piece', {}).get('hanja', '?')}")


def test_selfplay_detailed():
    """테스트 3: 자가 대전 (동일 설정) - 상세 로그"""
    print("\n" + "=" * 60)
    print("TEST 3: 자가 대전 (동일 설정 depth=3, time=2s)")
    print("=" * 60)

    board = Board()
    board.setup_initial_position()
    evaluator = Evaluator()

    cho_engine = SearchEngine(max_depth=20, time_limit=2.0)
    han_engine = SearchEngine(max_depth=20, time_limit=2.0)

    current_team = Team.CHO
    move_count = 0
    max_moves = 40

    print_board(board)

    while move_count < max_moves:
        engine = cho_engine if current_team == Team.CHO else han_engine
        team_name = "CHO" if current_team == Team.CHO else "HAN"
        enemy = Team.HAN if current_team == Team.CHO else Team.CHO

        # 현재 상태 평가
        phase = "opening" if board.count_pieces() >= 28 else "midgame" if board.count_pieces() >= 16 else "endgame"
        eval_cho = evaluator.evaluate(board, Team.CHO, phase)
        eval_han = evaluator.evaluate(board, Team.HAN, phase)

        # 체크메이트 확인
        if board.is_checkmate(current_team):
            winner = "HAN" if current_team == Team.CHO else "CHO"
            print(f"\n  ** Turn {move_count}: {winner} WINS (checkmate on {team_name}) **")
            break

        # 합법수 확인
        all_moves = board.get_all_valid_moves(current_team)
        if not all_moves:
            winner = "HAN" if current_team == Team.CHO else "CHO"
            print(f"\n  ** Turn {move_count}: {winner} WINS (no legal moves for {team_name}) **")
            break

        # 탐색
        result = engine.find_best_move(board, current_team, phase)
        move = result.get("move")
        if move is None:
            print(f"\n  ** Turn {move_count}: {team_name} has no best move **")
            break

        fr, fc = move["from"]
        tr, tc = move["to"]
        piece_info = move.get("piece", {})
        piece_hanja = piece_info.get("hanja", "?")

        captured = board.move_piece(fr, fc, tr, tc)

        # 이동 후 상태
        in_check = board.is_in_check(enemy)
        cho_mat = board.count_material(Team.CHO)
        han_mat = board.count_material(Team.HAN)

        capture_str = f" x{captured.hanja}" if captured else ""
        check_str = " CHECK!" if in_check else ""

        print(f"  Turn {move_count:2d} {team_name}: {piece_hanja}({fr},{fc})->({tr},{tc}){capture_str}"
              f"  score={result['score']:+.2f}  d={result['depth']}  n={result['nodes']:,}"
              f"  eval_cho={eval_cho:+.2f}  eval_han={eval_han:+.2f}"
              f"  mat={cho_mat}v{han_mat}{check_str}")

        move_count += 1
        current_team = enemy

    print(f"\n  Final board:")
    print_board(board)

    cho_mat = board.count_material(Team.CHO)
    han_mat = board.count_material(Team.HAN)
    print(f"  Final material: CHO={cho_mat}  HAN={han_mat}  diff={cho_mat - han_mat}")


def test_selfplay_strong_vs_weak():
    """테스트 4: 강한 AI(HAN) vs 약한 AI(CHO) - 이전 테스트 재현"""
    print("\n" + "=" * 60)
    print("TEST 4: 강한 HAN (time=3s) vs 약한 CHO (time=1s)")
    print("=" * 60)

    board = Board()
    board.setup_initial_position()
    evaluator = Evaluator()

    cho_engine = SearchEngine(max_depth=20, time_limit=1.0)  # 약한
    han_engine = SearchEngine(max_depth=20, time_limit=3.0)  # 강한

    current_team = Team.CHO
    move_count = 0
    max_moves = 60

    while move_count < max_moves:
        engine = cho_engine if current_team == Team.CHO else han_engine
        team_name = "CHO" if current_team == Team.CHO else "HAN"
        enemy = Team.HAN if current_team == Team.CHO else Team.CHO

        phase = "opening" if board.count_pieces() >= 28 else "midgame" if board.count_pieces() >= 16 else "endgame"

        if board.is_checkmate(current_team):
            winner = "HAN" if current_team == Team.CHO else "CHO"
            print(f"\n  ** {winner} WINS by checkmate at turn {move_count}! **")
            print_board(board)
            return winner

        all_moves = board.get_all_valid_moves(current_team)
        if not all_moves:
            winner = "HAN" if current_team == Team.CHO else "CHO"
            print(f"\n  ** {winner} WINS (no legal moves) at turn {move_count}! **")
            return winner

        result = engine.find_best_move(board, current_team, phase)
        move = result.get("move")
        if move is None:
            print(f"  ** {team_name}: no move found **")
            break

        fr, fc = move["from"]
        tr, tc = move["to"]
        piece = board.get_piece(fr, fc)
        captured = board.move_piece(fr, fc, tr, tc)

        in_check = board.is_in_check(enemy)
        cho_mat = board.count_material(Team.CHO)
        han_mat = board.count_material(Team.HAN)

        eval_current = evaluator.evaluate(board, current_team, phase)

        capture_str = f" x{captured.hanja}" if captured else ""
        check_str = " +CHECK" if in_check else ""

        print(f"  T{move_count:2d} {team_name}: {piece.hanja}({fr},{fc})->({tr},{tc}){capture_str}"
              f"  sc={result['score']:+.1f} d={result['depth']} n={result['nodes']:,}"
              f"  mat={cho_mat}v{han_mat}  eval({team_name})={eval_current:+.1f}{check_str}")

        move_count += 1
        current_team = enemy

    print(f"\n  Draw (max moves reached)")
    return "draw"


def test_negamax_correctness():
    """테스트 5: Negamax 정확성 (간단한 전술 포지션)"""
    print("\n" + "=" * 60)
    print("TEST 5: Negamax 정확성 - 전술 포지션")
    print("=" * 60)

    # 빈 보드에 왕과 차만 놓기
    board = Board()
    board.grid = [[None]*9 for _ in range(10)]
    board.pieces = []
    board.zobrist_hash = 0

    # CHO: 왕(1,4), 차(5,0)
    board._place(PieceType.KING, Team.CHO, 1, 4)
    board._place(PieceType.CAR, Team.CHO, 5, 0)

    # HAN: 왕(8,4), 졸(5,4)
    board._place(PieceType.KING, Team.HAN, 8, 4)
    board._place(PieceType.PAWN, Team.HAN, 5, 4)

    print("  CHO: 王(1,4), 車(5,0)")
    print("  HAN: 漢(8,4), 兵(5,4)")
    print("  CHO 차가 HAN 졸을 잡을 수 있어야 함")

    engine = SearchEngine(max_depth=3, time_limit=5.0)
    result = engine.find_best_move(board, Team.CHO, "endgame")
    move = result.get("move", {})
    print(f"  CHO best: {move.get('piece',{}).get('hanja','?')} "
          f"{move.get('from')}->{move.get('to')}  score={result['score']:+.2f}")

    if move.get("to") == (5, 4):
        print("  ✓ 정확: 차가 졸을 잡음")
    else:
        print(f"  ✗ 오류: 차가 졸을 안 잡음! to={move.get('to')}")


def test_hash_consistency():
    """테스트 6: Zobrist 해시 일관성"""
    print("\n" + "=" * 60)
    print("TEST 6: Zobrist 해시 일관성")
    print("=" * 60)

    board = Board()
    board.setup_initial_position()

    h0 = board.zobrist_hash
    print(f"  Initial hash: {h0}")

    # 여러 번 move/undo 후 해시가 동일한지
    moves_to_test = [
        (3, 4, 4, 4),  # CHO pawn forward
        (6, 4, 5, 4),  # HAN pawn forward
        (0, 0, 2, 0),  # CHO car
    ]

    for fr, fc, tr, tc in moves_to_test:
        piece = board.get_piece(fr, fc)
        if piece is None:
            print(f"  No piece at ({fr},{fc}), skipping")
            continue
        board.move_piece(fr, fc, tr, tc)

    for _ in moves_to_test:
        board.undo_move()

    h_after = board.zobrist_hash
    print(f"  After move/undo cycles: {h_after}")
    print(f"  Hash match: {'✓' if h0 == h_after else '✗ MISMATCH!'}")


def test_double_move_generation():
    """테스트 7: negamax 내 중복 이동 생성 성능 영향"""
    print("\n" + "=" * 60)
    print("TEST 7: 탐색 성능 측정")
    print("=" * 60)

    board = Board()
    board.setup_initial_position()

    for time_limit in [1.0, 2.0, 3.0]:
        engine = SearchEngine(max_depth=20, time_limit=time_limit)

        t0 = time.time()
        result = engine.find_best_move(board, Team.CHO, "opening")
        elapsed = time.time() - t0

        nps = result['nodes'] / elapsed if elapsed > 0 else 0
        print(f"  time_limit={time_limit}s: depth={result['depth']}  "
              f"nodes={result['nodes']:,}  time={elapsed:.3f}s  nps={nps:,.0f}")


def test_move_validity():
    """테스트 8: 자가 대전 중 모든 반환 수가 합법인지 검증"""
    print("\n" + "=" * 60)
    print("TEST 8: 탐색 반환 수 합법성 검증 (자가 대전 30수)")
    print("=" * 60)

    board = Board()
    board.setup_initial_position()

    engine = SearchEngine(max_depth=20, time_limit=1.0)
    current_team = Team.CHO
    invalid_count = 0
    total_moves = 0

    for turn in range(30):
        enemy = Team.HAN if current_team == Team.CHO else Team.CHO
        team_name = "CHO" if current_team == Team.CHO else "HAN"

        if board.is_checkmate(current_team):
            print(f"  Checkmate at turn {turn}")
            break

        # 탐색 전 합법수 목록 저장
        all_valid = board.get_all_valid_moves(current_team)
        if not all_valid:
            print(f"  No legal moves at turn {turn}")
            break

        valid_set = set()
        for p, r, c in all_valid:
            valid_set.add((p.row, p.col, r, c))

        # 보드 해시 & 기물 위치 스냅샷 (검증용)
        hash_before = board.zobrist_hash
        positions_before = [(p.row, p.col, p.captured) for p in board.pieces]

        phase = "opening" if board.count_pieces() >= 28 else \
                "midgame" if board.count_pieces() >= 16 else "endgame"

        result = engine.find_best_move(board, current_team, phase)

        # 탐색 후 보드 상태 불변 검증
        hash_after = board.zobrist_hash
        positions_after = [(p.row, p.col, p.captured) for p in board.pieces]

        if hash_before != hash_after:
            print(f"  !! T{turn} {team_name}: HASH CORRUPTION after search! "
                  f"{hash_before} -> {hash_after}")
        if positions_before != positions_after:
            print(f"  !! T{turn} {team_name}: POSITION CORRUPTION after search!")
            for i, (b, a) in enumerate(zip(positions_before, positions_after)):
                if b != a:
                    p = board.pieces[i]
                    print(f"     piece {p.piece_type.value}/{p.team.value}: "
                          f"({b[0]},{b[1]},cap={b[2]}) -> ({a[0]},{a[1]},cap={a[2]})")

        move = result.get("move")
        if move is None:
            print(f"  T{turn} {team_name}: no move returned")
            break

        fr, fc = move["from"]
        tr, tc = move["to"]
        total_moves += 1

        # 합법수 검증
        if (fr, fc, tr, tc) not in valid_set:
            invalid_count += 1
            piece_info = move.get("piece", {})
            pt = piece_info.get("type", "?")
            # 해당 기물의 실제 합법수 출력
            piece_on_board = board.grid[fr][fc]
            if piece_on_board:
                actual_valid = board.get_valid_moves(piece_on_board)
                print(f"  !! T{turn} {team_name} INVALID: {pt}({fr},{fc})->({tr},{tc}) "
                      f"d={result['depth']} score={result['score']}")
                print(f"     Piece at ({fr},{fc}): {piece_on_board.piece_type.value}"
                      f"/{piece_on_board.team.value}")
                print(f"     Valid targets: {actual_valid[:10]}")
            else:
                print(f"  !! T{turn} {team_name} INVALID: No piece at ({fr},{fc})!")
                print(f"     Returned: {pt}({fr},{fc})->({tr},{tc})")
        else:
            p_hanja = move.get("piece", {}).get("hanja", "?")
            captured = board.move_piece(fr, fc, tr, tc)
            cap_str = f" x{captured.hanja}" if captured else ""
            print(f"  T{turn:2d} {team_name}: {p_hanja}({fr},{fc})->({tr},{tc}){cap_str}"
                  f"  d={result['depth']} sc={result['score']:+.1f}")
            current_team = enemy
            continue

        # 불법수인 경우 수동으로 합법수 선택하여 계속 진행
        p, r, c = all_valid[0]
        board.move_piece(p.row, p.col, r, c)
        current_team = enemy

    print(f"\n  결과: {total_moves}수 중 불법수 {invalid_count}개"
          f" {'✓ ALL VALID' if invalid_count == 0 else '✗ INVALID MOVES FOUND'}")
    return invalid_count == 0


if __name__ == "__main__":
    test_evaluation_symmetry()
    test_search_symmetry()
    test_hash_consistency()
    test_negamax_correctness()
    test_double_move_generation()
    test_move_validity()
    test_selfplay_strong_vs_weak()
