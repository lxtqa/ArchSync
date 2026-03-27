from git import Repo, GitCommandError
import os
import re
import subprocess
import tempfile

def format(code: str, cwd=".") -> str:
    p = subprocess.run(
        [
            "clang-format",
            "-style=file",
            "-assume-filename=mirror.cpp",
        ],
        cwd=cwd,
        input=code,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return p.stdout


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
        return None

def modify_file_hex(file_name,reverse = False):
    if not reverse:
        try:
            with open(file_name,"r") as f:
                file = f.read()
                file = modify_hex(file)
            with open(file_name,"w") as f:
                f.write(file)
        except:
            pass
    else:
        #TODO:reverse back
        pass


def imply_patch(original_code: str, patch_text: str) -> str:
    with tempfile.TemporaryDirectory() as tmpdir:
        src_path = os.path.join(tmpdir, "file.c")
        patch_path = os.path.join(tmpdir, "change.patch")

        with open(src_path, "w", encoding="utf-8") as f:
            f.write(original_code)

        with open(patch_path, "w", encoding="utf-8") as f:
            f.write(patch_text)

        # 在临时目录执行 patch
        p = subprocess.Popen(
            ["patch", "-u", src_path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=tmpdir
        )

        out, err = p.communicate(input=patch_text.encode())

        if p.returncode != 0:
            raise ValueError(f"Patch application failed:\n{err.decode()}\n{out.decode()}")

        with open(src_path, "r", encoding="utf-8") as f:
            return f.read()

def modify_hex(cpp_code):
    pattern = r'0x[0-9a-fA-F]+(\'[0-9a-fA-F]+)*'
    replacer = lambda match: match.group().replace("'", '')
    processed_code = re.sub(pattern, replacer, cpp_code)
    return processed_code

def remove_whitespace(input_string):
    return re.sub(r"(?<!\\)\\(?!\\)", "",re.sub(r'\s+', '', input_string))

def remove_cpp_comments(file_content):
    pattern = r'//.*?$|/\*.*?\*/'
    cleaned_content = re.sub(pattern, '', file_content, flags=re.DOTALL | re.MULTILINE)
    return cleaned_content


from git import Repo, GitCommandError

def get_commit_date(repo_path: str, commit_id: str) -> str:
    """
    获取指定 commit 的提交日期，返回 YYYY-MM-DD 格式字符串
    """
    repo = Repo(repo_path)
    try:
        commit = repo.commit(commit_id)
    except (ValueError, GitCommandError):
        raise ValueError(f"Invalid commit id: {commit_id}")
    
    # commit.committed_datetime 是 datetime 对象，带时区
    date_str = commit.committed_datetime.strftime("%Y-%m-%d")
    return date_str