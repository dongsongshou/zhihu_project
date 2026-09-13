import requests
import time

ZHIHU_ACCESS_SECRET = "be85c5ce20f6a9dc1642d180cf08496420727e20"

url = "https://developer.zhihu.com/api/v1/content/zhihu_search"
ts = int(time.time())
headers = {
    "Authorization": f"Bearer {ZHIHU_ACCESS_SECRET}",
    "X-Request-Timestamp": str(ts),
    "Content-Type": "application/json"
}
params = {
    "Query": "人工智能",
    "Count": 5
}

resp = requests.get(url, headers=headers, params=params, timeout=12)
print("status_code:", resp.status_code)
print("resp text:", resp.text)
