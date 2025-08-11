from utils.ast_utils import *
import sys
import subprocess
import tempfile
from fuzzywuzzy import process,fuzz
import xml.etree.ElementTree as ET
import copy


def modify_comma(xml_node):
    if xml_node.tag.endswith("parameter_list") or xml_node.tag.endswith("member_init_list") or xml_node.tag.endswith("super_list") or xml_node.tag.endswith("argument_list"):
        if len(xml_node)!=0:
            for i in range(len(xml_node)-1,-1,-1):
                if not (xml_node[i].tag.endswith("comment") or xml_node[i].tag.endswith("if")):
                    if xml_node[i].tail != None:
                        xml_node[i].tail = re.sub(r",","",xml_node[i].tail)
                    for j in range(i-1,-1,-1):
                        if not (xml_node[j].tag.endswith("comment") or xml_node[i].tag.endswith("if")):
                            if xml_node[j].tail == None:
                                xml_node[j].tail = ","
                            elif "," not in xml_node[j].tail:
                                xml_node[j].tail = xml_node[j].tail + ", "
                        else:
                            if xml_node[j].tail != None:
                                xml_node[j].tail = re.sub(r",","",xml_node[j].tail)
                    break
                else:
                    if xml_node[i].tail != None:
                        xml_node[i].tail = re.sub(r",","",xml_node[i].tail)


def init_ast(ast_root,xml_root):
    ast_nodes = [ast_root]
    xml_nodes = [xml_root]
    while ast_nodes != []:
        ast_node = ast_nodes.pop()
        xml_node = xml_nodes.pop()
        if xml_node.text == "()":
            xml_node.text = "("
            if xml_node.tail != None:
                xml_node.tail = ")" + xml_node.tail
            else:
                xml_node.tail = ")"
        elif xml_node.text == "<>":
            xml_node.text = "<"
            if xml_node.tail != None:
                xml_node.tail = ">" + xml_node.tail
            else:
                xml_node.tail = ">"
        elif xml_node.text == "{}":
            xml_node.text = "{"
            if xml_node.tail != None:
                xml_node.tail = "}" + xml_node.tail
            else:
                xml_node.tail = "}"
        elif xml_node.text != None and xml_node.text.startswith("(") and ((xml_node.tail != None and not xml_node.tail.startswith(")")) or xml_node.tail == None):
            if len(xml_node) > 0:
                if xml_node[-1].tail == ")":
                    if xml_node[-1].text!="(":
                        xml_node[-1].tail = None
                    if xml_node.tail != None:
                        xml_node.tail=")" + xml_node.tail
                    else:
                        xml_node.tail = ")"
        elif xml_node.text != None and xml_node.text.startswith("<") and ((xml_node.tail != None and not xml_node.tail.startswith(">")) or xml_node.tail == None):
            if len(xml_node) > 0:
                if xml_node[-1].tail == ">":
                    if xml_node[-1].text!="<":
                        xml_node[-1].tail = None
                    if xml_node.tail != None:
                        xml_node.tail=">" + xml_node.tail
                    else:
                        xml_node.tail = ">"
        elif xml_node.text != None and xml_node.text.startswith("{") and ((xml_node.tail != None and not xml_node.tail.startswith("}")) or xml_node.tail == None):
            if len(xml_node) > 0:
                if xml_node[-1].tail == "}":
                    if xml_node[-1].text!="{":
                        xml_node[-1].tail = None
                    if xml_node.tail != None:
                        xml_node.tail="}" + xml_node.tail
                    else:
                        xml_node.tail = "}"
        ast_node.xml = xml_node
        ast_nodes.extend(ast_node.children)
        xml_nodes.extend(xml_node)


def map(root,mapping_dic):
    #获取产生修改部分的补丁代码中需要进行映射的操作
    queue = [root]
    while queue:
        xml = queue.pop()
        if xml.tag.endswith("name") and xml.text !=  None:
            new_name = get_newname(xml.text,mapping_dic)
            if new_name:
                xml.text =  new_name
        queue.extend(xml)
    return root



def get_newname(node_name,mapping_dic):
    """
        对name节点进行映射
    """
    if node_name not in mapping_dic.keys():
        return node_name
    candidate = []
    current_max = 0

    for item in mapping_dic[node_name].keys():
        if item == node_name:
            return item
        if mapping_dic[node_name][item] > current_max:
            current_max = mapping_dic[node_name][item]
            candidate = [item]
        elif mapping_dic[node_name][item] == current_max:
            candidate.append(item)

    matches = process.extract(node_name, candidate)

    if current_max <= 1 and fuzz.ratio(matches[0][0],node_name) < 50:
        return node_name
    return matches[0][0]


