# Story Relay Simulation - AI Module (DeepSeek)

from openai import AsyncOpenAI
from config import DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, LLM_MODEL, STORY_SEGMENT_WORD_LIMIT
import json
import re

# Configure DeepSeek client (OpenAI-compatible API) - ASYNC version
client = AsyncOpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)


_warned_missing_key = False
_warned_llm_failure = False


async def call_llm(prompt: str) -> str:
    """Call DeepSeek API asynchronously and return the response text."""
    global _warned_missing_key, _warned_llm_failure

    if not DEEPSEEK_API_KEY:
        if not _warned_missing_key:
            print("[Warning] DEEPSEEK_API_KEY is not set; using fallback content.")
            _warned_missing_key = True
        return ""

    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": "你是一个嘴巴很毒、喜欢嘲讽人类、脑洞大开的故事讲述者。即使是好消息，你也能说得阴阳怪气。"},
                {"role": "user", "content": prompt}
            ],
            temperature=1.3,
            max_tokens=500
        )
        return response.choices[0].message.content or ""
    except Exception as e:
        if not _warned_llm_failure:
            print(f"[Warning] LLM call failed ({type(e).__name__}): {e}")
            _warned_llm_failure = True
        return ""


def parse_json_response(text: str, fallback: dict) -> dict:
    """Extract JSON from LLM response."""
    try:
        json_match = re.search(r'\{[\s\S]*\}', text)
        if json_match:
            return json.loads(json_match.group())
        return fallback
    except Exception as e:
        print(f"[Warning] Failed to parse JSON: {e}")
        return fallback


async def generate_opening(player_keywords: list[str]) -> dict:
    """
    Generate an opening story segment based on keywords contributed by all players.
    """
    keywords_str = ", ".join(player_keywords)
    
    prompt = f"""玩家们贡献了以下关键词来开启故事：{keywords_str}

请根据这些关键词，生成一个**荒诞、有趣、引人入胜**的故事开头（约{STORY_SEGMENT_WORD_LIMIT}字）。
这个开头应该设定好场景、主要角色（或物品），并留下一个悬念让故事可以继续发展。

同时，请为这个开头生成一个适合AI绘图的英文Prompt（用于Stable Diffusion）。

请严格按照以下JSON格式返回，不要包含任何其他内容：
{{
  "story": "你的故事开头内容",
  "image_prompt": "English prompt for image generation, include style keywords like 'vibrant colors, digital art, cinematic lighting'"
}}"""
    
    text = await call_llm(prompt)
    return parse_json_response(text, {"story": text, "image_prompt": "abstract surreal scene, digital art"})


async def generate_keywords_for_player(story_so_far: str, num_keywords: int = 5) -> list[str]:
    """
    Generate a set of random, disparate keywords for a player to choose from.
    """
    prompt = f"""当前故事进度：
---
{story_so_far}
---

现在轮到下一位玩家了。请为他/她提供 {num_keywords} 个**完全不相关、荒诞离奇**的关键词供选择。
这些词应该能够把故事带向意想不到的方向。
可以是名词、动词、形容词，甚至是一个短语。
尽量避免与当前故事已有元素过于相似的词。

请严格按照以下JSON格式返回，不要包含任何其他内容：
{{
  "keywords": ["关键词1", "关键词2", "关键词3", "关键词4", "关键词5"]
}}"""
    
    text = await call_llm(prompt)
    result = parse_json_response(text, {"keywords": ["爆炸", "香蕉", "外星人", "时间倒流", "马桶"]})
    return result.get("keywords", [])[:num_keywords]


async def generate_story_continuation(story_so_far: str, selected_keywords: list[str]) -> dict:
    """
    Generate the next story segment based on selected keywords.
    """
    keywords_str = ", ".join(selected_keywords)
    
    prompt = f"""当前故事进度：
---
{story_so_far}
---

玩家选择了以下关键词来推动剧情：{keywords_str}

请根据这些关键词，**自然地**续写故事（约{STORY_SEGMENT_WORD_LIMIT}字）。
要求：
1. 必须包含所选关键词的元素
2. 与前文保持连贯，但要有出人意料的转折
3. 保持幽默和荒诞的风格
4. 留下悬念让故事可以继续

同时，请为这段新内容生成一个适合AI绘图的英文Prompt。

请严格按照以下JSON格式返回：
{{
  "story": "你的续写内容",
  "image_prompt": "English prompt for image generation"
}}"""
    
    text = await call_llm(prompt)
    return parse_json_response(text, {"story": text, "image_prompt": "surreal scene, digital art"})


