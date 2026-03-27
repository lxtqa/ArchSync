import os
from pathlib import Path
from fastmcp import FastMCP
from pydantic import Field
import threading
from fastapi import FastAPI
from fastapi.responses import FileResponse
import uvicorn
from typing import Dict, Any
from src.gen_result import gen_result
import warnings
import os
import uuid
from src.find_commit import find_commit
from git import Repo, GitCommandError
from src.utils.arch_utils import is_file_para

# ---------------- FastAPI File Server ----------------

DOWNLOAD_DIR = "download"
fastapi_app = FastAPI()

# 正式服务器下载路径
# @fastapi_app.get("/downloadArchsyncResult/{user_dir}/{filename}")
# 测试服务器下载路径
@fastapi_app.get("/download/{user_dir}/{filename}")
async def download_file(user_dir: str, filename: str):
    file_path = os.path.join(DOWNLOAD_DIR, user_dir, filename)
    if not os.path.exists(file_path):
        return {"error": "File not found"}
    return FileResponse(path=file_path, filename=filename)

def read_file_content(file_path):
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()

def clone_or_update_repo(repo_url, clone_dir=None):
    """
    克隆或更新仓库(GitPython 版本）
    """
    if not os.path.exists(clone_dir):
        # print(f"Cloning repository into {clone_dir} ...")
        try:
            repo = Repo.clone_from(repo_url, clone_dir)
        except GitCommandError as e:
            return {"success": False, "error": str(e)}
    else:
        repo = Repo(clone_dir)

    # 更新远程
    try:
        repo.remotes.origin.fetch()
    except GitCommandError as e:
        return {"success": False, "error": f"fetch failed: {e}"}

    return {"success": True, "repo_path": clone_dir}

def get_cfile_before_commit(repo_path, relative_path, commit_id):
    """
    读取某个 commit 发生【之前】的文件内容
    等价于：读取 commit.parent 中该文件的内容
    """
    repo = Repo(repo_path)
    relative_path = relative_path.lstrip("/")

    try:
        commit = repo.commit(commit_id)
    except Exception:
        raise ValueError(f"Invalid commit id: {commit_id}")

    # 没有 parent，说明是 root commit
    if not commit.parents:
        raise FileNotFoundError(f"Commit {commit_id} has no parent, no 'before' version")

    parent = commit.parents[0]

    try:
        blob = parent.tree[relative_path]
        return blob.data_stream.read().decode()
    except KeyError:
        raise FileNotFoundError(
            f"File not found before commit {commit_id}: {relative_path}"
        )


def get_cfile_from_repo(repo_path, relative_path, commit_id=None):
    """
    使用 GitPython 从 repo 中读取文件内容
    - commit_id = None → 读取 working tree 文件
    - commit_id != None → 读取该 commit 中的文件内容
    """
    repo = Repo(repo_path)
    relative_path = relative_path.lstrip("/")

    if commit_id is None:
        file_path = os.path.join(repo_path, relative_path)
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found in repo: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    else:
    # 读取 commit 内容
        try:
            commit = repo.commit(commit_id)
            blob = commit.tree[relative_path]
            return blob.data_stream.read().decode()
        except KeyError:
            raise FileNotFoundError(f"File not found at commit {commit_id}: {relative_path}")
    

def build_history_datas(repo_path, des_arch_file, max_commits=3):
    """
    对每个镜像文件：

    - 从最新版开始
    - 一直向过去取该文件的历史版本
    - 直到：
        - 取不到更旧的
        - 或者数量达到 max_commits + 1
    - 切片顺序：新 -> 旧
    """
    repo = Repo(repo_path)
    history_datas = {}

    des_arch_file = des_arch_file.lstrip("/")

    for root, dirs, files in os.walk(repo_path):
        for fname in files:
            abs_path = os.path.join(root, fname)
            rel_path = os.path.relpath(abs_path, repo_path).replace("\\", "/")

            if not is_file_para(des_arch_file, rel_path) or rel_path == des_arch_file:
                continue

            slices = []

            # Git 会自动只返回“这个文件存在的 commit”
            commits = repo.iter_commits(paths=rel_path)

            for c in commits:
                try:
                    content = get_cfile_from_repo(repo_path, rel_path, c.hexsha)
                except:
                    break  # 理论上不该发生，但安全起见：断掉

                slices.append({
                    "commit_id": c.hexsha,
                    "content": content,
                    "commit_info": c.message.strip()
                })

                # 达到上限就停
                if len(slices) >= max_commits + 1:
                    break

            if slices:
                history_datas[rel_path] = slices

    return history_datas


warnings.filterwarnings("ignore", category=DeprecationWarning)

# MCP 初始化
app = FastMCP(
    "ArchSync",
    instructions="跨架构代码同步：输入文件内容, 返回生成结果。"
    instructions="跨架构代码同步：输入文件内容, 返回生成结果。"
)

