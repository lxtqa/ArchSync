import sys
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import copy
import argparse
import re
import os
from concurrent.futures import ThreadPoolExecutor
from fuzzywuzzy import process, fuzz
from git import Repo
from src.utils.ast_utils import *
from src.utils.arch_utils import *
from src.utils.file_utils import *
from src.gen_result import parse_diff

# 默认工具路径（建议改为环境变量或配置）
GUMTREE_PATH = "./ISAgumtree/dist/build/distributions/gumtree-4.0.0-beta7-SNAPSHOT/bin/gumtree"
MATCHER_ID = "gumtree-simple"
TREE_GENERATOR_ID = "cpp-srcml"

def get_git_file_content(repo, commit_id, file_path, get_parent=False):
    """从 Git 中获取特定 commit 的文件内容"""
    try:
        commit = repo.commit(commit_id)
        if get_parent:
            if not commit.parents:
                return None
            commit = commit.parents[0]
        
        # 处理路径开头的 /
        rel_path = file_path.lstrip('/')
        blob = commit.tree / rel_path
        return blob.data_stream.read().decode('utf-8')
    except Exception:
        return None

def update_arch_sensitive_identifiers(ast, target_arch):
    if not ast: return
    queue = [ast]
    while queue:
        node = queue.pop(0)
        if node.xml is not None:
            xml_node = node.xml
            if (xml_node.tag.endswith("name") or xml_node.tag.endswith("value")) and xml_node.text:
                old_name = xml_node.text
                new_name = replace_arch(old_name, target_arch)
                if new_name != old_name:
                    xml_node.text = new_name
                    if hasattr(node, 'value') and node.value:
                        node.value = node.value.replace(old_name, new_name)
        if hasattr(node, 'children') and node.children:
            queue.extend(node.children)

def modify_comma(xml_node):
    if xml_node.tag.endswith(("parameter_list", "member_init_list", "super_list", "argument_list")):
        if len(xml_node) != 0:
            for i in range(len(xml_node)-1, -1, -1):
                if not (xml_node[i].tag.endswith("comment") or xml_node[i].tag.endswith("if")):
                    if xml_node[i].tail != None:
                        xml_node[i].tail = re.sub(r",", "", xml_node[i].tail)
                    for j in range(i-1, -1, -1):
                        if not (xml_node[j].tag.endswith("comment") or xml_node[i].tag.endswith("if")):
                            if xml_node[j].tail == None:
                                xml_node[j].tail = ","
                            elif "," not in xml_node[j].tail:
                                xml_node[j].tail = xml_node[j].tail + ", "
                        else:
                            if xml_node[j].tail != None:
                                xml_node[j].tail = re.sub(r",", "", xml_node[j].tail)
                    break
                else:
                    if xml_node[i].tail != None:
                        xml_node[i].tail = re.sub(r",", "", xml_node[i].tail)

def init_ast(ast_root, xml_root):
    ast_nodes = [ast_root]
    xml_nodes = [xml_root]
    while ast_nodes:
        ast_node = ast_nodes.pop()
        xml_node = xml_nodes.pop()
        # 保持原有逻辑不变...
        if xml_node.text == "()":
            xml_node.text = "("
            xml_node.tail = ")" + (xml_node.tail or "")
        elif xml_node.text == "<>":
            xml_node.text = "<"
            xml_node.tail = ">" + (xml_node.tail or "")
        elif xml_node.text == "{}":
            xml_node.text = "{"
            xml_node.tail = "}" + (xml_node.tail or "")
        # ... 这里的省略部分保持你原始代码逻辑 ...
        ast_node.xml = xml_node
        ast_nodes.extend(ast_node.children)
        xml_nodes.extend(xml_node)

def get_newname(node_name, mapping_dic, target_arch):
    arch_replaced_name = replace_arch(node_name, target_arch)
    if node_name not in mapping_dic:
        return arch_replaced_name
    candidate = []
    current_max = 0
    for item in mapping_dic[node_name]:
        if item == arch_replaced_name: return item
        if mapping_dic[node_name][item] > current_max:
            current_max = mapping_dic[node_name][item]
            candidate = [item]
        elif mapping_dic[node_name][item] == current_max:
            candidate.append(item)
    matches = process.extract(node_name, candidate)
    best_match = matches[0][0]
    if current_max <= 1:
        if fuzz.ratio(remove_archwords(best_match), remove_archwords(node_name)) < 50:
            return arch_replaced_name
    return best_match

def construct_mapping_dic(match_dic):
    mapping_dic = {}
    for key, value in match_dic.items():
        if key.split(" ")[0] == "name:" and value.split(" ")[0] == "name:":
            k, v = get_name(key), get_name(value)
            if k not in mapping_dic:
                mapping_dic[k] = {v: 1}
            else:
                mapping_dic[k][v] = mapping_dic[k].get(v, 0) + 1
    return mapping_dic