async def generate_ending(story_so_far: str) -> dict:
    """
    Generate a satisfying (or hilariously unsatisfying) ending for the story.
    """
    prompt = f"""完整故事：
---
{story_so_far}
---

请为这个故事写一个**令人意想不到**的结局（约{STORY_SEGMENT_WORD_LIMIT}字）。
可以是：
- 一个荒诞的反转
- 一个莫名其妙的"原来是一场梦"
- 一个 Breaking the Fourth Wall 的结局
- 或者任何让人拍腿叫绝的收尾

请严格按照以下JSON格式返回：
{{
  "story": "你的结局内容",
  "image_prompt": "English prompt for the final scene"
}}"""
    
    text = await call_llm(prompt)
    return parse_json_response(text, {"story": text, "image_prompt": "epic finale, digital art"})


# ============================================================
# Crisis Mode - 危机求生模式 AI 函数
# ============================================================

async def generate_crisis_options(num_options: int = 3) -> list[str]:
    """生成随机危机词供玩家选择。"""
    prompt = f"""请生成 {num_options} 个**荒诞离奇、紧急危险**的危机场景关键词。
例如：僵尸潮、火山爆发、巨型章鱼入侵、时空裂缝、外星人绑架等。
确保每个都足够戏剧性和荒诞，同时彼此风格不同。

请严格按照以下JSON格式返回，不要包含任何其他内容：
{{
  "crises": ["危机1", "危机2", "危机3"]
}}"""
    text = await call_llm(prompt)
    result = parse_json_response(text, {"crises": ["僵尸潮", "火山爆发", "外星人入侵"]})
    return result.get("crises", [])[:num_options]


async def generate_keyword_options(num_options: int = 3) -> list[str]:
    """生成一组供单人选择的随机关键词。"""
    prompt = f"""请生成 {num_options} 个**绝对离谱、完全不相关、让人一脸问号**的名词或短语。

要求：
1. 必须荒诞至极，例如：奶奶的假牙、量子纠缠的泡面、会说话的马桶刷、时间倒流的脚气
2. 尽量避免常见词汇，越冷门越好
3. 可以是物品、现象、职业、动物、食物的奇怪组合
4. 每次生成的词必须不同，发挥你的创造力！

一些灵感方向（随机选择，不要全用）：
- 身体部位 + 奇怪状态：会唱歌的膝盖、通货膨胀的眉毛
- 日用品 + 超自然：有灵魂的橡皮擦、预言未来的插座
- 食物 + 抽象概念：焦虑的饺子、存在主义的老干妈
- 动物 + 职业：考公的鲶鱼、炒股的鹦鹉
- 科技 + 古代：5G仙丹、蓝牙诸葛亮

请严格按照以下JSON格式返回：
{{
  "keywords": ["词1", "词2", "词3"]
}}"""
    text = await call_llm(prompt)
    result = parse_json_response(text, {"keywords": ["会飞的假牙", "量子力学的脚气", "通货膨胀的眉毛"]})
    return result.get("keywords", [])[:num_options]


async def generate_collaborative_crisis(keywords: list[str]) -> dict:
    """根据所有玩家提供的关键词生成融合危机。"""
    keywords_str = ", ".join(keywords)
    prompt = f"""玩家们分别提供了以下关键词：{keywords_str}

请将这些看似不相关的词汇**强行融合**，生成一个**荒诞、史诗级**的危机场景（约80字）。
这个危机应该是所有玩家必须共同面对的灾难。
脑洞要大，逻辑要“一本正经地胡说八道”。

同时生成适合AI绘图的英文Prompt。

请严格按照以下JSON格式返回：
{{
  "name": "给这个危机起个霸气的名字",
  "scenario": "危机场景描述",
  "image_prompt": "English prompt for crisis scene, include dramatic lighting, cinematic style"
}}"""
    text = await call_llm(prompt)
    return parse_json_response(text, {
        "name": "混沌风暴",
        "scenario": f"由 {keywords_str} 引发的时空错乱风暴正在摧毁一切！",
        "image_prompt": "chaotic storm, surreal elements, cinematic"
    })


