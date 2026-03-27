from src.utils.ast_utils import gumtree_parser, parse_tree_from_text, bfs_search_father, bfs_search, merge_lines
import subprocess
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor, as_completed
import os

MATCHER_ID = "gumtree-simple"
TREE_GENERATOR_ID = "cpp-srcml"

def run_gumtree(fa, fb, instruction="textdiff"):
    # gumtree = os.path.join(os.environ["ISAgumtree"], "bin", "gumtree")

    return subprocess.run(
        ["gumtree", instruction, fa, fb, "-m", MATCHER_ID, "-g", TREE_GENERATOR_ID],
        capture_output=True,
        text=True
    ).stdout

def get_ast(cpp_file_name):
    # gumtree = os.path.join(os.environ["ISAgumtree"], "bin", "gumtree")
    output = subprocess.run(["gumtree","parse",cpp_file_name,"-g",TREE_GENERATOR_ID],capture_output=True,text = True)
    tree_text = output.stdout.split("\n")
    root = parse_tree_from_text(merge_lines(tree_text))
    return root,len(merge_lines(tree_text))

def is_to_sync(file1,file1_,file2):
    with tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cpp') as cfile1, \
        tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cpp') as cfile1_, \
        tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cpp') as cfile2:

        cfile1.write(file1)
        cfile1.flush()
        cfile1_.write(file1_)
        cfile1_.flush()
        cfile2.write(file2)
        cfile2.flush()

        with ThreadPoolExecutor(max_workers=5) as pool:
            # 并行提交 AST 解析
            f_ast1_ = pool.submit(get_ast, cfile1_.name)
            f_ast2  = pool.submit(get_ast, cfile2.name)

            # 并行提交 gumtree diff
            f11_ = pool.submit(run_gumtree, cfile1.name,  cfile1_.name)
            f12  = pool.submit(run_gumtree, cfile1.name,  cfile2.name, "textmatch")
            f1_2 = pool.submit(run_gumtree, cfile1_.name, cfile2.name, "textmatch")

            # 等待 AST 结果
            ast1_, _ = f_ast1_.result()
            ast2, _  = f_ast2.result()

            # 等待 diff 结果
            output11_ = f11_.result()
            output12  = f12.result()
            output1_2 = f1_2.result()

    matches11_, diffs11_ = gumtree_parser(output11_)
    matches12, _ = gumtree_parser(output12)
    matches1_2, _ = gumtree_parser(output1_2)
    #parse match
    match_dic12 = {}
    for match in matches12:
        node = re.search(r"(.* \[\d+,\d+\])\n(.* \[\d+,\d+\])","\n".join(match[2:]),re.DOTALL)
        match_dic12[node[1]] = node[2]
    match_dic11_ = {}
    for match in matches11_:
        node = re.search(r"(.* \[\d+,\d+\])\n(.* \[\d+,\d+\])","\n".join(match[2:]),re.DOTALL)
        match_dic11_[node[1]] = node[2]
    match_dic1_2 = {}
    for match in matches1_2:
        node = re.search(r"(.* \[\d+,\d+\])\n(.* \[\d+,\d+\])","\n".join(match[2:]),re.DOTALL)
        match_dic1_2[node[1]] = node[2]

    to_sync = 0
    total = 0
    for diff in diffs11_:
        if diff[0] == "insert-node" or diff[0] == "insert-tree":
            source = diff[2].strip()
            des_node = diff[-2].strip()
            if des_node in match_dic12.keys():
                total += 1
                if source not in match_dic1_2.keys():
                    to_sync += 1
            continue
        elif diff[0] == "delete-node" or diff[0] == "delete-tree":
            des_node = diff[2].strip()
            total += 1
            if des_node in match_dic12.keys():
                to_sync += 1
                continue
        elif diff[0] == "update-node":
            node = re.search(r"(.*: (.*) \[\d+,\d+\])\nreplace \2 by (.*)","\n".join(diff[2:]),re.DOTALL)
            if node == None:
                node = re.search(r"(.* \[\d+,\d+\])\nreplace (.*) by (.*)","\n".join(diff[2:]),re.DOTALL)
            if node[1] in match_dic12.keys():
                total += 1
                if node[3] != match_dic12[node[1]].split(" ")[1]:
                    to_sync += 1
                    continue
        elif diff[0] == "move-node" or diff[0] == "move-tree":
            source = diff[2].strip()
            des_node = diff[-2].strip()
            if des_node in match_dic12.keys() and source in match_dic12.keys():
                total += 1
                father2 = bfs_search_father(ast2, match_dic12[source])
                if father2.value != match_dic12[des_node]:
                    to_sync += 1
                    continue
                else:
                    child_lst2 = []
                    for child in father2.children:
                        if child.value in match_dic12.values():
                            child_lst2.append(child.value)
                    child_lst1_ = []
                    father1_ = bfs_search(ast1_,match_dic11_[des_node])
                    for child in father1_.children:
                        if child.value in match_dic1_2.keys():
                            child_lst1_.append(match_dic1_2[child.value])
                    if set(child_lst2) != set(child_lst1_):
                        to_sync += 1
                        continue
    return to_sync / total if total > 0 else 0

