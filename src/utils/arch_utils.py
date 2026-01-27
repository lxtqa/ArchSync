import re
from fuzzywuzzy import fuzz

# arch_dic = {"arm":0,"arm64":1,"riscv64":2,"mips64":3,"ia32":4,"x64":5,"loong":6,"s390":7,"ppc":8}
# num_dic =  {0:"arm",1:"arm64",2:"riscv64",3:"mips64",4:"ia32",5:"x64",6:"loong",7:"s390",8:"ppc"}


arch_dic = {"arm":0,    "arm64":1,  "riscv":2,  "mips":3,   "x64":4,    "loong":5,  "s390":6,   "ppc":7}
num_dic =  {0:"arm",    1:"arm64",  2:"riscv",  3:"mips",   4:"x64",    5:"loong",  6:"s390",   7:"ppc"}

related_arch = ["arm",  "arm64",    "riscv64","riscv32","riscv",    "mips64","mips32","mips",   "x86","x64",    "loong",    "s390",    "ppc64","ppc32","ppc"]


def has_archwords(text):
        text = text.lower()
        for keyword in ["shared-ia32-x64","shared-x64-ia32"]:
            if keyword in text:
                return "shared-ia32-x64"
        for keyword in ["arm64","aarch64"]:
            if keyword in text:
                return "arm64"
        for keyword in ["arm","aarch"]:
            if keyword in text:
                if keyword == "arm" and "harmon" not in text and "alarm" not in text and "charm" not in text and "armor" not in text:
                    return "arm"
        for keyword in ["x64","x86_64","x86-64","ia64"]:
            if keyword in text and "linux64" not in text:
                return "x64"
        for keyword in ["ia32","i386","x86_32"]:
            if keyword in text:
                return "ia32"
        for keyword in ["x86"]:
            if keyword in text:
                return "x86"
        for keyword in ["riscv32","risc-v32"]:
            if keyword in text:
                return "riscv32"
        for keyword in ["riscv64","risc-v64"]:
            if keyword in text:
                return "riscv64"
        for keyword in ["riscv","risc-v"]:
            if keyword in text:
                return "riscv"
        for keyword in ["s390","systemz","s390x"]:
            if keyword in text:
                return "s390"
        for keyword in ["ppc64","powerpc64"]:
            if keyword in text:
                return "ppc64"
        for keyword in ["ppc32","powerpc32"]:
            if keyword in text:
                return "ppc32"
        for keyword in ["ppc","powerpc"]:
            if keyword in text and "cppc" not in text:
                return "ppc"
        for keyword in ["mips64"]:
            if keyword in text:
                return "mips64"
        for keyword in ["mips32"]:
            if keyword in text:
                return "mips32"
        for keyword in ["mips"]:
            if keyword in text:
                return "mips"
        for keyword in ["loong","loongarch"]:
            if keyword in text:
                return "loong"
        return None


def remove_archwords(text):
    text = text.lower()
    archs = [
                "arm64","aarch64","aarch",\
                "arm","aarch32",\
                "x64","x86","ia32","i386","x86_64", \
                "riscv64","riscv32","riscv",\
                "s390","s390x","systemz",\
                "ppc64","ppc32","ppc","powerpc64","powerpc32","powerpc",\
                "mips64","mips32","mips",\
                "loongarch64","loongarch32","loongarch","loong64","loong32","loong"
            ]
    for keyword in sorted(archs,key=len,reverse=True):
        if keyword in text:
            text = text.replace(keyword, '')
            return remove_archwords(text)
    return text


def remove_whitespace(input_string):
    return re.sub(r"(?<!\\)\\(?!\\)", "",re.sub(r'\s+', '', input_string))

def is_file_para(file1, file2):
    # 实现文件是否平行的逻辑
    return remove_whitespace(remove_archwords(file1)) == remove_whitespace(remove_archwords(file2))


patten1 = re.compile(r"(?:^\w+\s+)*(\w*:?:?\w+)\(.*\).*{$")
patten2 = re.compile(r"^(\w*:?:?\w+)\(.*\).*{$")

def extract_name(header):
    name = patten1.findall(header)
    if name != []:
        return name[0]
    name = patten2.findall(header)
    if name!= []:
        return name[0]

    return None

patten3 = re.compile(r"^\s*(//|/\*.*\*/|/\*.*?$)")

def is_block_para(block1, block2):
    if block1 == "" or block2 == "":
        return block1 == block2
    if patten3.match(block1) and patten3.match(block2):
        return fuzz.ratio(block1,block2) > 95

    # 实现block是否平行的逻辑
    arc1 = has_archwords(block1)
    arc2 = has_archwords(block2)
    if arc1 and arc2:
        return remove_whitespace(remove_archwords(block1)) == remove_whitespace(remove_archwords(block2))
    elif not arc1 and not arc2:
        return remove_whitespace(block1) == remove_whitespace(block2)
    return False
