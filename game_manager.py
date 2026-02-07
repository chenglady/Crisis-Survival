# Crisis Survival Web - Game Manager
# 游戏状态管理 + 匹配队列 + Bot 系统

import asyncio
import random
import time
from asyncio import Lock
from dataclasses import dataclass, field
from typing import Optional, Callable
from enum import Enum

# 搞笑 Bot 名字池
BOT_NAMES = [
    "躺平大师", "摸鱼冠军", "佛系青年", "咸鱼本鱼",
    "杠精附体", "键盘侠Plus", "柠檬精", "吃瓜群众",
    "嘴强王者", "理论帝", "白日梦想家", "社恐患者",
    "熬夜冠军", "拖延症晚期", "选择困难症", "咖啡成瘾者"
]


class GamePhase(Enum):
    WAITING = "waiting"
    MATCHING = "matching"
    CRISIS_SETUP = "crisis_setup"
    SCAVENGE = "scavenge"
    JUDGMENT = "judgment"
    ROUND_END = "round_end"
    GAME_OVER = "game_over"


@dataclass
class Player:
    id: str
    name: str
    websocket: Optional[object] = None
    is_bot: bool = False
    score: int = 0
    alive: bool = True
    item: Optional[dict] = None
    keyword_choice: Optional[str] = None
    
    def reset_round(self):
        self.alive = True
        self.item = None
        self.keyword_choice = None


class BotPlayer(Player):
    """AI 机器人玩家"""
    
    def __init__(self):
        name = f"[AI] {random.choice(BOT_NAMES)}"
        super().__init__(
            id=f"bot_{random.randint(1000, 9999)}",
            name=name,
            is_bot=True
        )
    
    async def choose_keyword(self, options: list[str]) -> str:
        """模拟选择关键词"""
        await asyncio.sleep(random.uniform(0.5, 1.5))
        return random.choice(options)
    
    async def grab_item(self, available_indices: list[int]) -> int:
        """模拟抢夺物品"""
        await asyncio.sleep(random.uniform(0.5, 2.5))
        if available_indices:
            return random.choice(available_indices)
        return -1


@dataclass
class GameRoom:
    """游戏房间状态"""
    room_id: str
    players: list[Player] = field(default_factory=list)
    phase: GamePhase = GamePhase.WAITING
    current_round: int = 0
    max_rounds: int = 3
    
    # 当前轮次数据
    keyword_options: dict = field(default_factory=dict)  # player_id -> [options]
    collected_keywords: list[str] = field(default_factory=list)
    crisis_data: Optional[dict] = None
    items: list[dict] = field(default_factory=list)
    judgment_results: list[dict] = field(default_factory=list)
    
    # 规则状态
    consecutive_safe_rounds: int = 0
    
    # 并发锁
    _grab_lock: Lock = field(default_factory=Lock)
    
    def add_player(self, player: Player) -> bool:
        if len(self.players) >= 3:
            return False
        self.players.append(player)
        return True
    
    def remove_player(self, player_id: str):
        self.players = [p for p in self.players if p.id != player_id]
    
    def get_player(self, player_id: str) -> Optional[Player]:
        for p in self.players:
            if p.id == player_id:
                return p
        return None
    
    def all_keywords_submitted(self) -> bool:
        return all(p.keyword_choice is not None for p in self.players)
    
    def all_items_grabbed(self) -> bool:
        return all(p.item is not None for p in self.players)
    
    def get_available_items(self) -> list[tuple[int, dict]]:
        """返回尚未被抢的物品列表 (index, item)"""
        grabbed_items = {id(p.item) for p in self.players if p.item is not None}
        return [(i, item) for i, item in enumerate(self.items) if id(item) not in grabbed_items]
    
    async def try_grab_item(self, player: Player, item_index: int) -> Optional[dict]:
        """线程安全的物品抢夺，返回抢到的物品或None"""
        async with self._grab_lock:
            if player.item is not None:
                return None  # 已经有物品了
            
            available = self.get_available_items()
            available_indices = [idx for idx, _ in available]
            
            if item_index in available_indices:
                item = self.items[item_index]
                player.item = item
                return item
            return None
    
    def reset_round(self):
        for p in self.players:
            p.reset_round()
        self.keyword_options = {}
        self.collected_keywords = []
        self.crisis_data = None
        self.items = []
        self.judgment_results = []
    
    def to_dict(self) -> dict:
        return {
            "room_id": self.room_id,
            "players": [{"id": p.id, "name": p.name, "score": p.score, "is_bot": p.is_bot} for p in self.players],
            "phase": self.phase.value,
            "current_round": self.current_round,
            "max_rounds": self.max_rounds
        }


