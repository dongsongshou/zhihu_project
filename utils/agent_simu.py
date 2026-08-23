# utils/agent_simu.py
from openai import OpenAI
from .config import ZHIHU_AGENT_API_KEY, ZHIHU_AGENT_BASE_URL, DEMO_MODE

MOCK_DIALOG = [
    {"role":"A","content":"我认为AI工具是很好的辅助，但是思考还是要靠人自己。"},
    {"role":"B","content":"同意。不过我觉得很多重复性分析工作交给AI可以释放大量精力。"},
    {"role":"A","content":"是的，但是我们也要警惕完全依赖模型带来思维惰性。"},
    {"role":"B","content":"这点我很认同，工具边界需要使用者清醒把握。"}
]

def simulate_agent_chat(userA, userB, tolerance=0.7):
    """两个用户数字分身对话仿真"""
    if DEMO_MODE:
        return MOCK_DIALOG

    client = OpenAI(base_url=ZHIHU_AGENT_BASE_URL, api_key=ZHIHU_AGENT_API_KEY)

    sys_prompt = f"""
你将模拟两位知乎用户A与B进行一轮简短对话。
用户A画像：{userA}
用户B画像：{userB}
沟通包容度系数：{tolerance}，越高越克制理性。
输出对话列表，每条格式{{"role":"A/B","content":"发言"}}，输出JSON数组。
不要多余文字。
"""
    resp = client.chat.completions.create(
        model="zhihu-direct-agent",
        messages=[{"role":"system","content":sys_prompt}],
        temperature=0.6
    )
    import json
    return json.loads(resp.choices[0].message.content)
