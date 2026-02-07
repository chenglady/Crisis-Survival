# Crisis Survival Web - FastAPI Server
# 后端服务器 with WebSocket

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import asyncio
import json
import uuid
import random
from pathlib import Path
from typing import Optional

from game_manager import (
    game_manager, GameRoom, Player, BotPlayer, GamePhase
)
from ai_module import (
    generate_keyword_options,
    generate_collaborative_crisis,
    generate_scavenge_items,
    judge_batch_survival
)

app = FastAPI(title="危机求生 - Crisis Survival")

# 存储 WebSocket 连接
connections: dict[str, WebSocket] = {}  # player_id -> websocket

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"


# ============================================================
# WebSocket 消息广播
# ============================================================

async def broadcast_to_room(room: GameRoom, message: dict, exclude: Optional[str] = None):
    """向房间内所有真人玩家广播消息"""
    for player in room.players:
        if player.is_bot:
            continue
        if exclude and player.id == exclude:
            continue
        ws = connections.get(player.id)
        if ws:
            try:
                await ws.send_json(message)
            except:
                pass


async def send_to_player(player_id: str, message: dict):
    """向单个玩家发送消息"""
    ws = connections.get(player_id)
    if ws:
        try:
            await ws.send_json(message)
        except:
            pass


# ============================================================
# 游戏流程控制
# ============================================================

async def run_game_loop(room: GameRoom):
    """主游戏循环"""
    
    for round_num in range(1, room.max_rounds + 1):
        room.current_round = round_num
        room.reset_round()
        
        await broadcast_to_room(room, {
            "type": "round_start",
            "round": round_num,
            "max_rounds": room.max_rounds
        })
        await asyncio.sleep(1)
        
        # ========== Phase 1: 危机设定 ==========
        room.phase = GamePhase.CRISIS_SETUP
        await run_crisis_phase(room)
        
        # ========== Phase 2: 抢夺物资 ==========
        room.phase = GamePhase.SCAVENGE
        await run_scavenge_phase(room)
        
        # ========== Phase 3: 判定生还 ==========
        room.phase = GamePhase.JUDGMENT
        await run_judgment_phase(room)
        
        # 回合结束
        room.phase = GamePhase.ROUND_END
        await broadcast_to_room(room, {
            "type": "round_end",
            "round": round_num,
            "scores": [{"name": p.name, "score": p.score} for p in room.players]
        })
        
        if round_num < room.max_rounds:
            await asyncio.sleep(3)
    
    # 游戏结束
    room.phase = GamePhase.GAME_OVER
    sorted_players = sorted(room.players, key=lambda p: p.score, reverse=True)
    
    # 检查是否有平分情况，需要用离谱理由决胜负
    tiebreaker_reason = None
    if len(sorted_players) >= 2:
        # 检查是否有分数相同的情况
        scores = [p.score for p in sorted_players]
        if len(scores) != len(set(scores)):
            # 有平分！生成离谱理由并随机打乱同分玩家
            absurd_reasons = [
                "因为你长得像个失败者",
                "你的网名透露出一股loser气质",
                "AI 掷骰子决定的，怪你运气不好",
                "你的键盘敲击频率暴露了你的菜",
                "凭直觉，AI 觉得你不配赢",
                "你的IP地址风水不好",
                "你妈昨晚托梦说让你输",
                "系统检测到你偷偷放屁，扣分",
                "你的头像散发着输家的气息",
                "AI 的猫踩到键盘选中了你垫底"
            ]
            tiebreaker_reason = random.choice(absurd_reasons)
            
            # 对同分玩家随机排序
            score_groups = {}
            for p in sorted_players:
                if p.score not in score_groups:
                    score_groups[p.score] = []
                score_groups[p.score].append(p)
            
            final_order = []
            for score in sorted(score_groups.keys(), reverse=True):
                group = score_groups[score]
                random.shuffle(group)
                final_order.extend(group)
            sorted_players = final_order
    
    await broadcast_to_room(room, {
        "type": "game_over",
        "rankings": [{"name": p.name, "score": p.score, "is_bot": p.is_bot} for p in sorted_players],
        "tiebreaker_reason": tiebreaker_reason
    })


