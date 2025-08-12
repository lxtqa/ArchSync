FROM ubuntu:focal

ARG DEBIAN_FRONTEND=noninteractive
ENV TZ=GMT


# Install all required packages
RUN apt-get update \
	&& apt-get install -y --no-install-recommends openjdk-17-jdk wget git gdebi-core \
	build-essential ocaml libnum-ocaml-dev python3-pip python3-dev \
	ca-certificates


# Set locale
ENV LANG=C.UTF-8

# Install srcML
RUN wget https://github.com/srcML/srcML/releases/download/v1.0.0/srcml_1.0.0-1_ubuntu20.04.deb \
	&& gdebi srcml_1.0.0-1_ubuntu20.04.deb -n

RUN pip3 install fuzzywuzzy python-Levenshtein

# Install gumtree
COPY gumtree /opt/gumtree
RUN /opt/gumtree/gradlew -p /opt/gumtree build \
    && ln -s /opt/gumtree/dist/build/install/gumtree/bin/gumtree /usr/bin/gumtree

# Copy Python projects
COPY src /app
WORKDIR /app


RUN mkdir -p /diff
VOLUME /diff
EXPOSE 4567

CMD ["python3", "gen_result.py"]
