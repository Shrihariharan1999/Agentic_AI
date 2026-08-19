import time
from openai import OpenAI
from app.config.settings import settings

client = OpenAI(
    base_url=settings.nvidia_base_url,
    api_key=settings.nvidia_api_key
)

MODELS = [
    "meta/llama-3.1-8b-instruct",
    "meta/llama-3.3-70b-instruct",
    "qwen/qwen2.5-coder-32b-instruct",
    "mistralai/mistral-large-2-instruct",
    "deepseek-ai/deepseek-r1",
]

prompt = "Generate a 1-step test case in JSON: {\"id\": \"TC-001\", \"action\": \"navigate\", \"target\": \"https://example.com\"}"

print(f"{'Model':<38} | {'Latency (s)':<12} | {'Output Snippet'}", flush=True)
print("-" * 80, flush=True)

for m in MODELS:
    t0 = time.perf_counter()
    try:
        completion = client.chat.completions.create(
            model=m,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=150
        )
        dur = round(time.perf_counter() - t0, 2)
        text = completion.choices[0].message.content.strip().replace("\n", " ")[:40]
        print(f"{m:<38} | {dur:<12} | {text}...", flush=True)
    except Exception as e:
        dur = round(time.perf_counter() - t0, 2)
        print(f"{m:<38} | {dur:<12} | ERROR: {str(e)[:40]}", flush=True)