# 后端 ArchSync 服务地址
ARCHSYNC_IMAGE = os.environ.get("ARCHSYNC_IMAGE", "archsync:latest")


@app.tool()
def get_unsync_info(
        gitUrl: str = Field(..., description="Git 仓库地址"),
        des_arch: str = Field(..., description="待更新文件名(通常是RISC-V架构)"),
        max_check_num: int = Field(3, description="镜像文件的最大检查commit数量(可选)")
)-> Dict[str, Any]:
    """
    获取未同步的跨架构代码变更信息

    功能: 根据提供的 Git 仓库地址、分支和文件路径, 获取该分支上未同步的跨架构代码变更信息
    - 实现自动的跨架构的更新同步
    - 支持从多种架构代码的生成
    - 自动生成架构兼容的代码

    使用场景:
    - 检查跨架构代码变更状态
    - 用户说“检查未同步的变更”

    参数说明:
    - gitUrl: Git 仓库地址
    - des_arch: 待更新文件名(通常是RISC-V架构)
    - max_check_num: 镜像文件的最大检查commit数量(可选)

    返回: 未同步的跨架构代码变更信息,以{文件名, commit_id}形式返回

    注意: 不要读取文件内容, 直接交给工具处理, 执行后直接返回完整结果, 无需调用其他工具。
    """
    print("Running get_unsync_info...",flush=True)
    try:
        user_dir = str(uuid.uuid4())
        ret = clone_or_update_repo(gitUrl, clone_dir=os.path.join("/tmp/", user_dir))
        if not ret["success"]:
            return ret

        repo_path = ret["repo_path"]
        history_datas = build_history_datas(
            repo_path,
            des_arch_file=des_arch,
            max_commits=max_check_num
        )

        file_content = read_file_content(os.path.join(repo_path, des_arch))
        unsynced_commits = find_commit(
            des_arch,
            file_content,
            history_datas
        )

        return {
            "success": True,
            "unsynced_info": str(unsynced_commits)
        }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.tool()
def generate_riscv_code_with_commit_id(
    gitUrl: str = Field(..., description="Git 仓库地址"),
    src_arch: str = Field(..., description="源文件名(通常是除了RISC-V外的其他架构, 此时源文件已经发生了更新)"),
    des_arch: str = Field(..., description="目标文件名(通常是RISC-V架构, 此时RISC-V文件还未更新)"),
    commit_id: str = Field(..., description="更新源文件的commit id"),
    output: str = Field("output.cc", description="输出文件名(可选)")
) -> Dict[str, Any]:
    """
    跨架构代码共变更推荐

    功能: 根据提供的其他架构更新后的源文件, 更新源文件的commit id和RISC-V架构的目标代码文件, 生成对应的RISC-V架构更新后的代码文件
    - 实现自动的跨架构的更新同步
    - 支持从多种架构代码的生成
    - 自动生成架构兼容的代码

    使用场景:
    - 从其他架构代码变更生成RISC-V代码共变更
    - 用户说“变更”

    参数说明:
    - src_arch: 源文件名(通常是除了RISC-V外的其他架构, 此时源文件已经发生了更新)
    - des_arch: 目标文件名(通常是RISC-V架构, 此时RISC-V文件还未更新)
    - commit_id: 更新源文件的commit id
    - output: 输出文件名(通常是RISC-V架构, 如果用户在请求中指定路径或文件名, 必须使用该值)

    返回: 生成的RISC-V代码文件的下载地址
    
    注意: 不要读取文件内容, 直接交给工具处理, 执行后直接返回完整结果, 无需调用其他工具, **下载时不要覆盖原来的代码**。
    """

    print("Running generate_riscv_code_with_commit_id...",flush=True)
    # --- 读取文件 ---
    try:
        user_dir = str(uuid.uuid4())
        # 克隆整个仓库
        repo_info = clone_or_update_repo(gitUrl, clone_dir=os.path.join("/tmp/", user_dir))

        if not repo_info["success"]:
            return repo_info  # MCP 会直接返回错误和所有分支列表

        local_repo = repo_info["repo_path"]
        # 读取文件
        cfile1 = get_cfile_before_commit(local_repo, src_arch, commit_id)
        cfile2 = get_cfile_from_repo(local_repo, des_arch)
        cfile1_ = get_cfile_from_repo(local_repo, src_arch)

        
        # print("Input files retrieved successfully.")
        result = gen_result(
                file_string1=cfile1,
                file_string2=cfile2,
                file_string1_=cfile1_,
                use_docker=False,
                MATCHER_ID='gumtree-simple',
                TREE_GENERATOR_ID='cpp-srcml'
            )
        # print("RISC-V code generated successfully.")
        # 如果没有 user_id，则生成随机目录
        download_dir = Path(DOWNLOAD_DIR) / user_dir
        download_dir.mkdir(parents=True, exist_ok=True)

        output_path = download_dir / output


        with open(output_path, "w") as f:
            f.write(result)

        # 正式服务器使用 GATEWAY_BASE
        # GATEWAY_BASE = os.getenv("GATEWAY_BASE", "https://gateway.rvpt.top")
        # download_url = f"{GATEWAY_BASE}/downloadArchsyncResult/{user_dir}/{output}"
        
        # 测试服务器使用 SERVER_IP
        download_url = f"http://{os.getenv('SERVER_IP', 'localhost')}:8012/download/{user_dir}/{output}"

        return {
            "success": True,
            "filename": output,
            "url": download_url,
            "message": "RISC-V 代码已生成"
        }


    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }


