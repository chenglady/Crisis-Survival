# Story Relay Simulation 2.0 - Crisis Survival Mode
# 危机求生模式 - 主游戏循环

from config import (
    NUM_PLAYERS, NUM_ROUNDS, 
    NUM_CRISIS_OPTIONS, NUM_SCAVENGE_ITEMS, 
    SCAVENGE_DELAY, POINTS_SURVIVE, POINTS_DEATH
)
from ai_module import (
    generate_collaborative_crisis,
    generate_scavenge_items,
    judge_batch_survival,
    generate_keyword_options
)
import asyncio
import time
import random
import sys


# Some Windows terminals / redirected outputs use GBK/CP936 and can't encode emojis.
# Avoid crashing by replacing unencodable characters (emojis become '?').
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(errors="replace")
        sys.stderr.reconfigure(errors="replace")
    except Exception:
        pass

# --- Terminal Colors for better readability ---
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    MAGENTA = '\033[35m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text.center(60)}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


def print_crisis(text):
    print(f"{Colors.RED}{Colors.BOLD}🚨 {text}{Colors.ENDC}\n")


def print_story(text, label=None):
    if label:
        print(f"{Colors.CYAN}[{label}]{Colors.ENDC}")
    print(f"{Colors.GREEN}{text}{Colors.ENDC}\n")


def print_item(index, item, available=True):
    tier_colors = {
        "legendary": Colors.YELLOW + Colors.BOLD,
        "normal": Colors.BLUE,
        "trash": Colors.MAGENTA
    }
    tier_icons = {
        "legendary": "⭐",
        "normal": "📦",
        "trash": "🗑️"
    }
    color = tier_colors.get(item["tier"], Colors.ENDC)
    icon = tier_icons.get(item["tier"], "?")
    
    if available:
        print(f"  {Colors.BOLD}{index}. {color}{icon} {item['name']}{Colors.ENDC}")
    else:
        print(f"  {Colors.BOLD}{index}. {Colors.RED}[已被抢走]{Colors.ENDC}")


def print_result(survived, player_name):
    if survived:
        print(f"{Colors.GREEN}{Colors.BOLD}✅ {player_name} 生还了！(+{POINTS_SURVIVE}分){Colors.ENDC}")
    else:
        print(f"{Colors.RED}{Colors.BOLD}❌ {player_name} 死亡了...{Colors.ENDC}")


def print_scores(players):
    print(f"\n{Colors.CYAN}--- 当前积分 ---{Colors.ENDC}")
    for p in players:
        print(f"  {p['name']}: {Colors.YELLOW}{p['score']}分{Colors.ENDC}")
    print()


async def get_player_keyword_choice(player_name):
    """让玩家从 AI 提供的选项中选择一个关键词。"""
    print(f"\n{Colors.YELLOW}[⏳ AI 正在为 {player_name} 生成灵感...]{Colors.ENDC}")
    options = await generate_keyword_options(NUM_CRISIS_OPTIONS)
    
    print(f"{Colors.CYAN}{player_name}，请选择一个贡献给危机的元素（越离谱越好）：{Colors.ENDC}")
    for i, opt in enumerate(options, 1):
        print(f"  {Colors.BOLD}{i}. {Colors.RED}{opt}{Colors.ENDC}")
    print(f"  {Colors.BOLD}0. 自定义输入{Colors.ENDC}")
    
    while True:
        try:
            choice = input("> ").strip()
            if not choice:
                return options[0]
            
            idx = int(choice)
            if idx == 0:
                custom = input(f"{Colors.CYAN}请输入自定义关键词: {Colors.ENDC}").strip()
                return custom if custom else options[0]
            elif 1 <= idx <= len(options):
                return options[idx - 1]
            else:
                print(f"{Colors.RED}无效选择{Colors.ENDC}")
        except ValueError:
            print(f"{Colors.RED}请输入数字{Colors.ENDC}")