async def run_crisis_phase(room: GameRoom):
    """危机设定阶段"""
    await broadcast_to_room(room, {"type": "phase_change", "phase": "crisis_setup"})
    
    # 为每个玩家生成关键词选项
    for player in room.players:
        options = await generate_keyword_options(3)
        room.keyword_options[player.id] = options
        
        if player.is_bot:
            # Bot 自动选择
            asyncio.create_task(bot_choose_keyword(room, player, options))
        else:
            await send_to_player(player.id, {
                "type": "keyword_options",
                "options": options
            })
    
    # 等待所有玩家提交 (最多 30 秒)
    for _ in range(30):
        if room.all_keywords_submitted():
            break
        await asyncio.sleep(1)
    
    # 超时的玩家随机选一个
    for player in room.players:
        if player.keyword_choice is None:
            options = room.keyword_options.get(player.id, ["未知"])
            player.keyword_choice = options[0]
            room.collected_keywords.append(player.keyword_choice)
    
    # 生成危机
    await broadcast_to_room(room, {"type": "generating_crisis"})
    crisis_data = await generate_collaborative_crisis(room.collected_keywords)
    room.crisis_data = crisis_data
    
    await broadcast_to_room(room, {
        "type": "crisis_revealed",
        "name": crisis_data.get("name", "未知危机"),
        "scenario": crisis_data.get("scenario", "危机来袭！"),
        "keywords": room.collected_keywords
    })
    await asyncio.sleep(3)


async def bot_choose_keyword(room: GameRoom, bot: BotPlayer, options: list[str]):
    """Bot 选择关键词"""
    choice = await bot.choose_keyword(options)
    bot.keyword_choice = choice
    room.collected_keywords.append(choice)


async def run_scavenge_phase(room: GameRoom):
    """抢夺物资阶段"""
    crisis_name = room.crisis_data.get("name", "危机") if room.crisis_data else "危机"
    
    # 生成物品
    items = await generate_scavenge_items(crisis_name, 5)
    room.items = items
    
    await broadcast_to_room(room, {
        "type": "phase_change",
        "phase": "scavenge",
        "items": [{"index": i, "name": item["name"], "tier": item["tier"]} for i, item in enumerate(items)]
    })
    
    # 启动 Bot 抢夺任务
    for player in room.players:
        if player.is_bot:
            asyncio.create_task(bot_grab_item(room, player))
    
    # 等待所有玩家抢夺完成 (最多 15 秒)
    for _ in range(15):
        if room.all_items_grabbed():
            break
        await asyncio.sleep(1)
    
    # 超时的玩家随机分配剩余物品
    available = room.get_available_items()
    for player in room.players:
        if player.item is None and available:
            idx, item = available.pop(0)
            player.item = item
            await broadcast_to_room(room, {
                "type": "item_grabbed",
                "player": player.name,
                "item_index": idx,
                "item_name": item["name"],
                "tier": item["tier"],
                "comment": item.get("pickup_comment", "...")
            })
    
    await asyncio.sleep(2)


