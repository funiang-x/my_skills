---
name: build-cmake
description: "当需要配置或构建基于 CMake 的固件工程、探测构建环境（cmake / Ninja / 工具链）、列出 CMakePresets、或构建后定位 ELF/HEX/BIN 产物时使用。适用于任意 CMake 工程（不绑定厂商模板）：有 CMakePresets.json 优先用预设，没有就手动指定源码目录/构建目录/生成器/工具链。工程自带构建入口（如 Tools/fw.py、idf.py）时优先用工程的入口，本 skill 是通用兜底。"
agent_created: true
---

# 构建 CMake 工程

## [MUST] 开工前置

- 先跑 `--detect` 确认 cmake 与生成器在位；缺了就是 `environment-missing`，**不要硬拼命令**。
- **工程自己的构建入口优先**：工程根有 `Tools/fw.py` / `idf.py` / `Makefile` 一类入口时，先问它，本 skill 只做通用兜底。
- 产物要交接给烧录/调试时，**写绝对路径**进交接说明，别让下游猜。

## 适用场景

- 用 CMake 的 MCU/嵌入式工程：配置（configure）、重编译、确认产物。
- 构建前确认环境：cmake、生成器（Ninja/Make）、交叉工具链是否可用。
- 烧录或调试流程需要新的 ELF / HEX / BIN。

## 必要输入

- 源码目录（默认当前目录）；其余可自动探测。
- 可选：预设名、构建目录、生成器、构建类型（Debug/Release）、工具链文件、目标名。

## 自动探测（优先级）

1. 有 `CMakePresets.json` → 优先用 `--preset`（先 `--list-presets` 看名字）。
2. 没有预设 → `--build-dir`（默认 `build/`）+ 可选 `--generator` / `--build-type` / `--toolchain`。
3. 生成器优先 Ninja，其次宿主机已有的 Make。

## 命令

```bash
S=scripts/cmake_builder.py        # 本 skill 的执行入口（纯标准库）

python $S --detect                                   # 环境探测
python $S --list-presets --source /path/to/project   # 列预设
python $S --source /path/to/project --preset Debug   # 预设：配置 + 构建
python $S --source . --build-dir build --build-type Debug --jobs 8
python $S --source . --preset Debug --no-configure   # 只构建（不重新配置）
python $S --source . --preset Debug --target app     # 只构建某个目标
```

## 失败分流（退出码）

| 码 | 分类 | 怎么办 |
|---|---|---|
| 0 | 成功 | 产物路径已按 ELF > HEX > BIN 排序列出 |
| 2 | `environment-missing` | 装 cmake / 生成器 / 工具链，见上表 `--detect` 输出 |
| 3 | `project-config-error` | 预设损坏 / 工具链文件缺失 / 生成器不可用 / 源码目录不存在 |
| 4 | `build-failed` | 看编译输出的第一处 error，不要先怀疑链接 |
| 5 | `artifact-missing` | 构建成功但没有 ELF/HEX/BIN——可能只构建了库目标，或 `--target` 选错 |

## 输出约定

- 打印实际执行的完整命令、构建目录、首选产物（绝对路径 + 体积）。
- 交接：烧录 → `flash-jlink`；GDB 调试 → `debug-jlink`。