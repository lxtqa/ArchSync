FROM ubuntu:20.04 AS builder

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHON_VERSION=3.11.8
ENV PYTHON_INSTALL_DIR=/usr/local

# 安装构建依赖
RUN apt-get update && apt-get install -y \
    build-essential wget curl libssl-dev zlib1g-dev \
    libncurses5-dev libncursesw5-dev libreadline-dev \
    libsqlite3-dev libgdbm-dev libbz2-dev libexpat1-dev \
    liblzma-dev tk-dev libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# 下载 Python 源码
RUN wget https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tgz \
    && tar xvf Python-$PYTHON_VERSION.tgz

# 编译安装 Python
WORKDIR Python-$PYTHON_VERSION
RUN ./configure --prefix=$PYTHON_INSTALL_DIR --enable-optimizations \
    && make -j$(nproc) \
    && make altinstall

# ---------- Stage 2: 创建最终镜像 ----------
FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHON_INSTALL_DIR=/usr/local

# 安装运行 Python 所需的最小依赖
RUN apt-get update && apt-get install -y \
    libssl1.1 zlib1g libncurses5 libreadline8 libsqlite3-0 \
    libgdbm6 libbz2-1.0 libexpat1 liblzma5 tk8.6 libffi7 \
    && rm -rf /var/lib/apt/lists/*

# 从构建阶段复制 Python
COPY --from=builder $PYTHON_INSTALL_DIR $PYTHON_INSTALL_DIR

# 设置 PATH
ENV PATH="$PYTHON_INSTALL_DIR/bin:$PATH"

# -------------------------------------------------------
# 基础包 + 系统依赖
# -------------------------------------------------------
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        wget git gdebi-core \
#        build-essential  ocaml libnum-ocaml-dev \
		build-essential \
        ca-certificates \
        openjdk-17-jdk 


# -------------------------------------------------------
# 安装 srcML
# -------------------------------------------------------
	
# RUN wget https://github.com/srcML/srcML/releases/download/v1.1.0/srcml_1.1.0-1_ubuntu22.04_amd64.deb \
#     && gdebi srcml_1.1.0-1_ubuntu22.04_amd64.deb -n \
#     && rm srcml_1.1.0-1_ubuntu22.04_amd64.deb

# 目前先安装旧版本的srcml
RUN wget https://github.com/srcML/srcML/releases/download/v1.0.0/srcml_1.0.0-1_ubuntu20.04.deb \
	&& gdebi srcml_1.0.0-1_ubuntu20.04.deb -n 

# -------------------------------------------------------
# Python 库
# -------------------------------------------------------
RUN python3.11 -m pip install --no-cache-dir fuzzywuzzy python-Levenshtein \
    fastmcp requests pydantic

# -------------------------------------------------------
# 安装 Gumtree
# -------------------------------------------------------
ENV LANG=C.UTF-8
COPY gumtree /opt/gumtree
RUN /opt/gumtree/gradlew -p /opt/gumtree build \
    && ln -s /opt/gumtree/dist/build/install/gumtree/bin/gumtree /usr/bin/gumtree

# -------------------------------------------------------
# 拷贝你的 Python 项目
# -------------------------------------------------------
WORKDIR /app
# 正确复制 src 到 /app/src，而不是覆盖 /app
COPY src /app/src

COPY archsync_mcp.py /app/archsync_mcp.py

# 设置 Python 搜索路径
ENV PYTHONPATH="/app"

# 工作目录挂载路径
ENV WORK_DIR=/diff
RUN mkdir -p /diff
VOLUME /diff

EXPOSE 8013

CMD ["python3.11", "archsync_mcp.py"]
