"""对局记录器"""

import json
import os
from pathlib import Path
from typing import Optional, List

from ..game.game import Game, get_game_save_dir, generate_game_filename


class GameRecorder:
    """对局记录器"""

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = base_dir or get_game_save_dir()

    def save_game(self, game: Game) -> Path:
        """保存对局"""
        date_str = game.meta.date.split("T")[0]
        date_dir = self.base_dir / date_str
        date_dir.mkdir(parents=True, exist_ok=True)

        filename = generate_game_filename(game)
        filepath = date_dir / filename
        game.save(str(filepath))
        return filepath

    def load_game(self, filepath: str) -> Game:
        """加载对局"""
        return Game.load(filepath)

    def list_games(self, date: Optional[str] = None, limit: int = 10) -> List[dict]:
        """列出对局记录"""
        games = []
        search_dir = self.base_dir / date if date else self.base_dir

        if not search_dir.exists():
            return []

        for filepath in sorted(search_dir.glob("**/*.xqi"), key=os.path.getmtime, reverse=True):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                games.append({
                    "file": filepath.name,
                    "path": str(filepath),
                    "date": data["meta"]["date"],
                    "player_color": data["meta"]["player_color"],
                    "level": data["meta"]["level"],
                    "result": data["meta"]["result"],
                    "total_moves": data["meta"]["total_moves"],
                })
            except Exception:
                continue
            if len(games) >= limit:
                break
        return games