@app.tool()
def generate_riscv_code(
    gitUrl: str = Field(..., description="Git 仓库地址"),
    old_src_arch: str = Field(..., description="更新前的源文件名(通常是除了RISC-V外的其他架构)"),
    old_des_arch: str = Field(..., description="更新前的目标文件名(通常是RISC-V架构)"),
    new_src_arch: str = Field(..., description="更新后的源文件名(通常是除了RISC-V外的其他架构)"),
    output: str = Field("output.cc", description="输出文件名(可选)")
) -> Dict[str, Any]:
    """
    跨架构代码变更共变更推荐

    功能: 根据提供的其他架构更新前的文件, 更新后的文件和RISC-V架构更新前代码文件, 生成对应的RISC-V架构更新后的代码文件
    - 实现自动的跨架构的更新同步
    - 支持从多种架构代码的生成
    - 自动生成架构兼容的代码

    使用场景:
    - 从其他架构代码变更生成RISC-V代码变更
    - 用户说“同步”

    参数说明:
    - old_src_arch: 更新前的源文件名(通常是除了RISC-V外的其他架构)
    - old_des_arch: 更新前的目标文件名(通常是RISC-V架构)
    - new_src_arch: 更新后的源文件名(通常是除了RISC-V外的其他架构)
    - output: 输出文件名(通常是RISC-V架构, 如果用户在请求中指定路径或文件名, 必须使用该值)

    返回: 生成的RISC-V代码文件的下载地址
    
    注意: 不要读取文件内容, 直接交给工具处理, 执行后直接返回完整结果, 无需调用其他工具,  **下载时不要覆盖原来的代码**。
    """


    print("Running generate_riscv_code...",flush=True)
    # --- 读取文件 ---
    try:
        user_dir = str(uuid.uuid4())
        # 克隆整个仓库
        repo_info = clone_or_update_repo(gitUrl, clone_dir=os.path.join("/tmp/", str(uuid.uuid4())))
        # print("Getting input files.",flush=True)
        if not repo_info["success"]:
            return repo_info  # MCP 会直接返回错误和所有分支列表

        local_repo = repo_info["repo_path"]
        # 读取文件
        cfile1 = get_cfile_from_repo(local_repo, old_src_arch)
        cfile2 = get_cfile_from_repo(local_repo, old_des_arch)
        cfile1_ = get_cfile_from_repo(local_repo, new_src_arch)

        
        # print("Input files retrieved successfully.",flush=True)
        result = gen_result(
                file_string1=cfile1,
                file_string2=cfile2,
                file_string1_=cfile1_,
                mapping_dic={},
                use_docker=False,
                MATCHER_ID='gumtree-simple',
                TREE_GENERATOR_ID='cpp-srcml'
            )
        # print("RISC-V code generated successfully.")
        # 如果没有 user_id，则生成随机目录
        download_dir = Path(DOWNLOAD_DIR) / user_dir
        download_dir.mkdir(parents=True, exist_ok=True)

        output_path = download_dir / output


        with open(output_path, "w") as f:
            f.write(result)

        # 正式服务器使用 GATEWAY_BASE
        # GATEWAY_BASE = os.getenv("GATEWAY_BASE", "https://gateway.rvpt.top")
        # download_url = f"{GATEWAY_BASE}/downloadArchsyncResult/{user_dir}/{output}"

        # 测试服务器使用 SERVER_IP
        download_url = f"http://{os.getenv('SERVER_IP', 'localhost')}:8012/download/{user_dir}/{output}"

        return {
            "success": True,
            "filename": output,
            "url": download_url,
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

    # 启动 FastAPI 后台线程
    threading.Thread(target=start_fastapi, daemon=True).start()

    # 启动 MCP
    MCP_PORT = int(os.getenv("MCP_PORT", "8013"))
    MCP_TRANSPORT = os.getenv("MCP_TRANSPORT", "http")

    if MCP_TRANSPORT == "stdio":
        app.run()
    else:
        app.run(transport="http", host="0.0.0.0", port=MCP_PORT)