def parse_diff(diff,ast1,ast1_,ast2,match_dic11_,match_dic12,mapping_dic):
    if diff[0] == "insert-node" or diff[0] == "insert-tree":
        source = parse_tree_from_text(diff[2:-3])
        des_node = parse_tree_from_text([diff[-2]])
        if None != bfs_search(ast1,des_node.value + "_"):
            des_node.value = des_node.value + "_"
        desRank = int(diff[-1].split(" ")[-1])
        father1 = bfs_search(ast1,des_node.value)
        source = copy.deepcopy(bfs_search(ast1_,source.value))
        queue = [source]
        while queue:
            node = queue.pop()
            node.value = node.value + "_"
            queue.extend(node.children)
        if diff[0] == "insert-node":
            for i in range(len(source.xml)-1,-1,-1):
                source.xml.remove(source.xml[i])
            source.children = []
        father1.xml.insert(desRank,source.xml)
        father1.children.insert(desRank,source)

        #不在father中找,而是直接找前后关系

        new_source = copy.deepcopy(source)

        for i in range(desRank-1,-1,-1):
            if father1.children[i].value in match_dic12:
                father2 = bfs_search_father(ast2,match_dic12[father1.children[i].value])
                for j,child in enumerate(father2.children):
                    if match_dic12[father1.children[i].value] == child.value:
                        queue = [new_source]
                        while queue:
                            node = queue.pop()
                            match_dic12[node.value] = node.value
                            queue.extend(node.children)
                        father2.xml.insert(j+1,map(new_source.xml,mapping_dic))
                        father2.children.insert(j+1,new_source)
                        return [father2.xml]
        for i in range(desRank+1,len(father1.children)):
            if father1.children[i].value in match_dic12:
                father2 = bfs_search_father(ast2,match_dic12[father1.children[i].value])
                for j,child in enumerate(father2.children):
                    if match_dic12[father1.children[i].value] == child.value:
                        queue = [new_source]
                        while queue:
                            node = queue.pop()
                            match_dic12[node.value] = node.value
                            queue.extend(node.children)
                        father2.xml.insert(j,map(new_source.xml,mapping_dic))
                        father2.children.insert(j,new_source)
                        return [father2.xml]
        if des_node.value in match_dic12.keys():
            father2 = bfs_search(ast2,match_dic12[des_node.value])
            queue = [new_source]
            while queue:
                node = queue.pop()
                match_dic12[node.value] = node.value
                queue.extend(node.children)
            father2.xml.insert(0,map(new_source.xml,mapping_dic))
            father2.children.insert(0,new_source)
            return [father2.xml]
    elif diff[0] == "delete-node" or diff[0] == "delete-tree":
        des_node = parse_tree_from_text(diff[2:])
        if des_node.value in match_dic12.keys():
            # find des_node in ast1
            father1 = bfs_search_father(ast1,des_node.value)
            des1 = bfs_search(father1,des_node.value)
            father1.children.remove(des1)
            father1.xml.remove(des1.xml)
            # find paral node in ast2
            father2 = bfs_search_father(ast2,match_dic12[des_node.value])
            des2 = bfs_search(father2,match_dic12[des_node.value])
            father2.children.remove(des2)
            father2.xml.remove(des2.xml)
            return [father2.xml]
    elif diff[0] == "update-node":
        node = re.search(r"(.*: (.*) \[\d+,\d+\])\nreplace \2 by (.*)","\n".join(diff[2:]),re.DOTALL)
        if node == None:
            node = re.search(r"(.* \[\d+,\d+\])\nreplace (.*) by (.*)","\n".join(diff[2:]),re.DOTALL)
        if node[1] in match_dic12.keys():
            # find des_node in ast1
            des1 = bfs_search(ast1,node[1])
            # find paral node in ast2
            des2 = bfs_search(ast2,match_dic12[node[1]])
            # update text in ast1
            des1.xml.text = node[3]
            # update text in ast2
            des2.xml.text = get_newname(node[3],mapping_dic)
            return [des2.xml]
    elif diff[0] == "move-node" or diff[0] == "move-tree":
        source = parse_tree_from_text(diff[2:-3])
        des_node = parse_tree_from_text([diff[-2]])
        if source.value in match_dic12.keys():
            if None != bfs_search(ast1,des_node.value + "_"):
                des_node.value = des_node.value + "_"
            new_source = bfs_search(ast2,match_dic12[source.value])
            desRank = int(diff[-1].split(" ")[-1])
            source = bfs_search(ast1,source.value)
            source_ = bfs_search(ast1_,match_dic11_[source.value])
            father1 = bfs_search_father(ast1,source.value)
            father1.xml.remove(source.xml)
            father1.children.remove(source)
            father2 = bfs_search_father(ast2,match_dic12[source.value])
            father2.xml.remove(new_source.xml)
            father2.children.remove(new_source)

            #插入需要找到前后能够产生映射的地方
            if source.xml.tail != source_.xml.tail:
                source.xml.tail = source_.xml.tail
                new_source.xml.tail = source_.xml.tail

            des1 = bfs_search(ast1,des_node.value)
            des1.xml.insert(desRank,source.xml)
            des1.children.insert(desRank,source)

            for i in range(desRank-1,-1,-1):
                if des1.children[i].value in match_dic12:
                    des2 = bfs_search_father(ast2,match_dic12[des1.children[i].value])
                    for j,child in enumerate(des2.children):
                        if match_dic12[des1.children[i].value] == child.value:
                            des2.xml.insert(j+1,new_source.xml)
                            des2.children.insert(j+1,new_source)
                            return [des2.xml,father2.xml]
            for i in range(desRank+1,len(des1.children)):
                if des1.children[i].value in match_dic12:
                    des2 = bfs_search_father(ast2,match_dic12[des1.children[i].value])
                    for j,child in enumerate(des2.children):
                        if match_dic12[des1.children[i].value] == child.value:
                            des2.xml.insert(j,new_source.xml)
                            des2.children.insert(j,new_source)
                            return [des2.xml,father2.xml]

            if des_node.value in match_dic12.keys():
                des2 = bfs_search(ast2,match_dic12[des_node.value])
                des2.xml.insert(0,new_source.xml)
                des2.children.insert(0,new_source)
                return [des2.xml,father2.xml]



