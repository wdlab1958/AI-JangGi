"""장기 게임 엔진 테스트"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.engine.board import Board
from backend.engine.pieces import Piece, PieceType, Team
from backend.engine.evaluator import Evaluator
from backend.engine.search import SearchEngine
from backend.engine.game import Game


def test_board_setup():
    """초기 배치 테스트"""
    board = Board()
    board.setup_initial_position()

    # 총 32개 기물
    assert len(board.pieces) == 32, f"Expected 32 pieces, got {len(board.pieces)}"

    # 초 16개, 한 16개
    cho = [p for p in board.pieces if p.team == Team.CHO]
    han = [p for p in board.pieces if p.team == Team.HAN]
    assert len(cho) == 16, f"CHO: {len(cho)}"
    assert len(han) == 16, f"HAN: {len(han)}"

    # 왕 확인
    cho_king = board.get_king(Team.CHO)
    han_king = board.get_king(Team.HAN)
    assert cho_king is not None
    assert han_king is not None
    assert cho_king.row == 1 and cho_king.col == 4
    assert han_king.row == 8 and han_king.col == 4

    print("OK test_board_setup")


def test_piece_moves():
    """기물 이동 규칙 테스트"""
    board = Board()
    board.setup_initial_position()

    # 졸(pawn) 이동: 초 졸은 위(row+)로 전진
    pawn = board.get_piece(3, 0)  # 초 졸
    assert pawn is not None
    assert pawn.piece_type == PieceType.PAWN
    moves = board.get_valid_moves(pawn)
    assert len(moves) > 0, "Pawn should have valid moves"
    assert (4, 0) in moves, f"Pawn at (3,0) should be able to move to (4,0), got {moves}"

    # 차(car) 이동 - 초기 위치에서는 양쪽 길이 다른 기물에 막혀있음
    car = board.get_piece(0, 0)  # 초 차
    assert car is not None
    assert car.piece_type == PieceType.CAR

    # 마(horse) 이동 확인
    horse = board.get_piece(0, 1)  # 위치는 포메이션에 따라 다를 수 있음
    if horse and horse.piece_type == PieceType.HORSE:
        moves = board.get_valid_moves(horse)
        # 초기 위치에서 마는 멀발로 일부 이동만 가능
        assert isinstance(moves, list)

    print("OK test_piece_moves")


def test_move_execution():
    """수 실행 및 되돌리기 테스트"""
    board = Board()
    board.setup_initial_position()

    # 졸 전진
    pawn = board.get_piece(3, 4)
    assert pawn is not None
    board.move_piece(3, 4, 4, 4)
    assert board.get_piece(4, 4) == pawn
    assert board.get_piece(3, 4) is None
    assert pawn.row == 4 and pawn.col == 4

    # 되돌리기
    board.undo_move()
    assert board.get_piece(3, 4) == pawn
    assert board.get_piece(4, 4) is None
    assert pawn.row == 3 and pawn.col == 4

    print("OK test_move_execution")


def test_evaluator():
    """판면 평가 함수 테스트"""
    board = Board()
    board.setup_initial_position()
    evaluator = Evaluator()

    # 초기 상태는 대칭이므로 점수가 0에 가까워야 함
    score_cho = evaluator.evaluate(board, Team.CHO)
    score_han = evaluator.evaluate(board, Team.HAN)

    # 대칭이므로 부호가 반대
    assert abs(score_cho + score_han) < 2.0, f"Scores should be roughly opposite: {score_cho}, {score_han}"

    # 상세 평가
    detail = evaluator.evaluate_detailed(board, Team.CHO)
    assert "total" in detail
    assert "material" in detail
    assert "position" in detail
    assert "mobility" in detail
    assert "king_safety" in detail

    print("OK test_evaluator")


def test_search_engine():
    """탐색 엔진 테스트"""
    board = Board()
    board.setup_initial_position()

    engine = SearchEngine(max_depth=3, time_limit=2.0)
    result = engine.find_best_move(board, Team.CHO)

    assert result is not None
    assert "move" in result
    assert result["move"] is not None
    assert "from" in result["move"]
    assert "to" in result["move"]
    assert "score" in result

    print(f"OK test_search_engine (depth={result.get('depth')}, "
          f"nodes={result.get('nodes')}, time={result.get('time')}s)")


def test_game_session():
    """게임 세션 테스트"""
    game = Game(ai_depth=3, ai_time_limit=1.0)

    state = game.get_state()
    assert state["status"] == "playing"
    assert state["current_turn"] == "cho"
    assert state["move_count"] == 0

    # 졸 전진 (유효 수)
    valid = game.get_valid_moves_for_position(3, 4)
    assert len(valid) > 0

    result = game.make_human_move(3, 4, 4, 4)
    assert result["success"], f"Move failed: {result}"
    assert result["move_count"] == 1

    # AI 수
    ai_result = game.make_ai_move()
    assert ai_result["success"], f"AI move failed: {ai_result}"
    assert ai_result["move_count"] == 2

    print("OK test_game_session")


def test_check_detection():
    """장군 판정 테스트"""
    board = Board()
    board.setup_initial_position()

    # 초기 상태에서는 장군이 아님
    assert not board.is_in_check(Team.CHO)
    assert not board.is_in_check(Team.HAN)

    # 체크메이트도 아님
    assert not board.is_checkmate(Team.CHO)
    assert not board.is_checkmate(Team.HAN)

    print("OK test_check_detection")


def test_all_valid_moves():
    """모든 유효수 생성 테스트"""
    board = Board()
    board.setup_initial_position()

    cho_moves = board.get_all_valid_moves(Team.CHO)
    han_moves = board.get_all_valid_moves(Team.HAN)

    assert len(cho_moves) > 0, "CHO should have valid moves"
    assert len(han_moves) > 0, "HAN should have valid moves"

    print(f"OK test_all_valid_moves (CHO: {len(cho_moves)}, HAN: {len(han_moves)})")


if __name__ == "__main__":
    test_board_setup()
    test_piece_moves()
    test_move_execution()
    test_evaluator()
    test_search_engine()
    test_game_session()
    test_check_detection()
    test_all_valid_moves()
    print("\n=== All tests passed! ===")
