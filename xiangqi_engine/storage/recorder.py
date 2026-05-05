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

    def list_games(
        self,
        date: Optional[str] = None,
        start_date: Optional[str] = None,
        date_prefix: Optional[str] = None,
        limit: int = 10
    ) -> List[dict]:
        """列出对局记录

        Args:
            date: 指定日期（YYYY-MM-DD）
            start_date: 开始日期，查询该日期之后的对局
            date_prefix: 日期前缀（YYYY-MM），查询该月份的对局
            limit: 最大返回数量

        Returns:
            对局列表，每项包含 file, path, date, player_color, level, result, total_moves
        """
        games = []

        # 根据参数确定搜索目录
        if date:
            # 指定日期
            search_dir = self.base_dir / date
        elif date_prefix:
            # 指定月份
            search_dir = self.base_dir
        else:
            # 全局搜索或日期范围
            search_dir = self.base_dir

        if not search_dir.exists():
            return []

        for filepath in sorted(search_dir.glob("**/*.xqi"), key=os.path.getmtime, reverse=True):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                game_date = data["meta"]["date"]

                # 过滤条件
                if date_prefix:
                    # 月份过滤
                    if not game_date.startswith(date_prefix):
                        continue

                if start_date:
                    # 日期范围过滤
                    if game_date.split("T")[0] < start_date:
                        continue

                games.append({
                    "file": filepath.name,
                    "path": str(filepath),
                    "date": game_date,
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

    def delete_game(self, filepath: str) -> bool:
        """删除单个对局

        Args:
            filepath: 对局文件路径

        Returns:
            是否删除成功
        """
        try:
            Path(filepath).unlink()
            return True
        except Exception:
            return False

    def delete_games_by_range(
        self,
        date: Optional[str] = None,
        start_date: Optional[str] = None,
        date_prefix: Optional[str] = None,
    ) -> int:
        """按时间范围删除对局

        Args:
            date: 指定日期
            start_date: 开始日期
            date_prefix: 日期前缀（月份）

        Returns:
            删除数量
        """
        deleted = 0

        # 获取要删除的对局列表
        games = self.list_games(
            date=date,
            start_date=start_date,
            date_prefix=date_prefix,
            limit=1000  # 大批量删除
        )

        for game in games:
            if self.delete_game(game["path"]):
                deleted += 1

        return deleted

    def delete_all_games(self) -> int:
        """删除所有对局

        Returns:
            删除数量
        """
        deleted = 0
        for filepath in self.base_dir.glob("**/*.xqi"):
            try:
                filepath.unlink()
                deleted += 1
            except Exception:
                continue
        return deleted