def gen_result(file_string1,
                file_string2,
                file_string1_,
                mapping_dic,
                use_docker,
                MATCHER_ID,
                TREE_GENERATOR_ID
                ):
    '''
    cfile_name1为架构a下的文件, cfile2_name2为架构b下的文件, cfile_name1_为cfile_name1修改后的文件
    取cfile1和cfile2的match部分, 取cfile1与cfile1_的diff部分
    '''

    with tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cpp') as cfile1, \
        tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cpp') as cfile1_, \
        tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cpp') as cfile2:

        cfile1.write(file_string1)
        cfile1.flush()
        cfile1_.write(file_string1_)
        cfile1_.flush()
        cfile2.write(file_string2)
        cfile2.flush()

        ast1, _ = get_ast(cfile1.name,use_docker=use_docker,TREE_GENERATOR_ID=TREE_GENERATOR_ID)

        ast1_, _  = get_ast(cfile1_.name,use_docker=use_docker,TREE_GENERATOR_ID=TREE_GENERATOR_ID)

        ast2, _  = get_ast(cfile2.name,use_docker=use_docker,TREE_GENERATOR_ID=TREE_GENERATOR_ID)



        output11_ = subprocess.run(["gumtree","textdiff",cfile1.name, cfile1_.name,
                                    "-m",MATCHER_ID,"-g", TREE_GENERATOR_ID],
                                    capture_output=True,text = True).stdout
        output12 = subprocess.run(["gumtree","textdiff",cfile1.name, cfile2.name,
                                    "-m",MATCHER_ID,"-g", TREE_GENERATOR_ID],
                                    capture_output=True,text = True).stdout

        with tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cpp') as xmlfile1, \
            tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cpp') as xmlfile1_, \
            tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.cpp') as xmlfile2:
            subprocess.run(["srcml","--position",cfile1.name,"-l","C++","--tabs=1","-o",xmlfile1.name])
            xmlfile1.flush()
            xml_tree1 = ET.parse(xmlfile1.name).getroot()
            subprocess.run(["srcml","--position",cfile1_.name,"-l","C++","--tabs=1","-o",xmlfile1_.name])
            xmlfile1_.flush()
            xml_tree1_ = ET.parse(xmlfile1_.name).getroot()
            subprocess.run(["srcml","--position",cfile2.name,"-l","C++","--tabs=1","-o",xmlfile2.name])
            xmlfile2.flush()
            xml_tree2 = ET.parse(xmlfile2.name).getroot()
            init_ast(ast1,xml_tree1)
            init_ast(ast1_,xml_tree1_)
            init_ast(ast2,xml_tree2)


            matches11_, diffs11_ = gumtree_parser(output11_)
            matches12, _= gumtree_parser(output12)
            #parse match
            match_dic12 = {}
            match_dic11_ = {}
            for match in matches12:
                node = re.search(r"(.* \[\d+,\d+\])\n(.* \[\d+,\d+\])","\n".join(match[2:]),re.DOTALL)
                match_dic12[node[1]] = node[2]
            for match in matches11_:
                node = re.search(r"(.* \[\d+,\d+\])\n(.* \[\d+,\d+\])","\n".join(match[2:]),re.DOTALL)
                match_dic11_[node[1]] = node[2]
            changed_nodes = []
            for diff in diffs11_:
                try:
                    c = parse_diff(diff,ast1,ast1_,ast2,match_dic11_,match_dic12,mapping_dic)
                    if c!= None:
                        changed_nodes.extend(c)
                except:
                    pass

            for changed_node in changed_nodes:
                modify_comma(changed_node)

            with tempfile.NamedTemporaryFile(delete=True, mode='w', suffix='.xml') as xmlfile2_:
                ET.ElementTree(ast2.xml).write(xmlfile2_.name, encoding="utf-8", xml_declaration=True)
                xmlfile2_.flush()
                sys.stdout.flush()

                return subprocess.run(["srcml",xmlfile2_.name], capture_output=True,text = True).stdout

