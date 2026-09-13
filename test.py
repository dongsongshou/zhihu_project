import re
def _tokenize_text(text: str):
    if not text:
        return []
    text = text.lower()
    text = text.replace("-", " ")
    tokens = re.findall(r"[a-z0-9\u4e00-\u9fff]+", text)
    return tokens
text="你好，Micale!"
print(_tokenize_text(text))
print(" ".join(_tokenize_text(text)))