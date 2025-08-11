import os
import re
from utils.arch_utils import *
from utils.ast_utils import *
from utils.patch_utils import *
from block_result import block_result
from extract_block import extract_block
import json
import tempfile
import concurrent.futures
from time import time
from gen_result import gen_result
import copy


def collect_mirrored_blocks(contents):
    all_blocks = []
    # 收集所有文件的blocks
    all_same_named = []
    for k,content in enumerate(contents):
        blocks = extract_block(content.split("\n"),num_dic[k])
        same_named = [False] * len(blocks)
        blocks2_name = [None] * len(blocks)
        for i in range(len(blocks)):
            blocks2_name[i] = extract_name(blocks[i]['header'])
        for i in range(len(blocks)):
            if same_named[i]:
                continue
            name1 = blocks2_name[i]
            if name1 == None:
                continue
            for j in range(i+1,len(blocks)):
                if same_named[j]:
                    continue
                name2 = blocks2_name[j]
                if name2 == None:
                    continue
                if remove_whitespace(name1) == remove_whitespace(name2) \
                    and remove_whitespace(blocks[i]['header']) != remove_whitespace(blocks[j]['header']):
                    same_named[i],same_named[j] = True, True
        all_blocks.extend(blocks)
        all_same_named.extend(same_named)


    mirrored_blocks_groups = []

    #首先过一遍纯name的检查，然后再进行header的检查
    #先检查同文件内是否有相同name的函数，如果没有，则直接认为name相同即为para
    #如果有则比较block
    # 判断平行的条件：file平行且不同，

    # 找到所有平行的blocks


    visited = [False] * len(all_blocks)
    for i in range(len(all_blocks)):
        if visited[i]:
            continue
        mirrored_group = [all_blocks[i]]
        visited[i] = True
        if all_same_named[i]:
            block_header1 = all_blocks[i]['header']
            for j in range(i + 1, len(all_blocks)):
                block_header2 = all_blocks[j]['header']
                if isblockpara(block_header1, block_header2):
                    mirrored_group.append(all_blocks[j])
                    visited[j] = True
        else:
            block_name1 = extract_name(all_blocks[i]['header'])
            block_header1 = all_blocks[i]['header']
            for j in range(i + 1, len(all_blocks)):
                block_name2 = extract_name(all_blocks[j]['header'])
                if block_name1 != None and block_name2 != None and not all_same_named[j]:
                    if  isblockpara(block_name1, block_name2):
                        mirrored_group.append(all_blocks[j])
                        visited[j] = True
                else:
                    block_header2 = all_blocks[j]['header']
                    if  isblockpara(block_header1, block_header2):
                        mirrored_group.append(all_blocks[j])
                        visited[j] = True
        #判断mirrored_group中是否存在相同的，如果相同，则合并
        if len(mirrored_group) > 1:
            merged_dict = {}

            for item in mirrored_group:
                key = (item['header'], item['file'])

                if key in merged_dict:
                    # 假设 'value' 字段是一个列表，进行合并
                    merged_dict[key]['content'].extend(item['content'])
                else:
                    # 如果这个键不存在，直接添加到合并字典中
                    merged_dict[key] = item
            # 将合并结果转换回列表格式
            if len(list(merged_dict.values())) > 1:
                lst = [{} for _ in range(len(arch_dic))]
                for block in list(merged_dict.values()):
                    lst[arch_dic[block["file"]]]=block
                mirrored_blocks_groups.append(lst)

    return mirrored_blocks_groups



def construct_mapping_dic(matches):
    match_dic = {}
    for match in matches:
        if match[1]!="---":
            exit(201)
        match_dic[match[2]] = match[3]
    mapping_dic = {}
    for key in match_dic.keys():
        value = match_dic[key]
        if key.split(" ")[0] == "name:" and value.split(" ")[0] == "name:":
            k,v = get_name(key),get_name(value)
            if k not in mapping_dic.keys():
                mapping_dic[k] = {v:1}
            else:
                if v not in mapping_dic[k].keys():
                    mapping_dic[k][v] = 1
                else:
                    mapping_dic[k][v] = mapping_dic[k][v] + 1
    return mapping_dic


