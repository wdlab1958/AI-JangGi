"""Agent 2: 게임 사례 설계자 (Use Case Designer)

역할: 경기 시나리오 설계, 게임 전략 패턴 정의, 대국 시나리오 최적화
입력: 전략 분석가의 판면 평가 결과, 상대 플레이어 프로파일, 과거 경기 데이터
처리: ① 경기 페이즈 분류 → ② 페이즈별 전략 템플릿 선택 → ③ 상대 스타일 분석 → ④ 맞춤형 시나리오
출력: {현재_페이즈, 적용_전략, 대응_시나리오, 예측_수순, 승리_경로}
"""
from .base_agent import BaseAgent


# 전략 템플릿
STRATEGY_TEMPLATES = {
    "opening": {
        "aggressive": {
            "name": "공격적 포진",
            "description": "차와 포의 빠른 전개로 상대 진영 압박",
            "priority_pieces": ["car", "cannon"],
            "key_principles": ["중앙 제어", "열린 줄 확보", "포 활성화"],
        },
        "defensive": {
            "name": "안정적 포진",
            "description": "사/상 배치 안정화 후 점진적 전개",
            "priority_pieces": ["guard", "elephant"],
            "key_principles": ["왕 보호 강화", "안정적 기물 전개", "상대 공격 대비"],
        },
        "balanced": {
            "name": "균형적 포진",
            "description": "양쪽 날개 균등 전개",
            "priority_pieces": ["horse", "car"],
            "key_principles": ["균등 전개", "유연한 대응", "기회 탐색"],
        },
    },
    "midgame": {
        "aggressive": {
            "name": "각축 공격",
            "description": "상대 약점 집중 공략 및 기물 교환 유도",
            "priority_pieces": ["car", "cannon", "horse"],
            "key_principles": ["약점 공략", "기물 교환 우위", "차 활용 극대화"],
        },
        "defensive": {
            "name": "견고한 방어",
            "description": "포위 방지 및 역공 기회 탐색",
            "priority_pieces": ["guard", "elephant", "pawn"],
            "key_principles": ["방어선 유지", "역공 준비", "기물 보존"],
        },
        "balanced": {
            "name": "유연한 대응",
            "description": "상대 수에 따른 적응적 대응",
            "priority_pieces": ["car", "horse"],
            "key_principles": ["상황 적응", "기회 활용", "리스크 관리"],
        },
    },
    "endgame": {
        "aggressive": {
            "name": "외통장 공격",
            "description": "왕 포위 및 체크메이트 시도",
            "priority_pieces": ["car", "cannon"],
            "key_principles": ["왕 포위", "장군 연속", "도주로 차단"],
        },
        "defensive": {
            "name": "울타리 방어",
            "description": "왕 주위 방어벽 구축 및 비김 유도",
            "priority_pieces": ["guard", "pawn"],
            "key_principles": ["왕 보호", "시간 끌기", "비김 유도"],
        },
        "balanced": {
            "name": "마무리 전략",
            "description": "기물 우위 활용한 점진적 마무리",
            "priority_pieces": ["car", "horse"],
            "key_principles": ["우위 확대", "안전한 마무리", "실수 방지"],
        },
    },
}


