"""오케스트레이터 통합 테스트"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.orchestrator.orchestrator import JanggiOrchestrator


def test_orchestrator_create_game():
    """게임 생성 테스트"""
    orch = JanggiOrchestrator(ai_depth=3, ai_time_limit=1.0,
                               storage_dir="/tmp/janggi_test")
    state = orch.create_game()

    assert "game_id" in state
    assert state["status"] == "playing"
    assert state["current_turn"] == "cho"
    assert len(state["board"]) == 10
    assert len(state["board"][0]) == 9

    print(f"OK test_orchestrator_create_game (game_id: {state['game_id'][:8]}...)")
    return state["game_id"], orch


def test_orchestrator_pipeline():
    """5개 에이전트 파이프라인 테스트"""
    game_id, orch = test_orchestrator_create_game()

    # 인간 수: 졸 전진
    human_result = orch.human_move(game_id, 3, 4, 4, 4)
    assert human_result["success"], f"Human move failed: {human_result}"

    # AI 수 (5개 에이전트 파이프라인)
    ai_result = orch.ai_move(game_id)
    assert ai_result["success"], f"AI move failed: {ai_result}"

    # 에이전트 결과 확인
    agents = ai_result.get("agent_results", {})
    for agent_name in ["strategy", "usecase", "winloss", "risk", "report"]:
        assert agent_name in agents, f"Missing agent: {agent_name}"
        assert agents[agent_name]["status"] == "success", \
            f"Agent {agent_name} failed: {agents[agent_name]}"

    # 보고서 확인
    assert "report" in ai_result
    assert "win_probability" in ai_result

    print(f"OK test_orchestrator_pipeline "
          f"(time: {ai_result.get('total_pipeline_time', 0)}s, "
          f"win_prob: {ai_result.get('win_probability', 0)}%)")


def test_orchestrator_analysis():
    """AI 분석 조회 테스트"""
    game_id, orch = test_orchestrator_create_game()

    # 수 두기
    orch.human_move(game_id, 3, 4, 4, 4)
    orch.ai_move(game_id)

    # 분석 조회
    analysis = orch.get_analysis(game_id)
    assert "analysis_history" in analysis
    assert "agent_status" in analysis
    assert len(analysis["analysis_history"]) > 0

    print("OK test_orchestrator_analysis")


def test_orchestrator_valid_moves():
    """유효 이동 조회 테스트"""
    game_id, orch = test_orchestrator_create_game()
    moves = orch.get_valid_moves(game_id, 3, 4)  # 초 졸
    assert len(moves) > 0

    print(f"OK test_orchestrator_valid_moves ({len(moves)} moves)")


def test_orchestrator_stats():
    """통계 테스트"""
    _, orch = test_orchestrator_create_game()
    stats = orch.get_stats()
    assert "total_games" in stats
    assert "elo_rating" in stats
    assert "win_rate" in stats

    print(f"OK test_orchestrator_stats (elo: {stats['elo_rating']})")


if __name__ == "__main__":
    test_orchestrator_create_game()
    test_orchestrator_pipeline()
    test_orchestrator_analysis()
    test_orchestrator_valid_moves()
    test_orchestrator_stats()
    print("\n=== All orchestrator tests passed! ===")