def construct_matches(file1,file2):
    if file1 == {} or file2 == {} or file1 == "" or file2 == "" or  file1 == file2:
        return []
    if type(file1) != str:
        file1 = "\n".join(file1["content"])
    if type(file2) != str:
        file2 = "\n".join(file2["content"])
    with tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cc') as cfile1, \
        tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cc') as cfile2:
        cfile1.write(file1)
        cfile1.flush()
        cfile2.write(file2)
        cfile2.flush()
        result = subprocess.run(["gumtree","textdiff",cfile1.name, cfile2.name,
                                "-m",MATCHER_ID,"-g", TREE_GENERATOR_ID],
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        matches, _ = gumtree_parser(result.stdout.decode())
    return matches





def remove_cpp_comments(file_content):
    # 正则表达式匹配 C++ 的注释
    pattern = r'//.*?$|/\*.*?\*/'

    # 使用 re.sub 替换掉匹配的注释内容，re.DOTALL 让 . 能匹配换行符，re.MULTILINE 处理多行注释
    cleaned_content = re.sub(pattern, '', file_content, flags=re.DOTALL | re.MULTILINE)

    return cleaned_content

def file_result(file1,patch1,file2,use_docker,MATCHER_ID,TREE_GENERATOR_ID,mapping_dic):
    patch1 = copy.deepcopy(patch1)
    with tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cc') as cfile1, \
        tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.patch') as patchfile1:
            cfile1.write(file1)
            cfile1.flush()
            patchfile1.write("\n".join(patch1["patch"])+"\n")
            patchfile1.flush()
            output11_ = subprocess.run(["patch",cfile1.name,patchfile1.name,"--output=-"],capture_output=True,text = True)
            file1_string_std = output11_.stdout
    return gen_result(file1,file2,file1_string_std,mapping_dic=mapping_dic,use_docker=use_docker,MATCHER_ID=MATCHER_ID,TREE_GENERATOR_ID=TREE_GENERATOR_ID)


def successfully_generate(item1,item2,mapping_dic,r,i,j):
    if item1 == [] or item2 == [] or item1 == item2:
        return None
    try:
        file1,patch1 = item1
        file2,patch2 = item2

        modify_hex(file1)
        modify_hex(file2)

        with tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cc') as cfile2, \
            tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.patch') as patchfile2:
                cfile2.write(file2)
                cfile2.flush()
                patchfile2.write("\n".join(patch2["patch"])+"\n")
                patchfile2.flush()
                output22_ = subprocess.run(["patch",cfile2.name,patchfile2.name,"--output=-"],capture_output=True,text = True)
                file2_string_std = output22_.stdout
        use_docker = False
        file2_string = block_result(file1,patch1,file2,use_docker=use_docker,MATCHER_ID=MATCHER_ID,TREE_GENERATOR_ID=TREE_GENERATOR_ID,mapping_dic = mapping_dic)
        # file2_string = file_result(file1,patch1,file2,use_docker=use_docker,MATCHER_ID=MATCHER_ID,TREE_GENERATOR_ID=TREE_GENERATOR_ID,mapping_dic = mapping_dic)
        clean_file2_string_std = remove_whitespace(remove_cpp_comments(format(file2_string_std)))
        clean_file2_string = remove_whitespace(remove_cpp_comments(format(file2_string)))
        #除去所有的注释和空字符
        if clean_file2_string_std == clean_file2_string:
            return True
        else:
            return False
    except:
        return False



