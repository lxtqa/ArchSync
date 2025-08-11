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
        for keyword in ["avr"]:
            if keyword in text:
                return "avr"
        for keyword in ["sparc64"]:
            if keyword in text:
                return "sparc64"
        for keyword in ["sparc"]:
            if keyword in text:
                return "sparc"
        for keyword in ["amdgpu"]:
            if keyword in text:
                return "amdgpu"
        for keyword in ["csky"]:
            if keyword in text:
                return "csky"
        for keyword in ["hexagon"]:
            if keyword in text:
                return "hexagon"
        for keyword in ["m68k"]:
            if keyword in text:
                return "m68k"
        for keyword in ["msp430"]:
            if keyword in text:
                return "msp430"
        for keyword in ["nvptx"]:
            if keyword in text:
                return "nvptx"
        for keyword in ["xcore"]:
            if keyword in text:
                return "xcore"
        for keyword in ["xtensa"]:
            if keyword in text:
                return "xtensa"
        for keyword in ["tricore"]:
            if keyword in text:
                return "tricore"
        for keyword in ["hppa"]:
            if keyword in text:
                return "hppa"
        for keyword in ["microblaze"]:
            if keyword in text:
                return "microblaze"
        for keyword in ["openrisc"]:
            if keyword in text:
                return "openrisc"
        for keyword in ["sh4","/sh/","/sh_","/sh-","_sh/","_sh_","-sh-","-sh_","-sh/"]:
            if keyword in text:
                return "sh4"
        for keyword in ["rx"]:
            if keyword in text:
                return "rx"
        for keyword in ["/arc/","/arc_","/arc-","_arc/","_arc_","-arc-","-arc_","-arc/"]:
            if keyword in text:
                return "arc"
        for keyword in ["mmix"]:
            if keyword in text:
                return "mmix"
        for keyword in ["bpf"]:
            if keyword in text:
                return "bpf"
        for keyword in ["cris"]:
            if keyword in text:
                return "cris"
        for keyword in ["fr30"]:
            if keyword in text:
                return "fr30"
        for keyword in ["gcn"]:
            if keyword in text:
                return "gcn"
        for keyword in ["iq2000"]:
            if keyword in text:
                return "iq2000"
        for keyword in ["m32r"]:
            if keyword in text:
                return "m32r"
        for keyword in ["lm32"]:
            if keyword in text:
                return "lm32"
        for keyword in ["mcore"]:
            if keyword in text:
                return "mcore"
        for keyword in ["nds32"]:
            if keyword in text:
                return "nds32"
        for keyword in ["nios2"]:
            if keyword in text:
                return "nios2"
        for keyword in ["parisc"]:
            if keyword in text:
                return "parisc"
        for keyword in ["pdp11"]:
            if keyword in text:
                return "pdp11"
        for keyword in ["pru"]:
            if keyword in text:
                return "pru"
        for keyword in ["rs6000"]:
            if keyword in text:
                return "rs6000"
        for keyword in ["vax"]:
            if keyword in text:
                return "vax"
        for keyword in ["v850"]:
            if keyword in text:
                return "v850"
        for keyword in ["visium"]:
            if keyword in text:
                return "visium"
        for keyword in ["/um/","/um_","/um-","_um/","_um_","-um-","-um_","-um/"]:
            if keyword in text:
                return "um"
        for keyword in ["epiphany"]:
            if keyword in text:
                return "epiphany"
        for keyword in ["frv"]:
            if keyword in text:
                return "frv"
        for keyword in ["h8300"]:
            if keyword in text:
                return "h8300"
        for keyword in ["tilera"]:
            if keyword in text:
                return "tilera"
        for keyword in ["xstormy16"]:
            if keyword in text:
                return "xstormy16"
        for keyword in ["/pa/","/pa_","/pa-","_pa/","_pa_","-pa-","-pa_","-pa/"]:
            if keyword in text:
                return "pa"
        return None


def remove_archwords(text):
    text = text.lower()
    archs = ["shared-ia32-x64","shared-x64-ia32", \
                    "arm64","arm","aarch32","aarch64","aarch",\
                    "x64","x86","ia32","i386","x86_64", \
                    "riscv64","riscv32","riscv",\
                    "s390","s390x","systemz",\
                    "ppc64","ppc32","ppc","powerpc64","powerpc32","powerpc",\
                    "mips64","mips32","mips",\
                    "loongarch64","loongarch32","loongarch","loong64","loong32","loong",\
                    "amdgpu",\
                    "avr",\
                    "hppa",\
                    "csky",\
                    "hexagon",\
                    "m68k",\
                    "msp430",\
                    "nvptx",\
                    "sparc","sparc64",\
                    "ve",\
                    "xcore",\
                    "xtensa",\
                    "tricore",\
                    "microblaze",\
                    "openrisc",\
                    "sh4","sh",\
                    "rx",\
                    "arc"]
    for keyword in sorted(archs,key=len,reverse=True):
        if keyword in text:
            text = text.replace(keyword, '')
            return remove_archwords(text)
    return text


def remove_whitespace(input_string):
    return re.sub(r"(?<!\\)\\(?!\\)", "",re.sub(r'\s+', '', input_string))

def isfilepara(file1, file2):
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

def isblockpara(block1, block2):
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