class UseCaseDesigner(BaseAgent):
    """게임 사례 설계자 에이전트"""

    def __init__(self):
        super().__init__(
            agent_id="agent_2_usecase",
            name="사례 설계자",
            role="경기 시나리오 설계, 게임 전략 패턴 정의",
        )

    def execute(self, input_data: dict) -> dict:
        """
        input_data:
            - strategy_result: Agent 1 결과
            - phase: str (opening/midgame/endgame)
            - memory_context: dict
        """
        strategy_result = input_data["strategy_result"]
        phase = input_data["phase"]
        memory_ctx = input_data.get("memory_context", {})

        # ① 경기 페이즈 확인
        current_phase = phase

        # ② 상대 스타일 분석
        opponent_style = self._analyze_opponent_style(memory_ctx)

        # ③ 페이즈별 전략 템플릿 선택
        strategy = self._select_strategy(
            current_phase, opponent_style, strategy_result
        )

        # ④ 맞춤형 시나리오 생성
        scenario = self._generate_scenario(
            current_phase, strategy, strategy_result, memory_ctx
        )

        # 승리 경로 예측
        win_path = self._predict_win_path(
            current_phase, strategy, strategy_result
        )

        return {
            "current_phase": current_phase,
            "opponent_style": opponent_style,
            "applied_strategy": strategy,
            "scenario": scenario,
            "win_path": win_path,
            "recommended_adjustments": self._get_adjustments(
                strategy_result, opponent_style
            ),
        }

    def _analyze_opponent_style(self, memory_ctx: dict) -> str:
        """상대 플레이 스타일 분석"""
        st_ctx = memory_ctx.get("short_term", {})
        opponent_profile = st_ctx.get("opponent_profile", {})

        style = opponent_profile.get("play_style", "balanced")
        return style

    def _select_strategy(self, phase: str, opponent_style: str,
                          strategy_result: dict) -> dict:
        """전략 템플릿 선택"""
        evaluation = strategy_result.get("evaluation", {})
        score = evaluation.get("total", 0)

        # 점수에 따른 전략 조정
        if score > 5:
            # 우세 → 공격적
            my_style = "aggressive"
        elif score < -5:
            # 열세 → 역공 또는 방어
            my_style = "aggressive" if opponent_style == "defensive" else "defensive"
        else:
            # 균형 → 상대 스타일에 대응
            counter = {
                "aggressive": "defensive",
                "defensive": "aggressive",
                "balanced": "balanced",
            }
            my_style = counter.get(opponent_style, "balanced")

        template = STRATEGY_TEMPLATES.get(phase, {}).get(my_style, {})
        return {
            **template,
            "style": my_style,
            "reason": f"판면 점수 {score:.1f}, 상대 {opponent_style} 성향에 대응",
        }

    def _generate_scenario(self, phase: str, strategy: dict,
                            strategy_result: dict, memory_ctx: dict) -> dict:
        """시나리오 생성"""
        candidates = strategy_result.get("candidates", [])
        best_move = strategy_result.get("recommended_move", {})

        scenario = {
            "primary_plan": strategy.get("description", ""),
            "key_principles": strategy.get("key_principles", []),
            "priority_pieces": strategy.get("priority_pieces", []),
            "move_suggestion": best_move,
            "alternative_moves": candidates[1:3] if len(candidates) > 1 else [],
        }

        # 위험 시나리오
        if strategy_result.get("evaluation", {}).get("king_safety", 0) < -5:
            scenario["warning"] = "왕 안전도 위험. 방어 우선 수행."

        return scenario

    def _predict_win_path(self, phase: str, strategy: dict,
                           strategy_result: dict) -> dict:
        """승리 경로 예측"""
        score = strategy_result.get("evaluation", {}).get("total", 0)

        if phase == "opening":
            return {
                "approach": "안정적 포진 완성 후 중반 공격 전환",
                "estimated_turns": "15-20수 내 중반 진입",
                "confidence": min(0.7, 0.5 + score * 0.02),
            }
        elif phase == "midgame":
            return {
                "approach": strategy.get("description", "유연한 대응"),
                "estimated_turns": "10-15수 내 기물 우위 확보",
                "confidence": min(0.8, 0.5 + score * 0.03),
            }
        else:
            return {
                "approach": "체크메이트 또는 기물 우위 마무리",
                "estimated_turns": "5-10수 내 마무리 시도",
                "confidence": min(0.9, 0.5 + score * 0.04),
            }

    def _get_adjustments(self, strategy_result: dict, opponent_style: str) -> list:
        """전략 조정 권고사항"""
        adjustments = []
        eval_detail = strategy_result.get("evaluation", {})

        if eval_detail.get("king_safety", 0) < -3:
            adjustments.append("왕 보호 강화 - 사/상 이동으로 방어벽 구축")

        if eval_detail.get("mobility", 0) < -3:
            adjustments.append("기동성 개선 - 막힌 기물 활성화 우선")

        if opponent_style == "aggressive":
            adjustments.append("상대 공격 대비 - 핵심 기물 보호 및 역공 준비")

        if not adjustments:
            adjustments.append("현재 전략 유지 - 안정적 진행")

        return adjustments
