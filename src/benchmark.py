import os
import re
from utils.arch_utils import *
from utils.ast_utils import *
from utils.patch_utils import *
from block_result import block_result
import json
import tempfile
import concurrent.futures
from time import time



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
    pattern = r'//.*?$|/\*.*?\*/'
    cleaned_content = re.sub(pattern, '', file_content, flags=re.DOTALL | re.MULTILINE)
    return cleaned_content

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
                output22_ = subprocess.run(["patch",cfile2.name,"-i",patchfile2.name,"--output=-"],capture_output=True,text = True)
                file2_string_std = output22_.stdout
        use_docker = False
        file2_string = block_result(file1,patch1,file2,use_docker=use_docker,MATCHER_ID=MATCHER_ID,TREE_GENERATOR_ID=TREE_GENERATOR_ID,mapping_dic = mapping_dic)
        clean_file2_string_std = remove_whitespace(remove_cpp_comments(format(file2_string_std)))
        clean_file2_string = remove_whitespace(remove_cpp_comments(format(file2_string)))
        if clean_file2_string_std == clean_file2_string:
            return True
        else:
            return False
    except:
        return False



def main():
    with open("test/diff.json") as jsonFile:
        versions_diff_block = json.load(jsonFile)
        for v,version in enumerate(versions_diff_block):
            vresult = []
            dir = "./v8"
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
            total_tasks = 0
            succeed_tasks = 0
            start_time = time()
            for t,file_type in enumerate(type_map.keys()):
                mapping_dics = [[{} for _ in range(len(arch_dic))] for _ in range(len(arch_dic))]
                contents = ["" for _ in range(len(arch_dic))]

                for files in type_map[file_type]:
                    files = files[0:4] + files[5:]
                    for r,file in enumerate(files):
                        if file != {} and contents[r] == "":
                            with open(file["file"],"r") as f:
                                contents[r] = modify_hex(format(f.read(),".."))
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future_to_task = {executor.submit(construct_matches, contents[i], contents[2]): (i, 2)
                                        for i in range(len(contents))}
                    for future in concurrent.futures.as_completed(future_to_task):
                        i,j = future_to_task[future]
                        try:
                            mapping_dics[i][j] = construct_mapping_dic(future.result())
                        except Exception as e:
                            pass

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
                    items.append(item)
                results = [[0 for _ in range(len(arch_dic))] for _ in range(len(items))]
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future_to_task = {executor.submit(successfully_generate, items[r][i], items[r][2],mapping_dics[i][2],r+len_item,i,2): (r, i)
                                    for r in range(len(items))
                                    for i in range(len(arch_dic))
                                    }
                    for future in concurrent.futures.as_completed(future_to_task):
                        r,i = future_to_task[future]
                        succeed = future.result()
                        if succeed == True:
                            results[r][i] =  1
                            succeed_tasks += 1
                            total_tasks += 1
                        elif succeed == False:
                            results[r][i] =  -1
                            total_tasks += 1
                        else:
                            results[r][i] = 0
                vresult.extend(results)
                len_item = len_item + len(items)

            print("")
            os.system("git -c advice.detachedHead=false checkout main > /dev/null 2>&1")
            print()
            os.chdir("..")
            print("Accuracy: {}/{} = {}".format(succeed_tasks,total_tasks,succeed_tasks/total_tasks))
            print("Total Time Cost: {}s".format(int(time()-start_time)))
if __name__ == "__main__":
    main()