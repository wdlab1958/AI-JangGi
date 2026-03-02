"""Layer 3: Long-term Memory (장기 메모리)

경기 간 영구 저장되는 전략 데이터를 관리한다.
- 누적 경기 통계 (Elo Rating, 승/패/무)
- 전략 패턴 데이터
- 상대 플레이어별 프로파일
- 종반전 패턴 라이브러리
- 경기 복기 및 분석 보고서 아카이브
"""
import json
import logging
import os
import time
from typing import Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class LongTermMemory:
    """Layer 3: 영구 저장되는 장기 전략 데이터"""

    def __init__(self, storage_dir: str = "./data/long_term"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.stats_file = self.storage_dir / "stats.json"
        self.players_dir = self.storage_dir / "players"
        self.players_dir.mkdir(exist_ok=True)
        self.patterns_dir = self.storage_dir / "patterns"
        self.patterns_dir.mkdir(exist_ok=True)
        self.games_dir = self.storage_dir / "games"
        self.games_dir.mkdir(exist_ok=True)

        self.stats = self._load_stats()

    def _load_stats(self) -> dict:
        """통계 로드 (corrupt JSON 시 기본값 반환)"""
        if self.stats_file.exists():
            try:
                with open(self.stats_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Corrupt stats file %s: %s. Using defaults.", self.stats_file, e)
        return {
            "total_games": 0,
            "wins": 0,
            "losses": 0,
            "draws": 0,
            "elo_rating": 1500,
            "best_streak": 0,
            "current_streak": 0,
        }

    def _save_stats(self):
        """통계 저장"""
        with open(self.stats_file, "w") as f:
            json.dump(self.stats, f, indent=2, ensure_ascii=False)

    def record_game_result(self, game_id: str, result: str,
                            opponent_id: str = "anonymous",
                            game_data: dict = None):
        """경기 결과 기록"""
        self.stats["total_games"] += 1

        if result == "win":
            self.stats["wins"] += 1
            self.stats["current_streak"] += 1
            self.stats["best_streak"] = max(
                self.stats["best_streak"], self.stats["current_streak"]
            )
            elo_change = 16
        elif result == "loss":
            self.stats["losses"] += 1
            self.stats["current_streak"] = 0
            elo_change = -16
        else:
            self.stats["draws"] += 1
            elo_change = 0

        self.stats["elo_rating"] += elo_change
        self._save_stats()

        # 경기 데이터 저장
        if game_data:
            game_file = self.games_dir / f"{game_id}.json"
            with open(game_file, "w") as f:
                json.dump({
                    "game_id": game_id,
                    "result": result,
                    "opponent_id": opponent_id,
                    "timestamp": time.time(),
                    "data": game_data,
                }, f, indent=2, ensure_ascii=False)

    def update_player_profile(self, player_id: str, profile: dict):
        """플레이어 프로파일 갱신"""
        player_file = self.players_dir / f"{player_id}.json"
        existing = {}
        if player_file.exists():
            with open(player_file, "r") as f:
                existing = json.load(f)

        existing.update(profile)
        existing["last_updated"] = time.time()

        with open(player_file, "w") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    def get_player_profile(self, player_id: str) -> Optional[dict]:
        """플레이어 프로파일 조회"""
        player_file = self.players_dir / f"{player_id}.json"
        if player_file.exists():
            try:
                with open(player_file, "r") as f:
                    return json.load(f)
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Corrupt player file %s: %s", player_file, e)
        return None

    def save_strategy_pattern(self, pattern_name: str, pattern_data: dict):
        """전략 패턴 저장"""
        pattern_file = self.patterns_dir / f"{pattern_name}.json"
        with open(pattern_file, "w") as f:
            json.dump(pattern_data, f, indent=2, ensure_ascii=False)

    def get_strategy_patterns(self) -> list[dict]:
        """모든 전략 패턴 목록 반환"""
        patterns = []
        for f in self.patterns_dir.glob("*.json"):
            try:
                with open(f, "r") as fp:
                    patterns.append(json.load(fp))
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Corrupt pattern file %s: %s", f, e)
        return patterns

    def get_stats(self) -> dict:
        """통계 반환"""
        win_rate = (
            self.stats["wins"] / self.stats["total_games"]
            if self.stats["total_games"] > 0 else 0.0
        )
        return {
            **self.stats,
            "win_rate": round(win_rate, 3),
        }

    def get_recent_games(self, limit: int = 10) -> list[dict]:
        """최근 경기 목록"""
        game_files = sorted(
            self.games_dir.glob("*.json"),
            key=lambda f: f.stat().st_mtime,
            reverse=True,
        )
        games = []
        for f in game_files[:limit]:
            try:
                with open(f, "r") as fp:
                    games.append(json.load(fp))
            except (json.JSONDecodeError, ValueError) as e:
                logger.warning("Corrupt game file %s: %s", f, e)
        return games

    def get_context(self) -> dict:
        """장기 메모리 컨텍스트 반환"""
        return {
            "stats": self.get_stats(),
            "strategy_patterns_count": len(list(self.patterns_dir.glob("*.json"))),
            "player_profiles_count": len(list(self.players_dir.glob("*.json"))),
            "recent_games_count": len(list(self.games_dir.glob("*.json"))),
        }