async def bot_grab_item(room: GameRoom, bot: BotPlayer):
    """Bot 抢夺物品"""
    available = room.get_available_items()
    if not available:
        return
    
    available_indices = [idx for idx, _ in available]
    chosen_idx = await bot.grab_item(available_indices)
    
    # 再次检查是否还可用
    available = room.get_available_items()
    available_indices = [idx for idx, _ in available]
    
    if chosen_idx in available_indices:
        item = room.items[chosen_idx]
        bot.item = item
        await broadcast_to_room(room, {
            "type": "item_grabbed",
            "player": bot.name,
            "item_index": chosen_idx,
            "item_name": item["name"],
            "tier": item["tier"],
            "comment": item.get("pickup_comment", "...")
        })
    elif available_indices:
        # 选的被抢了，换一个
        chosen_idx = available_indices[0]
        item = room.items[chosen_idx]
        bot.item = item
        await broadcast_to_room(room, {
            "type": "item_grabbed",
            "player": bot.name,
            "item_index": chosen_idx,
            "item_name": item["name"],
            "tier": item["tier"],
            "comment": item.get("pickup_comment", "...")
        })


async def run_judgment_phase(room: GameRoom):
    """判定生还阶段"""
    await broadcast_to_room(room, {"type": "phase_change", "phase": "judgment"})
    await asyncio.sleep(1)
    
    crisis_name = room.crisis_data.get("name", "危机") if room.crisis_data else "危机"
    
    # 准备判定数据
    players_data = []
    for p in room.players:
        players_data.append({
            "name": p.name,
            "item": p.item or {"name": "空手", "tier": "trash"}
        })
    
    # 判断是否强制死亡
    force_death = room.consecutive_safe_rounds >= 2
    
    await broadcast_to_room(room, {"type": "judging"})
    results = await judge_batch_survival(crisis_name, players_data, force_death=force_death)
    room.judgment_results = results
    
    any_death = False
    
    # 逐个公布结果
    for result in results:
        # Find player by name (safer than index)
        player_name = result.get("name")
        target_player = None
        for p in room.players:
            if p.name == player_name:
                target_player = p
                break
        
        # If player not found (e.g. left and glitch happened), skip
        if not target_player:
            continue
            
        if result.get("survived", True):
            target_player.score += 1
            target_player.alive = True
        else:
            target_player.alive = False
            any_death = True
        
        await broadcast_to_room(room, {
            "type": "judgment_result",
            "player": target_player.name,
            "survived": result.get("survived", True),
            "story": result.get("story", "命运已定..."),
            "item": target_player.item.get("name", "") if target_player.item else ""
        })
        await asyncio.sleep(7)  # 7秒阅读时间
    
    # 更新连续安全轮数
    if any_death:
        room.consecutive_safe_rounds = 0
    else:
        room.consecutive_safe_rounds += 1


# ============================================================
# WebSocket 端点
# ============================================================

@app.websocket("/ws/{player_name}")
async def websocket_endpoint(websocket: WebSocket, player_name: str):
    await websocket.accept()
    
    player_id = str(uuid.uuid4())
    player = Player(id=player_id, name=player_name)
    connections[player_id] = websocket
    
    await websocket.send_json({
        "type": "connected",
        "player_id": player_id,
        "message": f"欢迎, {player_name}!"
    })
    
    try:
        while True:
            try:
                data = await websocket.receive_json()
                await handle_message(player, data)
            except RuntimeError:
                break  # WebSocket 连接异常（例如未握手成功就断开）
    except WebSocketDisconnect:
        # 清理连接
        if player_id in connections:
            del connections[player_id]
        game_manager.matchmaking.leave(player_id)
        game_manager.leave_room(player_id)


async def handle_message(player: Player, data: dict):
    """处理客户端消息"""
    msg_type = data.get("type")
    
    if msg_type == "start_matching":
        await handle_start_matching(player)
    
    elif msg_type == "cancel_matching":
        game_manager.matchmaking.leave(player.id)
        await send_to_player(player.id, {"type": "matching_cancelled"})
    
    elif msg_type == "keyword_choice":
        await handle_keyword_choice(player, data.get("choice"))
    
    elif msg_type == "grab_item":
        await handle_grab_item(player, data.get("index"))
    
    elif msg_type == "start_solo":
        await handle_start_solo(player)
    
    elif msg_type == "exit_game":
        await handle_player_exit(player)


