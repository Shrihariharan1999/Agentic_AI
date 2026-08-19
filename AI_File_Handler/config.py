import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

# Load variables from .env
load_dotenv()

# Read API key
NVIDIA_API_KEY = os.getenv("NVIDIA_API_KEY")

# Validate API key
if not NVIDIA_API_KEY:
    raise ValueError(
        "NVIDIA_API_KEY not found. Please check your .env file."
    )

# Create LLM
llm = ChatOpenAI(
    base_url="https://integrate.api.nvidia.com/v1",
    api_key=NVIDIA_API_KEY,
    model="nvidia/llama-3.3-nemotron-super-49b-v1.5",
    temperature=0.3,
    streaming=True
)