# ==========================================================
# 数据结构说明：
# 1. mirror_files_map: Dict
#    格式：{"源文件路径": ["镜像文件1路径", "镜像文件2路径", ...]}
# 2. commits_history: List[Dict]
#    格式：[
#           {"commit_id": "sha1", "content": "新版本内容", "parent_content": "旧版本内容"},
#           {"commit_id": "sha2", "content": "...", "parent_content": "..."},
#           ... (按时间倒序排列，第一个是最新的)
#         ]
# ==========================================================
def analyze_one_mirror(mirror_path, history_data, target_file, code):
    """
    单个 mirror 的分析任务（给线程池用）
    """
    # 至少需要 2 个 commit
    if len(history_data) < 2:
        return None

    candidates = []

    for i in range(len(history_data) - 1):
        new_commit = history_data[i]
        old_commit = history_data[i + 1]
        score = is_to_sync(
            old_commit["content"],   # 旧版本
            new_commit["content"],   # 新版本
            code                     # 目标文件
        )

        candidates.append({
            "mirror_file": mirror_path,
            "commit_id": new_commit["commit_id"],
            "score": score,
            "commit_info": new_commit.get("commit_info")
        })

    if not candidates:
        return None

    candidates.sort(key=lambda x: x["score"], reverse=True)

    return {
        "target_file": target_file,
        "candidates": candidates
    }



def find_commit(target_file, code, history_datas):
    """
    history_datas 格式（按时间倒序，新在前）:
    {
        file1:
            [
                {"commit_id": "...", "content": "...", "commit_info": "..."},
                {"commit_id": "...", "content": "...", "commit_info": "..."},
                ...
            ],
        file2:
            [
                {"commit_id": "...", "content": "...", "commit_info": "..."},
                {"commit_id": "...", "content": "...", "commit_info": "..."},
                ...
            ]
    }
    返回:
    [
        {
            "mirror_file": "...",
            "candidates": [
                {
                    "commit_id": "...",
                    "score": float,
                    "commit_info": "..."
                },
                ...
            ]
        },
        ...
    ]
    """
    results = []

    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = []

        for mirror_path, history_data in history_datas.items():
            futures.append(
                pool.submit(analyze_one_mirror, mirror_path, history_data, target_file, code)
            )

        for f in as_completed(futures):
            res = f.result()
            if res is not None:
                results.append(res)
    return results



# 示例调用方式
def example_usage():
    # 模拟外部传入的数据
    target_file = "arch/loongarch/cpu.c"
    code = "code"

    # 模拟获取到的最近三个历史版本（外部逻辑提供）
    mock_history = {
        "file1": [
            {"commit_id": "C4", "content": "code_v4", "commit_info": "commit_info_4"}, # 最新
            {"commit_id": "C3", "content": "code_v3", "commit_info": "commit_info_3"},
            {"commit_id": "C2", "content": "code_v2", "commit_info": "commit_info_2"},
            {"commit_id": "C1", "content": "code_v1", "commit_info": "commit_info_1"}  # 最旧
        ],
        "file2": [
            {"commit_id": "C4", "content": "code_v4", "commit_info": "commit_info_4"}, # 最新
            {"commit_id": "C3", "content": "code_v3", "commit_info": "commit_info_3"},
            {"commit_id": "C2", "content": "code_v2", "commit_info": "commit_info_2"},
            {"commit_id": "C1", "content": "code_v1", "commit_info": "commit_info_1"}  # 最旧
        ]
    }

    results = find_commit(target_file, code, mock_history)

    for res in results:
        print(f"Result: Mirror {res['mirror_file']} needs sync from {res['suggested_commit']}")


def test_is_to_sync():
    with open("./samples/new_loong.cc", 'r') as f:
        file1 = f.read()
    with open("./samples/old_loong.cc", 'r') as f:
        file1_ = f.read()
    with open("./samples/old_riscv.cc", 'r') as f:
        file2 = f.read()
    return is_to_sync(file1, file1_, file2)

if __name__ == "__main__":
    print(f"To sync confidence: {test_is_to_sync()}")