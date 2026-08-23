import os
from dotenv import load_dotenv

load_dotenv()

# 知乎API配置
ZHIHU_AGENT_BASE_URL = os.getenv("ZHIHU_AGENT_BASE_URL", "https://api.zhihu.com/v1")
ZHIHU_AGENT_API_KEY = os.getenv("ZHIHU_AGENT_API_KEY", "")

# 演示模式自动判断
DEMO_MODE = len(ZHIHU_AGENT_API_KEY.strip()) == 0
CACHE_TTL = 3600

# 系统全局参数
VECTOR_DIM = 8
CLUSTER_NUM = 3
