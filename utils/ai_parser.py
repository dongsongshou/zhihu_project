# utils/ai_parser.py
from openai import OpenAI
from .config import ZHIHU_AGENT_API_KEY, ZHIHU_AGENT_BASE_URL, DEMO_MODE
import json

MOCK_PARSE_RESULT = {
    "domains": ["高等教育", "人工智能", "网络社区文化"],
    "stance": "偏向理性中立，重视思辨与实践价值",
    "style": "理性说理，注重逻辑，语言克制",
    "risk_topics": ["极端立场争论", "情绪化站队话题"],
    "embedding": [0.12, 0.21, -0.05, 0.33, 0.41, -0.22, 0.18, 0.09]
}

def parse_user_view(answer_texts: list[str]):
    """AI解析用户观点画像 + 简易观点向量"""
    if DEMO_MODE:
        return MOCK_PARSE_RESULT

    # 仅非演示模式才实例化客户端
    client = OpenAI(base_url=ZHIHU_AGENT_BASE_URL, api_key=ZHIHU_AGENT_API_KEY)

    prompt = f"""
基于下面用户多条知乎回答文本，输出JSON格式结果：
{{
"domains": list[str], 关注知识领域；
"stance": str,核心立场概括；
"style": str,表达风格；
"risk_topics": list[str],容易引发冲突话题；
"embedding": list[float],8维浮点数观点向量；
}}
回答文本：
{chr(10).join(answer_texts)}
只返回JSON，不要多余解释。
"""
    completion = client.chat.completions.create(
        model="zhihu-direct-agent",
        messages=[{"role":"user","content":prompt}],
        temperature=0.3
    )
    raw = completion.choices[0].message.content
    return json.loads(raw)
