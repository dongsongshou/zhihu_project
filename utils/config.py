import os
import time
from dotenv import load_dotenv

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, ".env")
load_dotenv(dotenv_path=env_path)

# ==========本地调试临时写死密钥，调试完成立刻删掉这一段！！==========
ZHIHU_ACCESS_SECRET = "be85c5ce20f6a9dc1642d180cf08496420727e20"
# =================================================================

ZHIHU_SEARCH_API_URL = "https://developer.zhihu.com/api/v1/content/zhihu_search"

ZHIHU_AGENT_BASE_URL = os.getenv("ZHIHU_AGENT_BASE_URL", "https://api.zhihu.com/v1")
ZHIHU_AGENT_API_KEY = os.getenv("ZHIHU_AGENT_API_KEY", "")

ZHIHU_OPENAPI_AVAILABLE = len(ZHIHU_ACCESS_SECRET.strip()) > 0
DEMO_MODE = len(ZHIHU_AGENT_API_KEY.strip()) == 0

CACHE_TTL = 3600
VECTOR_DIM = 8
CLUSTER_NUM = 3

def get_timestamp() -> int:
    return int(time.time())

print("=== .env调试 ===")
print(f"env_path: {env_path}")
print(f"文件是否存在: {os.path.exists(env_path)}")
print(f"ZHIHU_ACCESS_SECRET: {repr(ZHIHU_ACCESS_SECRET)}")
print(f"ZHIHU_OPENAPI_AVAILABLE: {ZHIHU_OPENAPI_AVAILABLE}")
