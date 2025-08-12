# README

### Clone

```bash
git clone --recurse-submodules https://github.com/lxtqa/ArchSync.git
```

### Build

Run the following command in the root directory of this project.

```
docker build -t archsync .
```

### Test & Run

Run the following command in the root directory of this project.

```bash
docker run --rm -v ./test:/diff archsync python3 gen_result.py 1.cc 2.cc 1_.cc -o 2_.cc
```

or

```bash
docker run --rm -v ./test:/diff archsync python3 gen_result.py 1.cc 2.cc 1_.cc
```

