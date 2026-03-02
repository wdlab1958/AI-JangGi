"""Agent 1: 장기 게임 전략 분석가 (Strategy Analyst)

역할: 현재 판면 분석, 전략 수립 및 최적의 수 결정
입력: 현재 보드 상태, 각 기물 위치/종류, 진행된 수 기록, 상대방 행동 패턴
처리: ① 판면 평가 → ② 후보수 생성 → ③ 전략 패턴 매칭 → ④ 최적수 추천
출력: {추천수, 평가점수, 전략근거, 후보수_목록, 판면_분석_요약}
"""
from .base_agent import BaseAgent
from ..engine.board import Board
from ..engine.pieces import Piece, PieceType, Team
from ..engine.evaluator import Evaluator
from ..engine.search import SearchEngine


class StrategyAnalyst(BaseAgent):
    """전략 분석가 에이전트"""

    def __init__(self, max_depth: int = 20, time_limit: float = 5.0):
        super().__init__(
            agent_id="agent_1_strategy",
            name="전략 분석가",
            role="현재 판면 분석, 전략 수립 및 최적의 수 결정",
        )
        self.evaluator = Evaluator()
        self.search_engine = SearchEngine(max_depth=max_depth, time_limit=time_limit)

    def execute(self, input_data: dict) -> dict:
        """
        input_data:
            - board: Board 객체
            - team: Team (AI 팀)
            - memory_context: dict (메모리 컨텍스트)
        """
        board: Board = input_data["board"]
        team: Team = input_data["team"]
        phase: str = input_data.get("phase", "midgame")
        memory_ctx = input_data.get("memory_context", {})

        # ① 판면 평가
        evaluation = self.evaluator.evaluate_detailed(board, team, phase)

        # ② 후보수 생성 (Minimax + Alpha-Beta + PVS + Quiescence)
        move_count = input_data.get("move_count", 0)
        search_result = self.search_engine.find_best_move(
            board, team, phase, move_count=move_count)

        # ③ 전략 패턴 매칭
        strategy_reasoning = self._generate_strategy_reasoning(
            board, team, evaluation, search_result, memory_ctx
        )

        # ④ 최적수 추천 및 근거 제시
        recommended_move = search_result.get("move")
        candidates = search_result.get("candidates", [])

        return {
            "recommended_move": recommended_move,
            "evaluation": evaluation,
            "candidates": candidates,
            "strategy_reasoning": strategy_reasoning,
            "search_stats": {
                "depth": search_result.get("depth", 0),
                "nodes": search_result.get("nodes", 0),
                "time": search_result.get("time", 0),
                "score": search_result.get("score", 0),
            },
            "board_summary": self._summarize_board(board, team),
        }

    def _generate_strategy_reasoning(self, board: Board, team: Team,
                                       evaluation: dict, search_result: dict,
                                       memory_ctx: dict) -> str:
        """전략 근거 텍스트 생성"""
        score = evaluation["total"]
        material = evaluation["material"]
        move = search_result.get("move", {})

        reasons = []

        # 기물 우위/열세 판단
        if material > 3:
            reasons.append("기물 우위 상태. 교환 유도하여 우위 확정 전략 권장.")
        elif material < -3:
            reasons.append("기물 열세 상태. 역공 기회 탐색 또는 방어 강화 필요.")
        else:
            reasons.append("기물 균형 상태. 위치적 이점 확보 전략 추진.")

        # 포지션 평가
        if evaluation["position"] > 2:
            reasons.append("위치적 이점 확보. 중앙 제어 유지하며 공격 진행.")
        elif evaluation["position"] < -2:
            reasons.append("위치적 열세. 기물 재배치를 통한 포지션 개선 필요.")

        # 기동성 평가
        if evaluation["mobility"] > 5:
            reasons.append("높은 기동성 확보. 다양한 공격 옵션 활용 가능.")
        elif evaluation["mobility"] < -5:
            reasons.append("기동성 저하. 기물 활성화 및 공간 확보 필요.")

        # 왕 안전도
        if evaluation["king_safety"] < -5:
            reasons.append("왕 안전도 위험. 방어 기물 보강 우선.")

        # 상대 패턴 기반 전략
        opponent_profile = memory_ctx.get("short_term", {}).get("opponent_profile", {})
        if opponent_profile:
            style = opponent_profile.get("play_style", "balanced")
            if style == "aggressive":
                reasons.append("상대 공격적 성향. 역공 함정 설치 및 방어 강화.")
            elif style == "defensive":
                reasons.append("상대 수비적 성향. 포위 전략으로 압박 강화.")

        return " ".join(reasons)

    def _summarize_board(self, board: Board, team: Team) -> dict:
        """보드 요약"""
        enemy = Team.HAN if team == Team.CHO else Team.CHO
        my_pieces = board.get_team_pieces(team)
        enemy_pieces = board.get_team_pieces(enemy)

        return {
            "my_pieces_count": len(my_pieces),
            "enemy_pieces_count": len(enemy_pieces),
            "my_material": sum(p.value for p in my_pieces),
            "enemy_material": sum(p.value for p in enemy_pieces),
            "my_pieces": {pt.value: sum(1 for p in my_pieces if p.piece_type == pt)
                         for pt in PieceType if sum(1 for p in my_pieces if p.piece_type == pt) > 0},
            "enemy_pieces": {pt.value: sum(1 for p in enemy_pieces if p.piece_type == pt)
                            for pt in PieceType if sum(1 for p in enemy_pieces if p.piece_type == pt) > 0},
        }
