"""
网关配置（macOS + evolving）
"""
import os
from dotenv import load_dotenv

load_dotenv()

GATEWAY_PORT: int = int(os.getenv("GATEWAY_PORT", "7070"))
# 可选：evolving 项目父目录，用于 sys.path（若未安装 evolving 包）
EVOLVING_PATH: str = (os.getenv("EVOLVING_PATH") or "").strip()