def scavenge_phase(players, items):
    """
    抢夺阶段 - CLI 模拟版本
    随机决定抢夺顺序，每人依次快速选择
    """
    print_header("🎒 抢夺物资阶段")
    print(f"{Colors.YELLOW}物品出现了！先到先得！{Colors.ENDC}\n")
    
    # 显示所有物品
    available = list(range(len(items)))  # 可用物品的索引
    
    # 随机决定抢夺顺序
    order = list(range(len(players)))
    random.shuffle(order)
    
    print(f"{Colors.CYAN}抢夺顺序: {', '.join([players[i]['name'] for i in order])}{Colors.ENDC}\n")
    
    for player_idx in order:
        player = players[player_idx]
        
        # 显示当前可用物品
        print(f"{Colors.BOLD}--- {player['name']} 的回合 ---{Colors.ENDC}")
        print(f"{Colors.CYAN}可选物品：{Colors.ENDC}")
        
        for i in range(len(items)):
            print_item(i + 1, items[i], i in available)
        
        # 玩家选择
        print(f"\n{Colors.CYAN}{player['name']}，快选一个！(输入数字):{Colors.ENDC}")
        
        while True:
            try:
                choice = input("> ").strip()
                if not choice:
                    # 默认选第一个可用的
                    if available:
                        chosen_idx = available[0]
                        break
                else:
                    chosen_idx = int(choice) - 1
                    if chosen_idx in available:
                        break
                    else:
                        print(f"{Colors.RED}这个物品已经被抢走了！选别的！{Colors.ENDC}")
            except ValueError:
                print(f"{Colors.RED}请输入数字{Colors.ENDC}")
        
        # 分配物品
        player["item"] = items[chosen_idx]
        available.remove(chosen_idx)
        
        tier_display = {"legendary": "神器", "normal": "普通", "trash": "垃圾"}
        tier = tier_display.get(player["item"]["tier"], "?")
        print(f"{Colors.GREEN}✓ {player['name']} 抢到了: {player['item']['name']} ({tier}){Colors.ENDC}")
        
        # 显示 AI 吐槽
        comment = player["item"].get("pickup_comment", "有趣的发现。")
        print(f"{Colors.YELLOW}   💬 AI吐槽: \"{comment}\"{Colors.ENDC}\n")
        
        time.sleep(SCAVENGE_DELAY)
    
    return players


async def judgment_phase(players, crisis, safe_rounds_count):
    """判定阶段 - AI 批量判定每位玩家的命运"""
    print_header("⚖️ 命运判定阶段")
    
    # Check if we need to force a death (Max 2 Safe Rounds Rule)
    force_death = False
    if safe_rounds_count >= 2:
        print(f"{Colors.RED}{Colors.BOLD}⚠️ 连续 {safe_rounds_count} 轮无人死亡，本轮生存难度极大提升！{Colors.ENDC}\n")
        force_death = True
    
    print(f"{Colors.YELLOW}[⏳ AI 正在审判所有人的命运...]{Colors.ENDC}")
    
    # Batch call to AI
    results = await judge_batch_survival(crisis, players, force_death=force_death)
    
    any_death = False
    
    # Process results
    # We need to match results back to players (assuming order is preserved, which it is)
    for i, result in enumerate(results):
        player = players[i] # Warning: ensure 'players' list order wasn't shuffled inside this function scope differently than passed to AI
        
        # Verify name match just in case
        # if player['name'] != result['name']: print("Warning: Name mismatch in batch result")
        
        print(f"\n{Colors.BOLD}--- 判定 {player['name']} ---{Colors.ENDC}")
        print(f"{Colors.CYAN}物品: {player['item']['name']}{Colors.ENDC}")
        
        print_story(result["story"], "📖 命运")
        
        if result["survived"]:
            player["score"] += POINTS_SURVIVE
            player["alive"] = True
        else:
            player["alive"] = False
            any_death = True
        
        print_result(result["survived"], player["name"])
        time.sleep(0.5)
        
    return any_death


def show_final_scores(players):
    """显示最终积分和排名"""
    print_header("🏆 最终结果")
    
    # 按分数排序
    sorted_players = sorted(players, key=lambda x: x["score"], reverse=True)
    
    medals = ["🥇", "🥈", "🥉"]
    
    for i, player in enumerate(sorted_players):
        medal = medals[i] if i < len(medals) else "  "
        print(f"  {medal} {player['name']}: {Colors.YELLOW}{Colors.BOLD}{player['score']}分{Colors.ENDC}")
    
    # 宣布冠军
    winner = sorted_players[0]
    print(f"\n{Colors.GREEN}{Colors.BOLD}🎉 恭喜 {winner['name']} 获得胜利！{Colors.ENDC}")