def main():
    # with open("versions_diff_block_same_len_15.json") as jsonFile:
    with open("commits_diff_block_same_len_15_llvm.json") as jsonFile:
        versions_diff_block = json.load(jsonFile)
        for v,version in enumerate(versions_diff_block):
            vresult = []
            dir = "llvm-project"
            os.chdir(dir)
            os.system("git -c advice.detachedHead=false  checkout " + version["versions"][0])
            print()
            type_map = {}
            for t,file_type in enumerate(version["contents"]):
                for ft in file_type:
                    if ft!={}:
                        if remove_archwords(ft["file"]) not in type_map.keys():
                            type_map[remove_archwords(ft["file"])] = [file_type]
                        else:
                            type_map[remove_archwords(ft["file"])].append(file_type)
                        break




            len_item = 0
            for t,file_type in enumerate(type_map.keys()):
                print(str(t)+"/"+str(len(type_map.keys())),end=" ",flush=True)
                start_time = time()
                mapping_dics = [[{} for _ in range(len(arch_dic))] for _ in range(len(arch_dic))]


                contents = ["" for _ in range(len(arch_dic))]


                for files in type_map[file_type]:
                    for r,file in enumerate(files):
                        if file != {} and contents[r] == "":
                            with open(file["file"],"r") as f:
                                contents[r] = modify_hex(format(f.read(),".."))
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future_to_task = {executor.submit(construct_matches, contents[i], contents[j]): (i, j)
                                        for i in range(len(contents))
                                        for j in range(len(contents))}
                    for future in concurrent.futures.as_completed(future_to_task):
                        i,j = future_to_task[future]
                        try:
                            mapping_dics[i][j] = construct_mapping_dic(future.result())
                        except Exception as e:
                            pass

                # mapping_lists = [[[] for _ in range(len(arch_dic))] for _ in range(len(arch_dic))]

                # for files in type_map[file_type]:
                #     for r,file in enumerate(files):
                #         if file != {} and contents[r] == "":
                #             with open(file["file"],"r") as f:
                #                 contents[r] = modify_hex(format(f.read(),".."))
                # contents = collect_mirrored_blocks(contents)
                # with concurrent.futures.ThreadPoolExecutor() as executor:
                #     future_to_task = {executor.submit(construct_matches, contents[r][i], contents[r][j]): (r, i, j)
                #                         for r in range(len(contents))
                #                         for i in range(len(contents[r]))
                #                         for j in range(len(contents[r]))}
                #     for future in concurrent.futures.as_completed(future_to_task):
                #         r,i,j = future_to_task[future]
                #         try:
                #             mapping_lists[i][j].extend(future.result())
                #         except Exception as e:
                #             pass

                # for i in range(len(mapping_lists)):
                #     for j in range(len(mapping_lists[i])):
                #         mapping_dics[i][j] = construct_mapping_dic(mapping_lists[i][j])



                end_time = time()
                print("构建map耗时: {}s".format(int(end_time-start_time)),end=" ")

                items = []
                for r,files in enumerate(type_map[file_type]):
                    item = []
                    for file in files:
                        if file == {}:
                            item.append([])
                            continue
                        with open(file["file"],"r") as f:
                            content = format(f.read(),"..")
                            patch = {"header":file["header"],"patch":file["patch"]}
                            item.append([content,patch])
                            # 使用 ThreadPoolExecutor 来并发执行任务
                    items.append(item)
                start_time = time()
                results = [[[0 for _ in range(len(arch_dic))] for _ in range(len(arch_dic))] for _ in range(len(items))]
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    # 提交所有任务到线程池
                    future_to_task = {executor.submit(successfully_generate, items[r][i], items[r][j],mapping_dics[i][j],r+len_item,i,j ): (r, i, j)
                                    for r in range(len(items))
                                    for i in range(len(arch_dic))
                                    for j in range(len(arch_dic))
                                    }
                    for future in concurrent.futures.as_completed(future_to_task):
                        r,i,j = future_to_task[future]
                        succeed = future.result()
                        if succeed == True:
                            results[r][i][j] =  1
                        elif succeed == False:
                            results[r][i][j] =  -1
                        else:
                            results[r][i][j] = 0
                vresult.extend(results)
                len_item = len_item + len(items)
                end_time = time()
                print("生成结果耗时: {}s".format(int(end_time-start_time)),end=" ")
            print("")
            os.system("git -c advice.detachedHead=false checkout main > /dev/null 2>&1")
            print()
            os.chdir("..")

            with open("result_llvm/result"+str(v)+".json","w") as f:
                json.dump(vresult,f,indent=4)

if __name__ == "__main__":
    main()
