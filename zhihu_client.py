"""
知乎开放平台 HTTP API 极简客户端（Python）

鉴权：Authorization: Bearer <Access Secret> + X-Request-Timestamp（秒级 Unix 时间戳）
密钥来源（按优先级）：
    1. 构造函数显式传入 access_secret
    2. 环境变量 ZHIHU_ACCESS_SECRET
    3. 项目根目录 env 文件中的 ZHIHU_ACCESS_SECRET
不要把密钥硬编码进代码或提交到仓库。

用法：
    from zhihu_client import ZhihuClient
    client = ZhihuClient()
    items = client.search_zhihu("大模型 Agent", count=10)
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List, Optional

import requests

BASE = "https://developer.zhihu.com"

# 与项目现有约定保持一致：密钥存放在项目根目录的 env 文件中
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "env")


def _load_secret_from_env_file(key: str = "ZHIHU_ACCESS_SECRET") -> str:
    """从项目 env 文件读取密钥。文件缺失或无该键时返回空字符串。"""
    if not os.path.isfile(_ENV_FILE):
        return ""
    try:
        with open(_ENV_FILE, "r", encoding="utf-8") as fh:
            for raw in fh:
                line = raw.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                name, _, value = line.partition("=")
                if name.strip() == key:
                    return value.strip().strip('"').strip("'")
    except OSError:
        return ""
    return ""


class ZhihuAPIError(RuntimeError):
    """业务错误：HTTP 200 但 Code != 0，或 HTTP 层失败。"""


class ZhihuClient:
    def __init__(self, access_secret: Optional[str] = None, timeout: int = 30):
        # 优先级：显式传参 > 环境变量 > 项目 env 文件
        secret = (
            access_secret
            or os.environ.get("ZHIHU_ACCESS_SECRET", "")
            or _load_secret_from_env_file()
        )
        if not secret:
            raise ValueError(
                "缺少 Access Secret：请设置环境变量 ZHIHU_ACCESS_SECRET，"
                f"或在 {_ENV_FILE} 中配置 ZHIHU_ACCESS_SECRET=<your_secret>"
            )
        self._secret = secret
        self.timeout = timeout
        self.session = requests.Session()

    # ---------- 内部：统一请求 ----------
    def _headers(self) -> Dict[str, str]:
        # X-Request-Timestamp 必须每次请求现算，不能复用旧值
        return {
            "Authorization": f"Bearer {self._secret}",
            "X-Request-Timestamp": str(int(time.time())),
            "Content-Type": "application/json",
        }

    def _get(self, path: str, params: Dict[str, Any]) -> Dict[str, Any]:
        params = {k: v for k, v in params.items() if v is not None}
        resp = self.session.get(
            f"{BASE}{path}", params=params, headers=self._headers(), timeout=self.timeout
        )
        resp.raise_for_status()
        body = resp.json()
        # 内容/用户类接口统一包一层 Code/Message/Data
        if isinstance(body, dict) and body.get("Code") not in (0, None):
            raise ZhihuAPIError(f"Code={body.get('Code')} Message={body.get('Message')}")
        return body.get("Data", body) if isinstance(body, dict) else body

    # ---------- 公共内容 ----------
    def search_zhihu(self, query: str, count: int = 10) -> List[Dict[str, Any]]:
        """知乎站内搜索。Count 最大 10，超出服务端自动截断。"""
        data = self._get("/api/v1/content/zhihu_search", {"Query": query, "Count": count})
        return data.get("Items", [])

    def search_global(
        self,
        query: str,
        count: int = 10,
        filter_expr: Optional[str] = None,
        search_db: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """全网搜索。Count 最大 20。

        filter_expr 高级语法示例：
            'host=="example.com"'
            'host=="example.com" AND publish_time>=1778494631'
        search_db: all(默认) / realtime / static
        """
        data = self._get(
            "/api/v1/content/global_search",
            {"Query": query, "Count": count, "Filter": filter_expr, "SearchDB": search_db},
        )
        return data.get("Items", [])

    def hot_list(self, limit: int = 20) -> List[Dict[str, Any]]:
        """知乎热榜。"""
        data = self._get("/api/v1/content/hot_list", {"Limit": limit})
        return data.get("Items", [])

    def quota(self) -> Dict[str, Any]:
        """查询当前账号当日开放 API 额度。"""
        return self._get("/api/v1/quota", {})

    # ---------- 本人数据（不传 X-OAuth-Token 即为 Secret 所属账号） ----------
    def my_contents(
        self, content_type: str = "all", limit: int = 20, offset: int = 0
    ) -> Dict[str, Any]:
        """本人创作列表。返回 {'Items': [...], 'Paging': {...}}。

        Paging.IsEnd 为 False 时，用 Paging.NextOffset 取下一页。
        """
        return self._get(
            "/api/v1/user/contents",
            {"ContentType": content_type, "Limit": limit, "Offset": offset},
        )

    def my_followees(self, limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """本人关注列表。"""
        return self._get("/api/v1/user/followees", {"Limit": limit, "Offset": offset})

    def recommend_questions(
        self, count: int = 5, query: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """问题推荐。不传 query 按本人画像推荐；Count 范围 1-20。"""
        data = self._get(
            "/api/v1/user/question_recommendations", {"Count": count, "Query": query}
        )
        return data.get("Items", data) if isinstance(data, dict) else data

    # ---------- 知乎直答（OpenAI 兼容 Chat Completions） ----------
    def answer(
        self, question: str, model: str = "zhida-thinking-1p5", stream: bool = False
    ) -> str:
        """知乎直答。model 可选 zhida-fast-1p5 / zhida-thinking-1p5 / zhida-agent。

        注意：该接口走 /v1/chat/completions，返回 OpenAI 风格结构，
        不是 Code/Message/Data 包装，因此单独处理。
        """
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": question}],
            "stream": stream,
        }
        resp = self.session.post(
            f"{BASE}/v1/chat/completions",
            json=payload,
            headers=self._headers(),
            timeout=self.timeout,
        )
        resp.raise_for_status()
        body = resp.json()
        if "error" in body:
            raise ZhihuAPIError(body["error"].get("message", "unknown error"))
        return body["choices"][0]["message"]["content"]


def paginate_my_contents(client: ZhihuClient, content_type: str = "all", page_size: int = 20):
    """分页遍历本人创作，按需消费的生成器。"""
    offset = 0
    while True:
        data = client.my_contents(content_type=content_type, limit=page_size, offset=offset)
        for item in data.get("Items", []):
            yield item
        paging = data.get("Paging", {})
        if paging.get("IsEnd", True):
            return
        offset = int(paging.get("NextOffset", offset + page_size))


if __name__ == "__main__":
    client = ZhihuClient()

    print("=== 知乎搜索 ===")
    for item in client.search_zhihu("如何评价大模型 Agent", count=3):
        print(f"- {item.get('Title')} — {item.get('AuthorName')}")
        print(f"  {item.get('Url')}")

    print("\n=== 热榜 Top 5 ===")
    for item in client.hot_list(limit=5):
        print(f"- {item.get('Title')}")

    print("\n=== 我的创作（第一页） ===")
    data = client.my_contents(limit=3)
    for item in data.get("Items", []):
        print(f"- [{item.get('ContentType')}] {item.get('Title')}")
    print("Paging:", data.get("Paging"))