async def handle_start_solo(player: Player):
    """处理单人模式：立即创建房间 + 2 AI 开始游戏"""
    from game_manager import BotPlayer
    
    bots = [BotPlayer(), BotPlayer()]
    all_players = [player] + bots
    await start_game_with_players(all_players)


async def handle_player_exit(player: Player):
    """处理玩家退出，用AI接管"""
    room = game_manager.get_player_room(player.id)
    if not room:
        return
    
    # 找到该玩家并替换为Bot
    for i, p in enumerate(room.players):
        if p.id == player.id:
            # 创建一个继承该玩家状态的Bot
            bot = BotPlayer()
            bot.name = f"[AI] {player.name}"
            bot.score = p.score
            bot.item = p.item
            bot.keyword_choice = p.keyword_choice
            bot.alive = p.alive
            room.players[i] = bot
            
            await broadcast_to_room(room, {
                "type": "player_left",
                "player": player.name,
                "message": f"{player.name} 已退出，AI 接管了他的角色"
            })
            break
    
    # 清理连接
    if player.id in connections:
        del connections[player.id]


async def handle_start_matching(player: Player):
    """处理开始匹配"""
    game_manager.matchmaking.join(player)
    
    await send_to_player(player.id, {
        "type": "matching_started",
        "queue_size": game_manager.matchmaking.get_queue_size()
    })
    
    # 尝试匹配（线程安全）
    matched = await game_manager.matchmaking.try_match_safe()
    
    if matched:
        # 匹配成功
        await start_game_with_players(matched)
    else:
        # 启动超时任务
        asyncio.create_task(matching_timeout(player))


async def matching_timeout(player: Player):
    """匹配超时处理"""
    await asyncio.sleep(30)  # 30 秒超时
    
    # 使用线程安全方法创建匹配
    all_players = await game_manager.matchmaking.safe_create_match_with_bots(player)
    if all_players:
        await start_game_with_players(all_players)


async def start_game_with_players(players: list[Player]):
    """创建房间并开始游戏"""
    room = game_manager.create_room()
    
    for p in players:
        game_manager.join_room(room, p)
    
    # 通知所有真人玩家
    for p in players:
        if not p.is_bot:
            await send_to_player(p.id, {
                "type": "game_starting",
                "room_id": room.room_id,
                "players": [{"name": pl.name, "is_bot": pl.is_bot} for pl in players]
            })
    
    await asyncio.sleep(2)
    
    # 启动游戏循环
    asyncio.create_task(run_game_loop(room))


async def handle_keyword_choice(player: Player, choice: str):
    """处理关键词选择"""
    room = game_manager.get_player_room(player.id)
    if not room or room.phase != GamePhase.CRISIS_SETUP:
        return
    
    room_player = room.get_player(player.id)
    if room_player and room_player.keyword_choice is None:
        room_player.keyword_choice = choice
        room.collected_keywords.append(choice)
        
        await broadcast_to_room(room, {
            "type": "keyword_submitted",
            "player": player.name
        })


async def handle_grab_item(player: Player, item_index: int):
    """处理抢夺物品（线程安全）"""
    room = game_manager.get_player_room(player.id)
    if not room or room.phase != GamePhase.SCAVENGE:
        return
    
    room_player = room.get_player(player.id)
    if not room_player:
        return
    
    # 使用线程安全的抢夺方法
    item = await room.try_grab_item(room_player, item_index)
    
    if item:
        await broadcast_to_room(room, {
            "type": "item_grabbed",
            "player": player.name,
            "item_index": item_index,
            "item_name": item["name"],
            "tier": item["tier"],
            "comment": item.get("pickup_comment", "...")
        })
    else:
        await send_to_player(player.id, {
            "type": "grab_failed",
            "message": "手慢了！这个物品已被抢走"
        })


# ============================================================
# 静态文件服务
# ============================================================

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def root():
    return HTMLResponse(content=(STATIC_DIR / "index.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
