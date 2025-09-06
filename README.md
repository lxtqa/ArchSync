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
docker run --rm -v ./test:/diff archsync python3 gen_result.py old_loong.cc old_riscv.cc new_loong.cc -o result.cc
```

or

```bash
docker run --rm -v ./test:/diff archsync python3 gen_result.py old_loong.cc old_riscv.cc new_loong.cc
```

