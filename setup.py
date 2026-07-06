import os
import subprocess
import sys
from pathlib import Path


def run_cmd(cmd):
    subprocess.check_call(cmd, shell=True)


def write_env_template():
    env_path = Path(".env")
    if env_path.exists():
        return

    env_path.write_text(
        """# OpenAI-compatible 配置：默认先用 DeepSeek 做低成本连通性测试。
OPENAI_API_KEY=
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-v4-flash

# 后续正式使用 GPT 时，改为对应的 OpenAI-compatible 地址、Key 和模型名。
# OPENAI_BASE_URL=https://api.openai.com/v1
# OPENAI_MODEL=gpt-4o-mini

MODEL_TEMPERATURE=0.0
""",
        encoding="utf-8",
    )


if __name__ == "__main__":
    if not Path("venv").exists():
        run_cmd(f"{sys.executable} -m venv venv")

    if os.name == "nt":
        pip_path = r"venv\Scripts\pip"
    else:
        pip_path = "venv/bin/pip"

    run_cmd(
        f"{pip_path} install --index-url https://mirrors.aliyun.com/pypi/simple/ "
        "--retries 5 --timeout 60 -r requirements.txt"
    )
    run_cmd(f"{pip_path} freeze > requirements.txt")
    write_env_template()

    print("=== 环境一键搭建完成 ===")
    print(r"Windows激活：venv\Scripts\activate")
    print("Mac/Linux激活：source venv/bin/activate")
    print("请打开.env填入你的API密钥后运行测试脚本：python test_llm.py")
