import httpx, json
r = httpx.get("http://localhost:11434/api/tags", timeout=5)
data = r.json()
models = [m["name"] for m in data.get("models", [])]
print("利用可能なモデル:", models)
