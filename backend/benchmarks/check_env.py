"""检查环境变量"""
from dotenv import load_dotenv
import os
load_dotenv(".env")
print("VLLM_ENABLED:", os.getenv("VLLM_ENABLED"))
print("VLLM_BASE_URLS:", os.getenv("VLLM_BASE_URLS"))
print("VLLM_MODEL:", os.getenv("VLLM_MODEL"))
print("USE_POSTGRESQL:", os.getenv("USE_POSTGRESQL"))