class MatchmakingQueue:
    """匹配队列"""
    
    def __init__(self, required_players: int = 3, timeout: int = 30):
        self.queue: list[Player] = []
        self.required_players = required_players
        self.timeout = timeout
        self.on_match_callback: Optional[Callable] = None
        self._lock = Lock()  # 并发锁
    
    def join(self, player: Player) -> bool:
        """加入匹配队列"""
        if player in self.queue:
            return False
        self.queue.append(player)
        return True
    
    def leave(self, player_id: str):
        """离开匹配队列"""
        self.queue = [p for p in self.queue if p.id != player_id]
    
    def get_queue_size(self) -> int:
        return len(self.queue)
    
    def try_match(self) -> Optional[list[Player]]:
        """尝试匹配，返回匹配到的玩家列表（非线程安全，内部使用）"""
        if len(self.queue) >= self.required_players:
            matched = self.queue[:self.required_players]
            self.queue = self.queue[self.required_players:]
            return matched
        return None
    
    async def try_match_safe(self) -> Optional[list[Player]]:
        """线程安全的匹配尝试"""
        async with self._lock:
            return self.try_match()
    
    async def safe_create_match_with_bots(self, player: Player) -> Optional[list[Player]]:
        """线程安全的超时匹配（用Bot补位）"""
        async with self._lock:
            # 再次检查玩家是否还在队列
            if player not in self.queue:
                return None  # 已经被其他匹配拿走了
            
            # 收集队列中的真人玩家（包括触发超时的这个）
            real_players = [p for p in self.queue if not p.is_bot][:self.required_players]
            if player not in real_players:
                real_players = [player] + real_players[:self.required_players - 1]
            
            # 从队列移除
            for p in real_players:
                if p in self.queue:
                    self.queue.remove(p)
            
            # 补充Bot
            bots_needed = self.required_players - len(real_players)
            bots = [BotPlayer() for _ in range(bots_needed)]
            
            return real_players + bots
    
    def create_match_with_bots(self, real_players: list[Player]) -> list[Player]:
        """用 Bot 补齐玩家数量"""
        bots_needed = self.required_players - len(real_players)
        bots = [BotPlayer() for _ in range(bots_needed)]
        
        # 从队列中移除这些真人玩家
        for p in real_players:
            if p in self.queue:
                self.queue.remove(p)
        
        return real_players + bots


class GameManager:
    """全局游戏管理器"""
    
    def __init__(self):
        self.rooms: dict[str, GameRoom] = {}
        self.matchmaking = MatchmakingQueue()
        self.player_room_map: dict[str, str] = {}  # player_id -> room_id
    
    def create_room(self) -> GameRoom:
        """创建新房间"""
        room_id = self._generate_room_id()
        room = GameRoom(room_id=room_id)
        self.rooms[room_id] = room
        return room
    
    def get_room(self, room_id: str) -> Optional[GameRoom]:
        return self.rooms.get(room_id)
    
    def get_player_room(self, player_id: str) -> Optional[GameRoom]:
        room_id = self.player_room_map.get(player_id)
        if room_id:
            return self.rooms.get(room_id)
        return None
    
    def join_room(self, room: GameRoom, player: Player) -> bool:
        if room.add_player(player):
            self.player_room_map[player.id] = room.room_id
            return True
        return False
    
    def leave_room(self, player_id: str):
        room = self.get_player_room(player_id)
        if room:
            room.remove_player(player_id)
            del self.player_room_map[player_id]
            
            # 如果房间空了，删除房间
            if not room.players:
                del self.rooms[room.room_id]
    
    def _generate_room_id(self) -> str:
        """生成 4 位大写字母房间码"""
        while True:
            code = ''.join(random.choices('ABCDEFGHJKLMNPQRSTUVWXYZ', k=4))
            if code not in self.rooms:
                return code


# 全局单例
game_manager = GameManager()
