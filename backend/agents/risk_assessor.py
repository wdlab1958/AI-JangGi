"""Agent 4: 전술 리스크 평가자 (Tactical Risk Assessor) - 개선판

핵심 원칙: 탐색 엔진의 최적수를 존중. 리스크 평가는 보조 정보로만 제공.
탐색 엔진이 depth N으로 계산한 수를 1-ply 분석으로 덮어쓰지 않음.
"""
from .base_agent import BaseAgent
from ..engine.board import Board
from ..engine.pieces import Piece, PieceType, Team


class RiskAssessor(BaseAgent):
    def __init__(self):
        super().__init__(
            agent_id="agent_4_risk",
            name="리스크 평가자",
            role="수별 리스크 평가, 함정 탐지, 안전수 확정",
        )

    def execute(self, input_data: dict) -> dict:
        board: Board = input_data["board"]
        team: Team = input_data["team"]
        strategy_result = input_data.get("strategy_result", {})
        winloss_result = input_data.get("winloss_result", {})

        candidates = strategy_result.get("candidates", [])
        recommended = strategy_result.get("recommended_move")

        # 각 후보수의 리스크 평가 (정보 제공 목적)
        risk_assessments = []
        for cand in candidates[:5]:
            risk = self._assess_move_risk(board, team, cand)
            risk_assessments.append(risk)

        # 함정 탐지
        traps = self._detect_traps(board, team)

        # 완화 전략 수립
        mitigation = self._generate_mitigation(risk_assessments, traps, winloss_result)

        # 최종 수 결정: 탐색 엔진의 추천수를 항상 존중
        # 리스크 평가기는 덮어쓰지 않음 (탐색이 이미 반론을 고려)
        final_move = self._select_final_move(recommended, candidates, risk_assessments)

        # 추천수의 리스크 등급 산출
        rec_risk = self._find_risk_for_move(recommended, risk_assessments)
        risk_grade = rec_risk["grade"] if rec_risk else "UNKNOWN"

        overall_risk = self._calculate_overall_risk(risk_assessments, traps, winloss_result)

        return {
            "risk_score": overall_risk,
            "risk_grade": risk_grade,
            "risk_assessments": risk_assessments,
            "traps_detected": traps,
            "mitigation_strategy": mitigation,
            "final_recommended_move": final_move,
            "safety_warnings": self._generate_safety_warnings(
                overall_risk, traps, winloss_result
            ),
        }

    def _select_final_move(self, recommended, candidates, risk_assessments):
        """
        최종 수 선택: 탐색 엔진의 추천수를 기본으로 사용.
        유일한 예외: 추천수가 즉시 기물 손실을 유발하고 (리스크 CRITICAL),
        동시에 탐색 점수가 비슷한 안전한 대안이 있을 때만 교체.
        """
        if recommended is None:
            return None

        if not risk_assessments or not candidates:
            return recommended

        # 추천수의 리스크 확인
        rec_risk = self._find_risk_for_move(recommended, risk_assessments)

        # 추천수의 리스크가 CRITICAL이 아니면 그대로 사용
        if rec_risk is None or rec_risk["risk_score"] < 80:
            return recommended

        # CRITICAL 리스크: 탐색 점수 차이가 작은 안전한 대안이 있는지 확인
        rec_score = self._find_search_score(recommended, candidates)

        for ra in risk_assessments:
            if ra["risk_score"] >= 80:
                continue  # 이것도 위험

            alt_score = self._find_search_score(ra["move"], candidates)
            # 대안의 탐색 점수가 추천수와 큰 차이가 없을 때만 (3점 이내)
            if alt_score is not None and rec_score is not None:
                if rec_score - alt_score <= 3.0:
                    return ra["move"]

        # 안전한 대안이 없으면 탐색 엔진의 판단을 존중
        return recommended

    def _find_risk_for_move(self, move, risk_assessments):
        if move is None:
            return None
        return next(
            (r for r in risk_assessments
             if r["move"].get("from") == move.get("from")
             and r["move"].get("to") == move.get("to")),
            None,
        )

    def _find_search_score(self, move, candidates):
        if move is None:
            return None
        for c in candidates:
            if c.get("from") == move.get("from") and c.get("to") == move.get("to"):
                return c.get("score", 0)
        return None

    def _assess_move_risk(self, board: Board, team: Team, candidate: dict) -> dict:
        risk_score = 0
        risk_factors = []

        from_pos = candidate.get("from", (0, 0))
        to_pos = candidate.get("to", (0, 0))
        piece_data = candidate.get("piece", {})
        piece_value = piece_data.get("value", 0)

        # 이동 후 기물이 위험에 처하는지 (board copy 사용)
        board_copy = board.copy()
        fr, fc = from_pos
        tr, tc = to_pos
        piece = board_copy.get_piece(fr, fc)

        if piece:
            board_copy.move_piece(fr, fc, tr, tc)
            enemy = Team.HAN if team == Team.CHO else Team.CHO

            # 이동한 기물이 공격받을 수 있는지 (빠른 체크)
            for ep in board_copy.get_team_pieces(enemy):
                for mr, mc in board_copy._get_raw_moves(ep):
                    if mr == tr and mc == tc:
                        tgt = board_copy.grid[mr][mc]
                        if tgt is None or tgt.team != ep.team:
                            risk_score += piece_value * 3
                            risk_factors.append(
                                f"{piece_data.get('hanja','?')}이(가) {ep.hanja}에 위험")
                            break
                if risk_score > 0:
                    break

            # 왕 장군 위험
            if board_copy.is_in_check(team):
                risk_score += 50
                risk_factors.append("이동 후 자왕 장군 위험")

            board_copy.undo_move()

        # 불리한 교환
        target = board.get_piece(to_pos[0], to_pos[1])
        if target and target.team != team:
            exchange = target.value - piece_value
            if exchange < -3:
                risk_score += abs(exchange) * 5
                risk_factors.append(f"불리한 교환 (차이: {exchange})")

        risk_score = min(100, max(0, risk_score))

        return {
            "move": candidate,
            "risk_score": risk_score,
            "risk_factors": risk_factors,
            "grade": self._score_to_grade(risk_score),
        }

    def _detect_traps(self, board: Board, team: Team) -> list[dict]:
        traps = []
        enemy = Team.HAN if team == Team.CHO else Team.CHO
        my_king = board.get_king(team)
        if my_king is None:
            return traps

        enemy_pieces = board.get_team_pieces(enemy)

        # 포+마 합공 패턴
        cannons = [p for p in enemy_pieces if p.piece_type == PieceType.CANNON]
        horses = [p for p in enemy_pieces if p.piece_type == PieceType.HORSE]
        kr, kc = my_king.row, my_king.col

        for cannon in cannons:
            for horse in horses:
                c_dist = abs(cannon.row - kr) + abs(cannon.col - kc)
                h_dist = abs(horse.row - kr) + abs(horse.col - kc)
                if c_dist <= 4 and h_dist <= 4:
                    traps.append({
                        "type": "cannon_horse_combo",
                        "description": "포+마 합공 위협 감지",
                        "severity": "HIGH",
                        "attacking_pieces": [cannon.to_dict(), horse.to_dict()],
                    })

        # 차의 열린 줄 위협
        cars = [p for p in enemy_pieces if p.piece_type == PieceType.CAR]
        for car in cars:
            if car.col == kc:
                lo, hi = min(car.row, kr), max(car.row, kr)
                cnt = sum(1 for r in range(lo+1, hi) if board.grid[r][kc] is not None)
                if cnt <= 1:
                    traps.append({
                        "type": "car_line_threat",
                        "description": f"차의 열린 줄 위협 (열 {car.col})",
                        "severity": "MEDIUM" if cnt == 1 else "HIGH",
                        "attacking_pieces": [car.to_dict()],
                    })

        return traps

    def _generate_mitigation(self, risk_assessments, traps, winloss_result):
        strategies = []

        high_risk = [r for r in risk_assessments if r["risk_score"] > 60]
        if high_risk:
            strategies.append({
                "action": "caution",
                "description": "일부 수에 높은 리스크 감지. 탐색 엔진 추천수가 최적.",
            })

        for trap in traps:
            if trap["severity"] == "HIGH":
                strategies.append({
                    "action": "counter_trap",
                    "description": f"함정 대응: {trap['description']}",
                })

        win_prob = winloss_result.get("win_probability", 50)
        if win_prob < 40:
            strategies.append({
                "action": "defensive_mode",
                "description": "승률 열세. 방어적 전략 권장.",
            })

        if not strategies:
            strategies.append({
                "action": "proceed",
                "description": "특별한 위험 없음. 공격 진행.",
            })

        return {"strategies": strategies, "trap_count": len(traps)}

    def _calculate_overall_risk(self, risk_assessments, traps, winloss_result):
        if not risk_assessments:
            return 50
        avg = sum(r["risk_score"] for r in risk_assessments) / len(risk_assessments)
        trap_pen = sum(20 if t["severity"] == "HIGH" else 10 for t in traps)
        win_prob = winloss_result.get("win_probability", 50)
        if win_prob < 30:
            avg += 15
        return min(100, max(0, int(avg + trap_pen)))

    def _score_to_grade(self, score):
        if score <= 30: return "LOW"
        if score <= 60: return "MEDIUM"
        if score <= 80: return "HIGH"
        return "CRITICAL"

    def _generate_safety_warnings(self, overall_risk, traps, winloss_result):
        warnings = []
        if overall_risk > 80:
            warnings.append("전체 리스크 CRITICAL. 방어 강화 중.")
        elif overall_risk > 60:
            warnings.append("전체 리스크 HIGH. 전략 주의.")
        for trap in traps:
            if trap["severity"] in ("HIGH", "CRITICAL"):
                warnings.append(f"함정 경고: {trap['description']}")
        return warnings
