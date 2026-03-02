"""Agent 3: 게임 승패 분석가 (Win/Loss Analyst)

역할: 경기 승패 확률 분석, 전세 역전 기회 포착, 승률 계산
입력: 판면 평가 결과, 전략 분석가 추천수, 경기 진행 이력, 상대 플레이어 통계
처리: ① 실시간 승률 계산 → ② 턴별 승률 변화 추적 → ③ 분기점 식별 → ④ 패배 예방 경고
출력: {승률_백분율, 승률_추이, 분기점_분석, 패배_위험_경고, ROI_분석}

Win_Prob = Sigmoid(ΔMaterial * 0.4 + ΔPosition * 0.3 + ΔMobility * 0.2 + ΔKingSafety * 0.1)
"""
import math
from .base_agent import BaseAgent


class WinLossAnalyst(BaseAgent):
    """승패 분석가 에이전트"""

    def __init__(self):
        super().__init__(
            agent_id="agent_3_winloss",
            name="승패 분석가",
            role="경기 승패 확률 분석, 전세 역전 기회 포착",
        )
        self.win_history: list[float] = []

    def execute(self, input_data: dict) -> dict:
        """
        input_data:
            - strategy_result: Agent 1 결과
            - usecase_result: Agent 2 결과
            - memory_context: dict
        """
        strategy_result = input_data["strategy_result"]
        usecase_result = input_data.get("usecase_result", {})
        memory_ctx = input_data.get("memory_context", {})

        evaluation = strategy_result.get("evaluation", {})

        # ① 실시간 승률 계산
        win_prob = self._calculate_win_probability(evaluation)
        self.win_history.append(win_prob)

        # ② 턴별 승률 변화 추적
        win_trend = self._analyze_trend()

        # ③ 분기점 식별
        critical_turns = self._identify_critical_turns(memory_ctx)

        # ④ 패배 예방 경고
        warnings = self._generate_warnings(evaluation, win_prob, strategy_result)

        # ROI 분석
        roi = self._analyze_roi(strategy_result)

        return {
            "win_probability": round(win_prob * 100, 1),
            "win_trend": win_trend,
            "critical_turns": critical_turns,
            "warnings": warnings,
            "roi_analysis": roi,
            "recommendation": self._get_recommendation(win_prob, win_trend),
            "momentum": self._calculate_momentum(),
        }

    def _calculate_win_probability(self, evaluation: dict) -> float:
        """승률 계산: Sigmoid(ΔMaterial*0.4 + ΔPosition*0.3 + ΔMobility*0.2 + ΔKingSafety*0.1)"""
        material = evaluation.get("material", 0)
        position = evaluation.get("position", 0)
        mobility = evaluation.get("mobility", 0)
        king_safety = evaluation.get("king_safety", 0)

        z = (material * 0.4 + position * 0.3 + mobility * 0.2 + king_safety * 0.1)
        return 1.0 / (1.0 + math.exp(-z * 0.15))

    def _analyze_trend(self) -> dict:
        """승률 추이 분석"""
        if len(self.win_history) < 2:
            return {"direction": "stable", "change": 0.0, "history": self.win_history[-20:]}

        recent = self.win_history[-5:]
        if len(recent) >= 2:
            change = recent[-1] - recent[0]
            if change > 0.05:
                direction = "improving"
            elif change < -0.05:
                direction = "declining"
            else:
                direction = "stable"
        else:
            change = 0.0
            direction = "stable"

        return {
            "direction": direction,
            "change": round(change * 100, 1),
            "history": [round(w * 100, 1) for w in self.win_history[-20:]],
        }

    def _identify_critical_turns(self, memory_ctx: dict) -> list[dict]:
        """분기점 식별 (승률 급변 지점)"""
        critical = []
        st_ctx = memory_ctx.get("short_term", {})
        eval_trend = st_ctx.get("evaluation_trend", [])

        for i in range(1, len(eval_trend)):
            delta = abs(eval_trend[i] - eval_trend[i - 1])
            if delta >= 2.0:
                critical.append({
                    "turn": i,
                    "delta": round(delta, 2),
                    "before": round(eval_trend[i - 1], 2),
                    "after": round(eval_trend[i], 2),
                    "type": "swing_positive" if eval_trend[i] > eval_trend[i - 1] else "swing_negative",
                })

        return critical[-5:]  # 최근 5개

    def _generate_warnings(self, evaluation: dict, win_prob: float,
                            strategy_result: dict) -> list[dict]:
        """패배 예방 경고"""
        warnings = []

        if win_prob < 0.3:
            warnings.append({
                "level": "CRITICAL",
                "message": "패배 위험 높음! 긴급 방어 전략 전환 필요.",
                "suggestion": "왕 보호 우선, 기물 교환 회피",
            })
        elif win_prob < 0.45:
            warnings.append({
                "level": "HIGH",
                "message": "열세 국면. 전략 재조정 권장.",
                "suggestion": "역공 기회 탐색 또는 장기전 유도",
            })

        if evaluation.get("king_safety", 0) < -8:
            warnings.append({
                "level": "CRITICAL",
                "message": "왕 안전도 심각! 즉시 방어 필요.",
                "suggestion": "사 또는 차를 이용한 즉시 방어",
            })

        if evaluation.get("material", 0) < -7:
            warnings.append({
                "level": "HIGH",
                "message": "기물 대차 열세. 교환 회피 필요.",
                "suggestion": "기물 보존 및 역공 포인트 탐색",
            })

        return warnings

    def _analyze_roi(self, strategy_result: dict) -> dict:
        """각 후보수의 투자 대비 수익 분석"""
        candidates = strategy_result.get("candidates", [])
        roi_data = []

        for cand in candidates[:5]:
            score = cand.get("score", 0)
            roi_data.append({
                "move": cand,
                "expected_value": round(score, 2),
                "risk_level": "low" if score > 2 else ("medium" if score > -2 else "high"),
            })

        return {"candidates_roi": roi_data}

    def _get_recommendation(self, win_prob: float, trend: dict) -> str:
        """상황별 권고"""
        direction = trend.get("direction", "stable")

        if win_prob > 0.7:
            if direction == "improving":
                return "우세 확대 중. 현재 전략 유지하며 적극 공격."
            return "우세 국면. 안정적 마무리 진행."
        elif win_prob > 0.5:
            if direction == "declining":
                return "우위 감소 중. 전략 점검 및 수비 보강 필요."
            return "소폭 우세. 신중한 진행으로 우위 유지."
        elif win_prob > 0.3:
            if direction == "improving":
                return "열세이나 개선 중. 역전 기회 적극 활용."
            return "열세 국면. 방어 강화 및 역공 타이밍 탐색."
        else:
            return "심각한 열세. 최선의 방어수 선택 및 상대 실수 유도."

    def _calculate_momentum(self) -> dict:
        """모멘텀 계산 (최근 추세 강도)"""
        if len(self.win_history) < 3:
            return {"value": 0, "label": "neutral"}

        recent = self.win_history[-5:]
        changes = [recent[i] - recent[i - 1] for i in range(1, len(recent))]
        avg_change = sum(changes) / len(changes) if changes else 0

        if avg_change > 0.03:
            return {"value": round(avg_change * 100, 1), "label": "positive"}
        elif avg_change < -0.03:
            return {"value": round(avg_change * 100, 1), "label": "negative"}
        return {"value": round(avg_change * 100, 1), "label": "neutral"}

    def reset(self):
        """경기 시작 시 리셋"""
        self.win_history = []
