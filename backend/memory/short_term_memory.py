"""Layer 2: Short-term Memory (단기 메모리)

현재 경기 세션 동안의 패턴을 기록한다.
- 현재 경기 전체 수순 기록
- 상대방 행동 패턴 분석
- 현재 경기 분기점 기록
- 페이즈별 전략 성공/실패 기록
"""
from collections import defaultdict
from typing import Optional


class ShortTermMemory:
    """Layer 2: 현재 경기 세션의 패턴을 관리하는 단기 메모리"""

    def __init__(self):
        self.game_id: Optional[str] = None
        self.move_sequence: list[dict] = []  # 전체 수순
        self.opponent_patterns: dict = {
            "opening_preference": [],  # 초반 선호 패턴
            "midgame_preference": [],  # 중반 선호 패턴
            "endgame_preference": [],  # 종반 선호 패턴
            "attack_frequency": 0,    # 공격 빈도
            "defense_frequency": 0,   # 방어 빈도
            "piece_preferences": defaultdict(int),  # 기물 사용 빈도
        }
        self.critical_points: list[dict] = []  # 분기점 기록
        self.phase_strategies: dict = {
            "opening": {"success": 0, "fail": 0, "strategies": []},
            "midgame": {"success": 0, "fail": 0, "strategies": []},
            "endgame": {"success": 0, "fail": 0, "strategies": []},
        }
        self.evaluation_history: list[float] = []
        self.sync_counter: int = 0  # 동기화 카운터 (5턴마다)

    def init_game(self, game_id: str):
        """새 경기 시작시 초기화"""
        self.game_id = game_id
        self.move_sequence = []
        self.opponent_patterns = {
            "opening_preference": [],
            "midgame_preference": [],
            "endgame_preference": [],
            "attack_frequency": 0,
            "defense_frequency": 0,
            "piece_preferences": defaultdict(int),
        }
        self.critical_points = []
        self.phase_strategies = {
            "opening": {"success": 0, "fail": 0, "strategies": []},
            "midgame": {"success": 0, "fail": 0, "strategies": []},
            "endgame": {"success": 0, "fail": 0, "strategies": []},
        }
        self.evaluation_history = []
        self.sync_counter = 0

    def record_move(self, move: dict, phase: str, evaluation: float,
                     is_opponent: bool = False):
        """수 기록"""
        self.move_sequence.append({
            **move,
            "phase": phase,
            "evaluation": evaluation,
            "is_opponent": is_opponent,
        })
        self.evaluation_history.append(evaluation)
        self.sync_counter += 1

        if is_opponent:
            self._analyze_opponent_move(move, phase)

        # 분기점 감지: 평가 점수 급변 (절대값 2.0 이상 변화)
        if len(self.evaluation_history) >= 2:
            delta = abs(self.evaluation_history[-1] - self.evaluation_history[-2])
            if delta >= 2.0:
                self.critical_points.append({
                    "turn": len(self.move_sequence),
                    "delta": round(delta, 2),
                    "eval_before": round(self.evaluation_history[-2], 2),
                    "eval_after": round(self.evaluation_history[-1], 2),
                    "move": move,
                    "phase": phase,
                })

    def _analyze_opponent_move(self, move: dict, phase: str):
        """상대방 수 패턴 분석"""
        phase_key = f"{phase}_preference"
        if phase_key in self.opponent_patterns:
            self.opponent_patterns[phase_key].append(move)

        # 포획이 있으면 공격, 없으면 방어로 분류
        if move.get("captured"):
            self.opponent_patterns["attack_frequency"] += 1
        else:
            self.opponent_patterns["defense_frequency"] += 1

        # 기물 사용 빈도
        piece_type = move.get("piece", {}).get("type", "unknown")
        self.opponent_patterns["piece_preferences"][piece_type] += 1

    def record_strategy_result(self, phase: str, strategy: str, success: bool):
        """전략 결과 기록"""
        if phase in self.phase_strategies:
            if success:
                self.phase_strategies[phase]["success"] += 1
            else:
                self.phase_strategies[phase]["fail"] += 1
            self.phase_strategies[phase]["strategies"].append({
                "name": strategy,
                "success": success,
            })

    def should_sync(self) -> bool:
        """5턴마다 동기화 필요 여부 확인"""
        return self.sync_counter >= 5

    def reset_sync_counter(self):
        self.sync_counter = 0

    def get_opponent_profile(self) -> dict:
        """상대 프로파일 요약"""
        total = (self.opponent_patterns["attack_frequency"]
                 + self.opponent_patterns["defense_frequency"])
        attack_ratio = (self.opponent_patterns["attack_frequency"] / total
                       if total > 0 else 0.5)

        style = "aggressive" if attack_ratio > 0.6 else (
            "defensive" if attack_ratio < 0.4 else "balanced"
        )

        return {
            "play_style": style,
            "attack_ratio": round(attack_ratio, 2),
            "total_moves": total,
            "piece_preferences": dict(self.opponent_patterns["piece_preferences"]),
            "critical_points_count": len(self.critical_points),
        }

    def get_context(self) -> dict:
        """단기 메모리 컨텍스트 반환"""
        return {
            "game_id": self.game_id,
            "total_moves": len(self.move_sequence),
            "recent_moves": self.move_sequence[-10:],
            "opponent_profile": self.get_opponent_profile(),
            "critical_points": self.critical_points[-5:],
            "phase_strategies": self.phase_strategies,
            "evaluation_trend": self.evaluation_history[-20:],
        }
