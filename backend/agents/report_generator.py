"""Agent 5: 게임 결과 보고서 생성자 (Report Generator)

역할: 경기 결과 종합 보고서 자동 생성, 분석 시각화, 통계 대시보드 제공
입력: 전체 경기 데이터, 각 에이전트 분석 결과, 승률 통계, 리스크 평가 결과
처리: ① 경기 요약 → ② 턴별 분석 → ③ Critical Turn 식별 → ④ 시각화 → ⑤ 보고서 출력
출력: 웹 대시보드 데이터, JSON API 응답
"""
import time
from .base_agent import BaseAgent


class ReportGenerator(BaseAgent):
    """게임 결과 보고서 생성자 에이전트"""

    def __init__(self):
        super().__init__(
            agent_id="agent_5_report",
            name="보고서 생성자",
            role="경기 결과 종합 보고서 자동 생성",
        )

    def execute(self, input_data: dict) -> dict:
        """
        input_data:
            - strategy_result: Agent 1 결과
            - usecase_result: Agent 2 결과
            - winloss_result: Agent 3 결과
            - risk_result: Agent 4 결과
            - game_state: dict (현재 게임 상태)
            - move_number: int
        """
        strategy = input_data.get("strategy_result", {})
        usecase = input_data.get("usecase_result", {})
        winloss = input_data.get("winloss_result", {})
        risk = input_data.get("risk_result", {})
        game_state = input_data.get("game_state", {})
        move_number = input_data.get("move_number", 0)

        # ① 경기 요약 생성
        summary = self._generate_summary(
            strategy, usecase, winloss, risk, game_state
        )

        # ② 턴별 분석
        turn_analysis = self._generate_turn_analysis(
            strategy, usecase, winloss, risk, move_number
        )

        # ③ Critical Turn 식별
        critical_turns = winloss.get("critical_turns", [])

        # ④ 대시보드 데이터
        dashboard_data = self._generate_dashboard_data(
            strategy, winloss, risk, game_state
        )

        # ⑤ AI 사고 과정 요약
        ai_thinking = self._summarize_ai_thinking(
            strategy, usecase, winloss, risk
        )

        return {
            "summary": summary,
            "turn_analysis": turn_analysis,
            "critical_turns": critical_turns,
            "dashboard": dashboard_data,
            "ai_thinking": ai_thinking,
            "timestamp": time.time(),
            "move_number": move_number,
        }

    def generate_final_report(self, game_data: dict) -> dict:
        """최종 경기 보고서 생성"""
        analysis_history = game_data.get("analysis_history", [])

        return {
            "game_id": game_data.get("game_id"),
            "result": game_data.get("result"),
            "total_moves": game_data.get("total_moves", 0),
            "duration": game_data.get("duration", 0),
            "phases": self._analyze_phases(analysis_history),
            "key_moments": self._identify_key_moments(analysis_history),
            "performance_metrics": self._calculate_metrics(analysis_history),
            "generated_at": time.time(),
        }

    def _generate_summary(self, strategy: dict, usecase: dict,
                           winloss: dict, risk: dict,
                           game_state: dict) -> dict:
        """경기 요약"""
        win_prob = winloss.get("win_probability", 50)
        risk_grade = risk.get("risk_grade", "UNKNOWN")
        phase = usecase.get("current_phase", "unknown")
        applied_strategy = usecase.get("applied_strategy", {})

        # 전체 상태 판단
        if win_prob > 70:
            status = "우세"
            outlook = "유리한 국면이 이어지고 있습니다."
        elif win_prob > 55:
            status = "소폭 우세"
            outlook = "주의를 기울이며 우위를 유지해야 합니다."
        elif win_prob > 45:
            status = "균형"
            outlook = "양측이 팽팽한 국면입니다."
        elif win_prob > 30:
            status = "열세"
            outlook = "역전 기회를 모색해야 합니다."
        else:
            status = "심각한 열세"
            outlook = "최선의 방어를 통해 기회를 찾아야 합니다."

        return {
            "status": status,
            "outlook": outlook,
            "win_probability": win_prob,
            "risk_grade": risk_grade,
            "phase": phase,
            "strategy_name": applied_strategy.get("name", ""),
            "strategy_description": applied_strategy.get("description", ""),
        }

    def _generate_turn_analysis(self, strategy: dict, usecase: dict,
                                  winloss: dict, risk: dict,
                                  move_number: int) -> dict:
        """턴별 분석"""
        evaluation = strategy.get("evaluation", {})
        recommended = risk.get("final_recommended_move", {})

        return {
            "move_number": move_number,
            "evaluation": evaluation,
            "recommended_move": recommended,
            "risk_score": risk.get("risk_score", 0),
            "win_probability": winloss.get("win_probability", 50),
            "warnings": risk.get("safety_warnings", []) + [
                w.get("message", "") for w in winloss.get("warnings", [])
            ],
            "strategy_reasoning": strategy.get("strategy_reasoning", ""),
        }

    def _generate_dashboard_data(self, strategy: dict, winloss: dict,
                                   risk: dict, game_state: dict) -> dict:
        """대시보드 시각화 데이터"""
        evaluation = strategy.get("evaluation", {})

        return {
            "win_probability_gauge": winloss.get("win_probability", 50),
            "evaluation_breakdown": {
                "material": evaluation.get("weighted", {}).get("material", 0),
                "position": evaluation.get("weighted", {}).get("position", 0),
                "mobility": evaluation.get("weighted", {}).get("mobility", 0),
                "king_safety": evaluation.get("weighted", {}).get("king_safety", 0),
            },
            "risk_indicator": {
                "score": risk.get("risk_score", 0),
                "grade": risk.get("risk_grade", "UNKNOWN"),
            },
            "win_trend": winloss.get("win_trend", {}),
            "momentum": winloss.get("momentum", {}),
            "board_summary": strategy.get("board_summary", {}),
        }

    def _summarize_ai_thinking(self, strategy: dict, usecase: dict,
                                 winloss: dict, risk: dict) -> list[dict]:
        """에이전트별 판단 근거 요약"""
        thinking = []

        # Agent 1: 전략 분석가
        thinking.append({
            "agent": "전략 분석가",
            "summary": strategy.get("strategy_reasoning", "분석 중..."),
            "confidence": min(0.95, 0.5 + abs(strategy.get("evaluation", {}).get("total", 0)) * 0.05),
        })

        # Agent 2: 사례 설계자
        applied = usecase.get("applied_strategy", {})
        thinking.append({
            "agent": "사례 설계자",
            "summary": f"{applied.get('name', '')} - {applied.get('reason', '')}",
            "confidence": 0.8,
        })

        # Agent 3: 승패 분석가
        thinking.append({
            "agent": "승패 분석가",
            "summary": winloss.get("recommendation", "분석 중..."),
            "confidence": winloss.get("win_probability", 50) / 100,
        })

        # Agent 4: 리스크 평가자
        grade = risk.get("risk_grade", "UNKNOWN")
        traps = risk.get("traps_detected", [])
        trap_msg = f" 함정 {len(traps)}건 탐지." if traps else ""
        thinking.append({
            "agent": "리스크 평가자",
            "summary": f"리스크 등급: {grade}.{trap_msg}",
            "confidence": 0.85,
        })

        return thinking

    def _analyze_phases(self, analysis_history: list) -> dict:
        """페이즈별 분석"""
        phases = {"opening": [], "midgame": [], "endgame": []}
        for entry in analysis_history:
            phase = entry.get("phase", "midgame")
            if phase in phases:
                phases[phase].append(entry.get("score", 0))

        result = {}
        for phase, scores in phases.items():
            if scores:
                result[phase] = {
                    "moves": len(scores),
                    "avg_score": round(sum(scores) / len(scores), 2),
                    "best_score": round(max(scores), 2),
                    "worst_score": round(min(scores), 2),
                }
            else:
                result[phase] = {"moves": 0}

        return result

    def _identify_key_moments(self, analysis_history: list) -> list[dict]:
        """핵심 순간 식별"""
        key_moments = []
        for i, entry in enumerate(analysis_history):
            if i > 0:
                prev_score = analysis_history[i - 1].get("score", 0)
                curr_score = entry.get("score", 0)
                delta = curr_score - prev_score

                if abs(delta) >= 3.0:
                    key_moments.append({
                        "move_number": entry.get("move_number", i),
                        "type": "turning_point",
                        "delta": round(delta, 2),
                        "description": (
                            f"{'호전' if delta > 0 else '악화'}: "
                            f"평가 점수 {round(prev_score, 1)} → {round(curr_score, 1)}"
                        ),
                    })

        return key_moments[-10:]

    def _calculate_metrics(self, analysis_history: list) -> dict:
        """성능 지표 계산"""
        if not analysis_history:
            return {}

        scores = [e.get("score", 0) for e in analysis_history]
        times = [e.get("time", 0) for e in analysis_history]
        depths = [e.get("depth", 0) for e in analysis_history]

        return {
            "avg_score": round(sum(scores) / len(scores), 2),
            "avg_think_time": round(sum(times) / len(times), 3),
            "avg_depth": round(sum(depths) / len(depths), 1),
            "total_nodes": sum(e.get("nodes", 0) for e in analysis_history),
            "consistency": round(
                1.0 - (max(scores) - min(scores)) / max(abs(max(scores)), abs(min(scores)), 1),
                2
            ),
        }
