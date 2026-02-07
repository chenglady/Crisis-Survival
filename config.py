# Story Relay Simulation - Configuration

import os

# --- LLM Configuration (DeepSeek) ---
# Get your API key from: https://platform.deepseek.com/api_keys
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "").strip()

# DeepSeek API Base URL
DEEPSEEK_BASE_URL = "https://api.deepseek.com"

# Model to use for text generation
LLM_MODEL = "deepseek-chat"

# --- Game Configuration ---
# Number of players in the simulation
NUM_PLAYERS = 3

# Number of rounds to play
NUM_ROUNDS = 3

# Word limit for AI-generated story segments
STORY_SEGMENT_WORD_LIMIT = 80

# --- Crisis Mode Configuration ---
# 每轮生成的危机选项数量
NUM_CRISIS_OPTIONS = 3

# 每轮生成的物品数量 (1 神器 + 2 普通 + 2 垃圾)
NUM_SCAVENGE_ITEMS = 5

# 抢夺阶段的模拟延迟（秒），用于制造紧张感
SCAVENGE_DELAY = 0.3

# 积分规则
POINTS_SURVIVE = 1
POINTS_DEATH = 0

# --- Image Generation (Mock for now) ---
# Set to True to enable actual image generation (requires Replicate API key)
ENABLE_IMAGE_GENERATION = False
REPLICATE_API_KEY = os.environ.get("REPLICATE_API_KEY", "YOUR_REPLICATE_KEY_HERE")
