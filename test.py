from zhihu_client import ZhihuClient

items = ZhihuClient().hot_list(limit=10)

for rank, item in enumerate(items, start=1):
    print(f"{rank}. {item['Title']}")
    print(f"   {item['Url']}")
