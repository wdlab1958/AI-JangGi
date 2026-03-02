"""장기 기물 정의 모듈"""
from enum import Enum
from dataclasses import dataclass
from typing import Optional


class Team(Enum):
    CHO = "cho"   # 초 (Red/Green)
    HAN = "han"   # 한 (Blue)


class PieceType(Enum):
    KING = "king"       # 왕(王) - 漢/楚
    CAR = "car"         # 차(車)
    CANNON = "cannon"   # 포(砲)
    HORSE = "horse"     # 마(馬)
    ELEPHANT = "elephant"  # 상(象)
    GUARD = "guard"     # 사(士)
    PAWN = "pawn"       # 졸(卒)/兵


# 기물 가치 (평가 함수용)
PIECE_VALUES = {
    PieceType.KING: 0,       # 왕은 무한 가치 (별도 처리)
    PieceType.CAR: 13,
    PieceType.CANNON: 7,
    PieceType.HORSE: 5,
    PieceType.ELEPHANT: 3,
    PieceType.GUARD: 3,
    PieceType.PAWN: 2,
}

# 한자 표기
PIECE_HANJA = {
    (PieceType.KING, Team.CHO): "楚",
    (PieceType.KING, Team.HAN): "漢",
    (PieceType.CAR, Team.CHO): "車",
    (PieceType.CAR, Team.HAN): "車",
    (PieceType.CANNON, Team.CHO): "包",
    (PieceType.CANNON, Team.HAN): "包",
    (PieceType.HORSE, Team.CHO): "馬",
    (PieceType.HORSE, Team.HAN): "馬",
    (PieceType.ELEPHANT, Team.CHO): "象",
    (PieceType.ELEPHANT, Team.HAN): "象",
    (PieceType.GUARD, Team.CHO): "士",
    (PieceType.GUARD, Team.HAN): "士",
    (PieceType.PAWN, Team.CHO): "卒",
    (PieceType.PAWN, Team.HAN): "兵",
}


class Piece:
    """장기 기물 (고성능: 캐시된 속성)"""
    __slots__ = ("piece_type", "team", "row", "col", "captured",
                 "_value", "_hanja", "_team_sign")

    def __init__(self, piece_type: PieceType, team: Team,
                 row: int, col: int, captured: bool = False):
        self.piece_type = piece_type
        self.team = team
        self.row = row
        self.col = col
        self.captured = captured
        # 캐시: 반복적 dict/enum 조회 제거
        self._value = PIECE_VALUES[piece_type]
        self._hanja = PIECE_HANJA[(piece_type, team)]
        self._team_sign = 1 if team == Team.CHO else -1

    @property
    def value(self) -> int:
        return self._value

    @property
    def hanja(self) -> str:
        return self._hanja

    def to_dict(self) -> dict:
        return {
            "type": self.piece_type.value,
            "team": self.team.value,
            "row": self.row,
            "col": self.col,
            "captured": self.captured,
            "hanja": self._hanja,
            "value": self._value,
        }

    def copy(self) -> "Piece":
        return Piece(
            piece_type=self.piece_type,
            team=self.team,
            row=self.row,
            col=self.col,
            captured=self.captured,
        )
