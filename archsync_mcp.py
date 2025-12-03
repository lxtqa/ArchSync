import os
from pathlib import Path
from fastmcp import FastMCP
from pydantic import Field
from typing import Dict, Any, Optional
import requests

# MCP 初始化
app = FastMCP(
    "ArchSync",
    instructions="跨架构代码同步：输入文件内容，返回生成结果。"
)

# 后端 ArchSync 服务地址
ARCHSYNC_BACKEND = os.getenv("BACKEND", "http://archsync:8012")


def call_archsync_api(
    old_other_arch_content: str,
    old_riscv_content: str,
    new_other_arch_content: str,
    output_filename: str
) -> Dict[str, Any]:
    """
    调用 archsync 后端 API，不使用 docker，不访问本地文件
    """

    payload = {
        "old_other_arch": old_other_arch_content,
        "old_riscv": old_riscv_content,
        "new_other_arch": new_other_arch_content,
        "output_file": output_filename
    }

    try:
        url = f"{ARCHSYNC_BACKEND}/gen_result"
        resp = requests.post(url, json=payload, timeout=300)

        if resp.status_code != 200:
            return {
                "success": False,
                "error": f"HTTP {resp.status_code}",
                "output": resp.text
            }

        return resp.json()

    except requests.Timeout:
        return {
            "success": False,
            "error": "请求 archsync 超时（300秒）"
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


def _read_file_content(path: str) -> Optional[str]:
    """读取用户本地上传的文件内容"""
    try:
        p = Path(path)
        if not p.exists():
            return None
        return p.read_text(encoding="utf-8")
    except:
        return None


@app.tool()
def generate_riscv_code(
    old_other_arch: str = Field(..., description="旧架构源文件路径"),
    old_riscv: str = Field(..., description="旧 RISC-V 文件路径"),
    new_other_arch: str = Field(..., description="新架构源文件路径"),
    new_riscv: Optional[str] = Field(None, description="生成结果文件名")
) -> Dict[str, Any]:

    old_src = _read_file_content(old_other_arch)
    if old_src is None:
        return {"success": False, "error": f"文件不存在: {old_other_arch}"}

    old_riscv_src = _read_file_content(old_riscv)
    if old_riscv_src is None:
        return {"success": False, "error": f"文件不存在: {old_riscv}"}

    new_src = _read_file_content(new_other_arch)
    if new_src is None:
        return {"success": False, "error": f"文件不存在: {new_other_arch}"}

    if new_riscv is None:
        new_riscv = "output.cc"

    # 调用后端服务
    return call_archsync_api(
        old_other_arch_content=old_src,
        old_riscv_content=old_riscv_src,
        new_other_arch_content=new_src,
        output_filename=new_riscv
    )


if __name__ == "__main__":
    MCP_PORT = int(os.getenv("MCP_PORT", "8012"))
    MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "http")

    if MCP_TRANSPORT == "stdio":
        app.run()
    else:
        app.run(transport="http", host="0.0.0.0", port=MCP_PORT)