async def generate_scavenge_items(crisis: str, num_items: int = 5) -> list[dict]:
    """生成抢夺阶段的物品列表：1神器 + 2普通 + 2垃圾。"""
    prompt = f"""当前危机：{crisis}

请生成 {num_items} 个可以被玩家抢夺的物品，包括：
- 1 个【神器/legendary】：明显能用来解决当前危机的强力道具
- 2 个【普通物品/normal】：可能有用也可能没用的东西
- 2 个【垃圾/trash】：看起来完全没用的废物

要求：
1. 物品要荒诞有趣，不要太正经
2. 每个物品都要有创意，避免无聊的选项
3. 垃圾物品也要有梗
4. **为每个物品写一句简短的拾取吐槽/评语**（pickup_comment），**风格要极其毒舌、嘲讽、阴阳怪气**。比如"你以为这能救你？"、"垃圾配垃圾，绝配。"

请严格按照以下JSON格式返回：
{{
  "items": [
    {{"name": "物品名", "tier": "legendary", "pickup_comment": "吐槽内容"}},
    {{"name": "物品名", "tier": "normal", "pickup_comment": "吐槽内容"}},
    {{"name": "物品名", "tier": "normal", "pickup_comment": "吐槽内容"}},
    {{"name": "物品名", "tier": "trash", "pickup_comment": "吐槽内容"}},
    {{"name": "物品名", "tier": "trash", "pickup_comment": "吐槽内容"}}
  ]
}}"""
    text = await call_llm(prompt)
    fallback = {"items": [
        {"name": "神秘的万能按钮", "tier": "legendary", "pickup_comment": "千万别乱按！"},
        {"name": "生锈的消防斧", "tier": "normal", "pickup_comment": "希望能砍断点什么。"},
        {"name": "过期的能量饮料", "tier": "normal", "pickup_comment": "喝了可能会拉肚子。"},
        {"name": "半根香蕉", "tier": "trash", "pickup_comment": "谁吃剩下的？"},
        {"name": "破洞的袜子", "tier": "trash", "pickup_comment": "味道有点冲..."}
    ]}
    result = parse_json_response(text, fallback)
    items = result.get("items", [])
    # 确保返回正确数量
    return items[:num_items] if len(items) >= num_items else fallback["items"][:num_items]


async def judge_batch_survival(crisis: str, players_data: list[dict], force_death: bool = False) -> list[dict]:
    """
    批量判定所有玩家的命运。
    Constraint 1: 每轮最多死 1 人 (Max 1 Death per Round)
    Constraint 2: force_death=True 时，尽量保证有一人死亡 (Max 2 Safe Rounds rule)
    """
    
    players_desc = []
    for i, p in enumerate(players_data):
        item_tier = p['item'].get("tier", "normal")
        players_desc.append(f"Player {i+1} ({p['name']}): 物品='{p['item']['name']}' (品质: {item_tier})")
    
    players_block = "\n".join(players_desc)
    
    rules_text = """
1. **每轮最多只能死 1 个人**。即使多个人都拿了垃圾，你也只能选一个"最倒霉"的带走，其他人必须以某种荒诞的理由幸存。
2. **随机性高于一切**！不要总是让最后一个玩家死，也不要太看重物品品质：
   - 拿到神器(legendary)也可能因为太嘚瑟被天降陨石砸死
   - 拿到垃圾(trash)也可能靠着逆天运气或神秘力量活下来
   - 请**随机**选择谁死谁活，不要有固定模式
3. 用**毒舌嘲讽的语气**描述结果，无论生死都要极尽嘲讽。

"""

    if force_death:
        rules_text += "\n4. **强制危机模式**：本轮**必须**有一人死亡。在所有玩家中**随机**选择一个倒霉蛋，编造一个离谱的死法。"

    prompt = f"""当前危机：{crisis}

玩家状态：
{players_block}

请根据规则判定所有玩家的命运：
规则：{rules_text}

对于每位玩家，请生成一段**简短且荒诞**的剧情描述（约40字）。

请严格按照以下JSON格式返回列表（顺序对应输入玩家）：
{{
  "results": [
    {{
      "name": "玩家名",
      "survived": true,
      "story": "生还/死亡剧情",
      "image_prompt": "English prompt"
    }},
    ...
  ]
}}"""
    
    text = await call_llm(prompt)
    
    # Fallback default (everyone survives)
    fallback_results = []
    for p in players_data:
        fallback_results.append({
            "name": p['name'],
            "survived": True, 
            "story": f"{p['name']} 侥幸逃过一劫。",
            "image_prompt": "survivor scene"
        })
    
    json_data = parse_json_response(text, {"results": fallback_results})
    results = json_data.get("results", [])
    
    # Consistency check: Ensure list length matches
    if len(results) != len(players_data):
        return fallback_results
        
    return results

