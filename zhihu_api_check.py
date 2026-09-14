"""知乎热榜获取示例。

热榜接口每日额度仅 100 次，注意节约调用。
密钥由 zhihu_client 自动从项目 env 文件读取，无需硬编码。
"""

from zhihu_client import ZhihuClient

# limit 控制返回条数
items = ZhihuClient().hot_list(limit=10)

print(f"知乎热榜 Top {len(items)}\n")
for rank, item in enumerate(items, start=1):
    print(f"{rank}. {item['Title']}")
    print(f"   {item['Url']}")

    # Summary 为热榜摘要，部分条目可能为空
    summary = (item.get("Summary") or "").strip()
    if summary:
        print(f"   摘要：{summary[:80]}...")
    print()