async def main():
    print_header("🎮 危机求生模拟器 (Crisis Survival Simulator)")
    print(f"版本: 2.0 - 危机模式")
    print(f"玩家人数: {NUM_PLAYERS}")
    print(f"回合数: {NUM_ROUNDS}")
    print(f"\n{Colors.BOLD}游戏规则：{Colors.ENDC}")
    print("  1. 所有玩家共同贡献关键词，AI生成融合危机")
    print("  2. 每轮玩家随机顺序抢夺物资（手慢无）")
    print("  3. AI 判定每位玩家能否用物品逃过危机")
    print(f"  4. 生还得 {POINTS_SURVIVE} 分，死亡得 {POINTS_DEATH} 分")
    print("  5. 每轮最多死 1 人，若连续 2 轮无人死亡，第三轮将强制提升难度")
    print(f"\n{Colors.BOLD}准备好了吗？按 Enter 开始游戏...{Colors.ENDC}")
    input()
    
    # 初始化玩家
    players = [
        {"name": f"玩家 {i+1}", "score": 0, "alive": True, "item": None}
        for i in range(NUM_PLAYERS)
    ]
    
    consecutive_safe_rounds = 0
    
    # --- 主游戏循环 ---
    for round_num in range(NUM_ROUNDS):
        print_header(f"🔄 第 {round_num + 1} / {NUM_ROUNDS} 轮")
        
        # 重置本轮状态
        for p in players:
            p["alive"] = True
            p["item"] = None
        
        # ========== Phase 1: 危机设定 ==========
        print_header("⚠️ 危机设定阶段")
        print(f"{Colors.YELLOW}每位玩家请从 AI 提供的选项中选择一个关键元素，共同组合成本轮危机！{Colors.ENDC}\n")
        
        round_keywords = []
        for p in players:
            kw = await get_player_keyword_choice(p["name"])
            round_keywords.append(kw)
        
        print(f"\n{Colors.CYAN}收集到的关键词: {', '.join(round_keywords)}{Colors.ENDC}\n")
        
        # 生成危机场景
        print(f"{Colors.YELLOW}[⏳ AI 正在融合危机场景...]{Colors.ENDC}\n")
        
        crisis_data = await generate_collaborative_crisis(round_keywords)
        crisis_word = crisis_data["name"]
        
        print(f"\n{Colors.RED}{Colors.BOLD}☠️ 本轮危机: 【{crisis_word}】{Colors.ENDC}")
        print_crisis(crisis_data["scenario"])
        
        time.sleep(1)
        
        # ========== Phase 2: 抢夺物资 ==========
        print(f"{Colors.YELLOW}[⏳ AI 正在生成物品...]{Colors.ENDC}")
        items = await generate_scavenge_items(crisis_word, NUM_SCAVENGE_ITEMS)
        
        # 打乱物品顺序，增加随机性
        random.shuffle(items)
        
        scavenge_phase(players, items)
        
        # ========== Phase 3: 判定生还 ==========
        any_death = await judgment_phase(players, crisis_word, consecutive_safe_rounds)
        
        if any_death:
            consecutive_safe_rounds = 0
            print(f"\n{Colors.MAGENTA}☠️ 有人牺牲了，幸存者计数重置。{Colors.ENDC}\n")
        else:
            consecutive_safe_rounds += 1
            print(f"\n{Colors.GREEN}🕊️ 全员生还！连续生还轮数: {consecutive_safe_rounds}{Colors.ENDC}\n")
        
        # 显示本轮结束后的积分
        print_scores(players)
        
        if round_num < NUM_ROUNDS - 1:
            print(f"{Colors.CYAN}按 Enter 进入下一轮...{Colors.ENDC}")
            input()
    
    # --- 游戏结束 ---
    show_final_scores(players)
    print_header("🎬 游戏结束！")


if __name__ == "__main__":
    asyncio.run(main())
