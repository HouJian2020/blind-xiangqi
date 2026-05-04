"""招法数据结构"""

from dataclasses import dataclass


@dataclass
class MoveRecord:
    """招法记录（用于对局存储）"""

    num: int
    player: str
    chinese: str
    uci: str

    def to_dict(self) -> dict:
        return {
            "num": self.num,
            "player": self.player,
            "chinese": self.chinese,
            "uci": self.uci,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "MoveRecord":
        return cls(
            num=data["num"],
            player=data["player"],
            chinese=data["chinese"],
            uci=data["uci"],
        )