import os
from pathlib import Path
from fastmcp import FastMCP
from pydantic import Field
import threading
from fastapi import FastAPI
from fastapi.responses import FileResponse
import uvicorn
from typing import Dict, Any
import subprocess
from src.gen_result import gen_result
import warnings
import os
import subprocess
import uuid


# ---------------- FastAPI File Server ----------------

DOWNLOAD_DIR = "download"
fastapi_app = FastAPI()

@fastapi_app.get("/download/{user_dir}/{filename}")
async def download_file(user_dir: str, filename: str):
    file_path = os.path.join(DOWNLOAD_DIR, user_dir, filename)
    if not os.path.exists(file_path):
        return {"error": "File not found"}
    return FileResponse(path=file_path, filename=filename)



def clone_or_update_repo(repo_url, branch="main", clone_dir="/tmp/mcp_repo"):
    """
    克隆或更新仓库。如果指定分支不存在，则返回错误信息并列出所有分支。
    """

    # Step 1: 如果不存在则 clone --no-checkout（避免直接 checkout 失败）
    if not os.path.exists(clone_dir):
        print(f"Cloning repository into {clone_dir} (no checkout)...")
        subprocess.run(
            ["git", "clone", "--no-checkout", repo_url, clone_dir],
            check=True
        )

    # Step 2: 更新远程信息
    subprocess.run(
        ["git", "-C", clone_dir, "fetch", "--all"],
        check=True
    )

    # Step 3: 检查分支是否存在
    result = subprocess.run(
        ["git", "-C", clone_dir, "branch", "-a"],
        capture_output=True,
        text=True
    )
    branch_list = result.stdout.splitlines()

    # Git 可能显示为 remotes/origin/xxx
    normalized = [b.strip().replace("remotes/origin/", "") for b in branch_list]

    if branch not in normalized:
        return {
            "success": False,
            "error": f"Branch '{branch}' does not exist.",
            "available_branches": sorted(set(normalized))
        }

    # Step 4: checkout
    subprocess.run(
        ["git", "-C", clone_dir, "checkout", branch],
        check=True
    )
    subprocess.run(
        ["git", "-C", clone_dir, "pull"],
        check=True
    )

    return {
        "success": True,
        "repo_path": clone_dir
    }

def get_cfile_from_repo(repo_path, relative_path):
    """
    从本地仓库读取文件内容
    """
    file_path = os.path.join(repo_path, relative_path.lstrip("/"))
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found in local repo: {file_path}")

    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


warnings.filterwarnings("ignore", category=DeprecationWarning)

# MCP 初始化
app = FastMCP(
    "ArchSync",
    instructions="跨架构代码同步：输入文件内容, 返回生成结果。"
)

# 后端 ArchSync 服务地址
ARCHSYNC_IMAGE = os.environ.get("ARCHSYNC_IMAGE", "archsync:latest")

@app.tool()
def generate_riscv_code(
    gitUrl: str = Field(..., description="Git 仓库地址"),
    old_other_arch: str = Field(..., description="更新前的源文件名(通常是除了RISC-V外的其他架构)"),
    old_riscv: str = Field(..., description="更新前的目标文件名(通常是RISC-V架构)"),
    new_other_arch: str = Field(..., description="更新后的源文件名(通常是除了RISC-V外的其他架构)"),
    branch: str = Field("rvpt-branch", description="分支(可选)"),
    new_riscv: str = Field("output.cc", description="输出文件名(可选)")
) -> Dict[str, Any]:
    """
    跨架构代码变更同步

    功能: 根据提供的其他架构更新前的文件, 更新后的文件和RISC-V架构更新前代码文件, 生成对应的RISC-V架构更新后的代码文件
    - 实现自动的跨架构的更新同步
    - 支持从多种架构代码的生成
    - 自动生成架构兼容的代码

    使用场景:
    - 从其他架构代码变更生成RISC-V代码变更
    - 用户说“同步变更到”

    参数说明:
    - old_other_arch: 更新前的源文件名(通常是除了RISC-V外的其他架构)
    - old_riscv: 更新前的目标文件名(通常是RISC-V架构)
    - new_other_arch: 更新后的源文件名(通常是除了RISC-V外的其他架构)
    - new_riscv: 输出文件名(通常是RISC-V架构, 如果用户在请求中指定路径或文件名, 必须使用该值)

    返回: 生成的RISC-V代码内容
    
    注意: 这是独立工具, 执行后直接返回完整结果, 无需调用其他工具。
    """


    if new_riscv is None:
        new_riscv = "output.cc"
    print(f"Generating RISC-V code: {new_riscv}")
    # --- 读取文件 ---
    try:
        
        # 克隆整个仓库
        repo_info = clone_or_update_repo(gitUrl, branch)

        if not repo_info["success"]:
            return repo_info  # MCP 会直接返回错误和所有分支列表

        local_repo = repo_info["repo_path"]
        # 读取文件
        cfile1 = get_cfile_from_repo(local_repo, old_other_arch)
        cfile2 = get_cfile_from_repo(local_repo, old_riscv)
        cfile1_ = get_cfile_from_repo(local_repo, new_other_arch)

        
        print("Input files retrieved successfully.")
        result = gen_result(
                file_string1=cfile1,
                file_string2=cfile2,
                file_string1_=cfile1_,
                mapping_dic={},
                use_docker=False,
                MATCHER_ID='gumtree-simple',
                TREE_GENERATOR_ID='cpp-srcml'
            )
        print("RISC-V code generated successfully.")
        # 如果没有 user_id，则生成随机目录
        user_dir = str(uuid.uuid4())
        download_dir = Path(DOWNLOAD_DIR) / user_dir
        download_dir.mkdir(parents=True, exist_ok=True)

        output_path = download_dir / new_riscv


        with open(output_path, "w") as f:
            f.write(result)

        download_url = f"http://{os.getenv('SERVER_IP', 'localhost')}:8012/download/{user_dir}/{new_riscv}"


        return {
            "success": True,
            "filename": new_riscv,
            "url": download_url,          # ⭐ 加上这个
            "message": "RISC-V 代码已生成"
        }

    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

def start_fastapi():
    uvicorn.run(fastapi_app, host="0.0.0.0", port=8012)


if __name__ == "__main__":

    # 启动 FastAPI 后台线程
    threading.Thread(target=start_fastapi, daemon=True).start()

    # 启动 MCP
    MCP_PORT = int(os.getenv("MCP_PORT", "8013"))
    MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "http")

    if MCP_TRANSPORT == "stdio":
        app.run()
    else:
        app.run(transport="http", host="0.0.0.0", port=MCP_PORT)

