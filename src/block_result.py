from gen_result import gen_result
import tempfile
import subprocess
from extract_block import extract_block
import subprocess
from utils.arch_utils import *
from utils.patch_utils import *
import copy


def collect_mirrored_blocks(inner_headers,blocks2):

    same_named = [False] * len(blocks2)
    blocks2_name = [None] * len(blocks2)
    for i in range(len(blocks2)):
        blocks2_name[i] = extract_name(blocks2[i]['header'])
    for i in range(len(blocks2)):
        if same_named[i]:
            continue
        name1 = blocks2_name[i]
        if name1 == None:
            continue
        for j in range(i+1,len(blocks2)):
            if same_named[j]:
                continue
            if blocks2[i]['file'] != blocks2[j]['file']:
                continue
            name2 = blocks2_name[j]
            if name2 == None:
                continue
            if remove_whitespace(name1) == remove_whitespace(name2) \
                and remove_whitespace(blocks2[i]['header']) != remove_whitespace(blocks2[j]['header']):
                same_named[i],same_named[j] = True, True

    visited = [False] * len(blocks2)
    target_headers = []
    for inner_header in inner_headers:
        block_name1 = extract_name(inner_header)
        for i in range(len(blocks2)):
            if visited[i]:
                continue
            if same_named[i]:
                block_header = blocks2[i]['header']
                if isblockpara(inner_header, block_header):
                    target_headers.append(blocks2[i]['header'])
                    visited[i] = True
            else:
                block_name2 = blocks2_name[i]
                if block_name1 != None and block_name2 != None:
                    if isblockpara(block_name1, block_name2):
                        target_headers.append(blocks2[i]['header'])
                        visited[i] = True
                else:
                    block_header = blocks2[i]['header']
                    if isblockpara(inner_header, block_header):
                        target_headers.append(blocks2[i]['header'])
                        visited[i] = True
    return target_headers


def clear(file_string1,inner_header):
    visited = 0
    tmp_file_string1 = file_string1.split("\n")
    for i,line in enumerate(tmp_file_string1):
        if line not in inner_header:
            tmp_file_string1[i] = " "*len(line)
        else:
            visited = 1
            for j,line in enumerate(tmp_file_string1):
                if j <= i :  continue
                if line in inner_header:
                    visited = visited + 1
                    continue
                if re.match(header_re,line) and visited == len(inner_header):
                    for k,line in enumerate(tmp_file_string1):
                        if k < j :  continue
                        tmp_file_string1[k] = " "*len(line)
                    return tmp_file_string1
            return tmp_file_string1
    return None


def block_result(cfile1,
                patch,
                cfile2,
                use_docker,
                MATCHER_ID,
                TREE_GENERATOR_ID,
                mapping_dic):

    patch = copy.deepcopy(patch)
    if len(read_patch(patch["patch"])) != 0:
        changed_header = read_patch(patch["patch"])[0]
    else:
        changed_header = patch["header"]
    inner_header = []
    for line in patch["patch"]:
        if len(line) > 0 and line[0] == "-" and re.match(header_re,line[1:]):
            inner_header.append(line[1:])
    inner_header = set(inner_header)
    inner_header.add(changed_header)
    file_string1 = clear(cfile1,inner_header)
    file_string1 = "\n".join(file_string1)
    with tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cc') as file1, \
        tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.patch') as patchfile1:
            file1.write(file_string1)
            file1.flush()
            patchfile1.write("\n".join(patch["patch"])+"\n")
            patchfile1.flush()
            output11_ = subprocess.run(["patch",file1.name,"-i",patchfile1.name,"--output=-"],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
            file_string1_ = output11_.stdout.decode()
    file_string2 = cfile2


    blocks2 = extract_block(file_string2.split("\n"),file_name="2")

    target_header = collect_mirrored_blocks(inner_header,blocks2)


    if len(target_header) != len(inner_header):
        with tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cc') as file1, \
        tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.patch') as patchfile1:
            file1.write(cfile1)
            file1.flush()
            patchfile1.write("\n".join(patch["patch"])+"\n")
            patchfile1.flush()
            output11_ = subprocess.run(["patch",file1.name,"-i",patchfile1.name,"--output=-"],
                                        stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE)
            file_string1_ = output11_.stdout.decode()
        file_string2 = gen_result(cfile1,file_string2,file_string1_,mapping_dic,use_docker,MATCHER_ID,TREE_GENERATOR_ID)
        return file_string2

    match = [file_string1.strip()+"\n",
            file_string1_.strip()+"\n",
            "\n".join(clear(file_string2,target_header)).strip()+"\n"
            ]
    block2_ = gen_result(match[0],match[2],match[1],mapping_dic,use_docker,MATCHER_ID,TREE_GENERATOR_ID)
    file_string2 = file_string2.replace(match[2],block2_)
    return file_string2