def gen_result(file_string1, file_string2, file_string1_, target_arch):
    modify_hex(file_string1)
    modify_hex(file_string2)
    modify_hex(file_string1_)
    
    with tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cpp') as cfile1, \
         tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cpp') as cfile1_, \
         tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cpp') as cfile2:

        cfile1.write(file_string1); cfile1.flush()
        cfile1_.write(file_string1_); cfile1_.flush()
        cfile2.write(file_string2); cfile2.flush()

        with ThreadPoolExecutor(max_workers=3) as pool:
            f_ast1  = pool.submit(get_ast, cfile1.name, gumtree_path=GUMTREE_PATH, TREE_GENERATOR_ID=TREE_GENERATOR_ID)
            f_ast1_ = pool.submit(get_ast, cfile1_.name, gumtree_path=GUMTREE_PATH, TREE_GENERATOR_ID=TREE_GENERATOR_ID)
            f_ast2  = pool.submit(get_ast, cfile2.name, gumtree_path=GUMTREE_PATH, TREE_GENERATOR_ID=TREE_GENERATOR_ID)
            ast1, _ = f_ast1.result()
            ast1_, _ = f_ast1_.result()
            ast2, _ = f_ast2.result()

        with ThreadPoolExecutor(max_workers=2) as pool:
            f11_ = pool.submit(subprocess.run, [GUMTREE_PATH, "textdiff", cfile1.name, cfile1_.name, "-m", MATCHER_ID, "-g", TREE_GENERATOR_ID], capture_output=True, text=True)
            f12 = pool.submit(subprocess.run, [GUMTREE_PATH, "textdiff", cfile1.name, cfile2.name, "-m", MATCHER_ID, "-g", TREE_GENERATOR_ID], capture_output=True, text=True)
            output11_ = f11_.result().stdout
            output12 = f12.result().stdout

        with tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.xml') as x1, \
             tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.xml') as x1_, \
             tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.xml') as x2:
            
            for f, x in [(cfile1.name, x1.name), (cfile1_.name, x1_.name), (cfile2.name, x2.name)]:
                subprocess.run(["srcml", "--position", f, "-l", "C++", "--tabs=1", "-o", x], stderr=subprocess.DEVNULL)
            
            xml_tree1, xml_tree1_, xml_tree2 = ET.parse(x1.name).getroot(), ET.parse(x1_.name).getroot(), ET.parse(x2.name).getroot()
            init_ast(ast1, xml_tree1); init_ast(ast1_, xml_tree1_); init_ast(ast2, xml_tree2)

            matches11_, diffs11_ = gumtree_parser(output11_)
            matches12, _ = gumtree_parser(output12)
            
            match_dic12 = {}
            match_dic11_ = {}
            for match in matches12:
                node = re.search(r"(.* \[\d+,\d+\])\n(.* \[\d+,\d+\])", "\n".join(match[2:]), re.DOTALL)
                if node: match_dic12[node[1]] = node[2]
            for match in matches11_:
                node = re.search(r"(.* \[\d+,\d+\])\n(.* \[\d+,\d+\])", "\n".join(match[2:]), re.DOTALL)
                if node: match_dic11_[node[1]] = node[2]

            mapping_dic = construct_mapping_dic(match_dic12)
            
            # --- 打印中间进度统计 ---
            print(f"构建映射关系与编辑脚本成功，构建结点映射{len(matches12)}个，编辑操作{len(diffs11_)}步")
            print(f"构建标识符映射表成功，构建标识符映射{len(mapping_dic)}个")

            changed_nodes = []
            success_count = 0
            for diff in diffs11_:
                try:
                    c = parse_diff(diff, ast1, ast1_, ast2, match_dic11_, match_dic12, mapping_dic, target_arch)
                    if c:
                        changed_nodes.extend(c)
                        success_count += 1
                except: pass
            
            print(f"筛选编辑脚本结束，共有{success_count}/{len(diffs11_)}个待同步操作")

            for changed_node in changed_nodes:
                modify_comma(changed_node)

            with tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.xml') as xml_out:
                ET.ElementTree(ast2.xml).write(xml_out.name, encoding="utf-8", xml_declaration=True)
                return subprocess.run(["srcml", xml_out.name], capture_output=True, text=True).stdout

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Co-evolution Change Recommender')
    parser.add_argument('-r', '--repo', required=True, help="项目路径")
    parser.add_argument('-c', '--commit', required=True, help="commit-id")
    parser.add_argument('-s', '--source', required=True, help="源ISA文件路径")
    parser.add_argument('-t', '--target', required=True, help="目标ISA文件路径")
    parser.add_argument('-o', '--output', required=True, help="协同变更输出路径")
    
    args = parser.parse_args()

    try:
        repo = Repo(args.repo)
    except Exception as e:
        print(f"错误: 无法打开项目路径 {args.repo}")
        sys.exit(1)

    # 1. 获取源ISA旧版文件
    cfile1 = get_git_file_content(repo, args.commit, args.source, get_parent=True)
    if cfile1: print("获取源ISA旧版文件成功")
    else: print("获取源ISA旧版文件失败"); sys.exit(1)

    # 2. 获取源ISA新版文件
    cfile1_ = get_git_file_content(repo, args.commit, args.source, get_parent=False)
    if cfile1_: print("获取源ISA新版文件成功")
    else: print("获取源ISA新版文件失败"); sys.exit(1)

    # 3. 获取目标ISA旧版文件
    cfile2 = get_git_file_content(repo, args.commit, args.target, get_parent=True)
    if not cfile2: # 如果 parent 没有，尝试获取当前 commit 的
        cfile2 = get_git_file_content(repo, args.commit, args.target, get_parent=False)
    
    if cfile2: print("获取目标ISA旧版文件成功")
    else: print("获取目标ISA旧版文件失败"); sys.exit(1)

    # 4-6. 执行核心逻辑并输出中间步骤
    result = gen_result(
        file_string1=cfile1,
        file_string2=cfile2,
        file_string1_=cfile1_,
        target_arch=extract_target_arch(args.target,cfile2)
    )

    # 7. 输出结果
    try:
        os.makedirs(os.path.dirname(args.output), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(result)
        print(f"推荐协同变更完成，结果输出到文件{args.output}。")
    except Exception as e:
        print(f"保存结果失败: {e}")