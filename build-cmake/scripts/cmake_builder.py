#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""cmake_builder.py — build-cmake skill 的执行入口（纯标准库，零第三方依赖）。

用法：
    python cmake_builder.py --detect
    python cmake_builder.py --list-presets --source .
    python cmake_builder.py --source . --preset Debug
    python cmake_builder.py --source . --build-dir build --build-type Debug --jobs 8
退出码：0=成功 2=环境缺失 3=配置失败 4=构建失败 5=未找到产物
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:                                                # noqa: BLE001
    pass

ART_RANK = {".elf": 0, ".axf": 0, ".hex": 1, ".bin": 2}


def run(cmd, cwd=None):
    print("$ " + " ".join(str(c) for c in cmd), flush=True)
    return subprocess.run([str(c) for c in cmd], cwd=cwd)


def tool_version(name):
    p = shutil.which(name)
    if not p:
        return None, ""
    try:
        out = subprocess.run([p, "--version"], capture_output=True, text=True,
                             timeout=20).stdout
        ver = (out.strip().splitlines() or [""])[0]
    except Exception:                                            # noqa: BLE001
        ver = ""
    return p, ver


def cmd_detect():
    ok = True
    print("构建环境探测：")
    for name, required, hint in (
            ("cmake", True, "https://cmake.org/download/"),
            ("ninja", False, "pip install ninja / 系统包管理器"),
            ("make", False, "随工具链或系统提供"),
            ("arm-none-eabi-gcc", False, "嵌入式交叉工具链（工程用它时必需）"),
            ("gcc", False, "主机编译器（PC 单测常用）")):
        path, ver = tool_version(name)
        if path:
            print("  ✓ %-18s %-28s %s" % (name, ver, path))
        else:
            print("  %s %-18s 未找到——%s" % ("✗" if required else "·", name, hint))
            ok = ok and not required
    return 0 if ok else 2


def load_presets(src: Path):
    """→ (CMakePresets 数据, 文件路径)；没有或解析失败 → (None, None)。"""
    for name in ("CMakePresets.json", "CMakeUserPresets.json"):
        p = src / name
        if p.is_file():
            try:
                return json.loads(p.read_text(encoding="utf-8")), p
            except Exception as e:                               # noqa: BLE001
                print("✗ %s 解析失败：%s" % (name, e))
                return None, None
    return None, None


def preset_names(data, key):
    return [x.get("name") for x in (data or {}).get(key, []) if x.get("name")]


def preset_binary_dir(src: Path, data, name: str):
    """取配置预设的 binaryDir（只做 ${sourceDir} 字面替换，不算继承——够用）。"""
    for cp in (data or {}).get("configurePresets", []):
        if cp.get("name") == name and cp.get("binaryDir"):
            return Path(str(cp["binaryDir"]).replace("${sourceDir}", str(src)))
    return None


def scan_artifacts(build_dir: Path):
    found = [p for p in build_dir.rglob("*")
             if p.is_file() and p.suffix.lower() in ART_RANK
             and "cmakefiles" not in str(p).lower()]
    found.sort(key=lambda p: (ART_RANK[p.suffix.lower()], -p.stat().st_mtime))
    return found


def main():
    ap = argparse.ArgumentParser(description="CMake 配置 / 构建 / 产物定位（build-cmake skill）")
    ap.add_argument("--detect", action="store_true", help="探测构建环境后退出")
    ap.add_argument("--list-presets", action="store_true", help="列 CMakePresets 后退出")
    ap.add_argument("--source", default=".", help="源码目录（默认当前目录）")
    ap.add_argument("--preset", help="CMakePresets 预设名")
    ap.add_argument("--build-dir", help="构建目录（无预设时用，默认 <source>/build）")
    ap.add_argument("--generator", help="如 Ninja / Unix Makefiles")
    ap.add_argument("--build-type", help="Debug / Release / RelWithDebInfo")
    ap.add_argument("--toolchain", help="CMAKE_TOOLCHAIN_FILE 路径")
    ap.add_argument("--target", help="只构建该目标")
    ap.add_argument("--jobs", type=int, help="并行任务数")
    ap.add_argument("--no-configure", action="store_true", help="跳过 configure，只 build")
    a = ap.parse_args()

    if a.detect:
        return cmd_detect()
    src = Path(a.source).resolve()
    if not src.is_dir():
        print("✗ 源码目录不存在：%s" % src)
        return 3

    data, ppath = load_presets(src)
    if a.list_presets:
        if not data:
            print("· 没有 CMakePresets.json —— 走 --build-dir 手动模式")
            return 0
        for key, label in (("configurePresets", "配置预设"), ("buildPresets", "构建预设")):
            print("%s（%s）：%s" % (label, ppath.name, ", ".join(preset_names(data, key)) or "无"))
        return 0

    if not shutil.which("cmake"):
        print("✗ environment-missing：找不到 cmake")
        return 2

    if not a.no_configure:
        if a.preset:
            cmd = ["cmake", "--preset", a.preset]
        else:
            bd = Path(a.build_dir) if a.build_dir else src / "build"
            cmd = ["cmake", "-S", str(src), "-B", str(bd)]
            if a.generator:
                cmd += ["-G", a.generator]
            if a.build_type:
                cmd += ["-DCMAKE_BUILD_TYPE=" + a.build_type]
            if a.toolchain:
                cmd += ["-DCMAKE_TOOLCHAIN_FILE=" + a.toolchain]
        if run(cmd, cwd=src).returncode != 0:
            print("✗ 配置失败——查预设 / 工具链文件 / 生成器")
            return 3

    if a.preset:
        bdir = preset_binary_dir(src, data, a.preset) or (src / "build")
        if a.preset in preset_names(data, "buildPresets"):
            cmd = ["cmake", "--build", "--preset", a.preset]
        else:
            cmd = ["cmake", "--build", str(bdir)]
    else:
        bdir = Path(a.build_dir) if a.build_dir else src / "build"
        cmd = ["cmake", "--build", str(bdir)]
    if a.target:
        cmd += ["--target", a.target]
    if a.jobs:
        cmd += ["--parallel", str(a.jobs)]
    if run(cmd, cwd=src).returncode != 0:
        print("✗ 构建失败——看输出的第一处 error")
        return 4

    arts = scan_artifacts(bdir) if bdir.is_dir() else []
    if not arts:
        print("· 构建成功，但 %s 下没有 ELF/HEX/BIN 产物（可能只构建了库目标）" % bdir)
        return 5
    print("\n产物（ELF > HEX > BIN；首选在最前）：")
    for p in arts[:8]:
        print("  %s  (%.1f KB)" % (p, p.stat().st_size / 1024))
    print("\n首选产物：%s" % arts[0])
    print("→ 烧录交给 flash-jlink；GDB 调试交给 debug-jlink")
    return 0


if __name__ == "__main__":
    sys.exit(main())