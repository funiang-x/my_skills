#!/usr/bin/env python3
"""从 templet 模板派生新项目：一条命令复制全格式骨架（软件+硬件+文档+工具+固件）。

用法:
  python tools/derive_project.py <新项目名>                  # dry-run，只打印方案
  python tools/derive_project.py <新项目名> --go             # 执行
  python tools/derive_project.py <新项目名> --dest D:/prj    # 指定父目录（默认与本模板同级）

随行内容:
  根骨架   AGENTS.md / CLAUDE.md / .gitignore / PROJECT.md / docs/INDEX.md（按新名改写）
  工具     tools/tidy_workspace.py
  固件     firmware/ 整树（除 build/_work/_archive/.git；CMake 工程名与 .ioc 文件名按新名改写）
  空目录   _work/ _archive/ hardware/
不随行:   产品内容（派生项目的编号文档从 01 写起）。
"""
import shutil, sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1]   # 模板工程根（templet）
FW_SKIP = shutil.ignore_patterns("build", ".git", "_work", "_archive", "__pycache__", "*.pyc")
COPY_ROOT = ["AGENTS.md", "CLAUDE.md", ".gitignore", "tools/tidy_workspace.py"]
COPY_FW_TEXT = ["firmware/CMakeLists.txt", "firmware/README.md", "firmware/AGENTS.md", "firmware/CLAUDE.md"]


def main():
    args = sys.argv[1:]
    go = "--go" in args
    args = [a for a in args if a != "--go"]
    dest = Path(args[args.index("--dest") + 1]) if "--dest" in args else SRC.parent
    name = next((a for a in args if not a.startswith("--")), "")
    if not name:
        print(__doc__)
        return
    root = dest / name
    print(f"[{'APPLY' if go else 'DRY-RUN'}] 派生 {name} → {root}")
    print("  根骨架   AGENTS.md CLAUDE.md README.md PROJECT.md .gitignore（按新名改写）")
    print("  工具     tools/tidy_workspace.py")
    print("  文档     docs/INDEX.md（空索引骨架）")
    print("  固件     firmware/ 整树（除 build；CMake 工程名/.ioc 按新名改写）")
    print("  空目录   _work/ _archive/ hardware/")
    if not go:
        print("(dry-run，加 --go 执行)")
        return
    if root.exists():
        print(f"⛔ {root} 已存在，停止")
        return

    # 根骨架（templet→新名）
    for f in COPY_ROOT:
        dst = root / f
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text((SRC / f).read_text(encoding="utf-8").replace("templet", name), encoding="utf-8")
    (root / "README.md").write_text(
        (SRC / "README.md").read_text(encoding="utf-8").replace("templet", name),
        encoding="utf-8")
    # PROJECT.md 最小骨架（阶段重置）
    (root / "PROJECT.md").write_text(f"""# {name}

阶段: ① 需求（约束冻结）

交付物: （尚未产出）

门禁基线: （固件 `fw.py build --clean-first` 后回填；EDA/其他按所用工具补）

待办: 1. 需求冻结——第一篇编号文档，写完登记 `docs/INDEX.md`

回退点: git 初始提交

下一步判据: 01 号需求文档定稿并登记 INDEX
""", encoding="utf-8")
    # INDEX 骨架
    (root / "docs" / "INDEX.md").parent.mkdir(parents=True, exist_ok=True)
    (root / "docs" / "INDEX.md").write_text(f"""# {name} · docs 索引

> 给 agent 的入口：接 {name} 的活，**先读本表**挑文档，打开原文读。
> 新增文档必在下面补一行（文档 | 内容 | 何时读）。

| 文档 | 内容 | 何时读 |
|---|---|---|
| （第一篇 01 写完后登记在这里） | | |
| `firmware/docs/00~13` | **固件四层工程规范手册**（分层/文件头/命名/注释/风格/Checklist/安全边界） | 写/改固件代码前按层查 |

## 与工程文件的边界

| 类别 | 真相源 |
|---|---|
| （按项目补：硬件事实=… / 应用参数=… / 数值复算=…） | |
""", encoding="utf-8")
    # 固件整树
    shutil.copytree(SRC / "firmware", root / "firmware", ignore=FW_SKIP)
    # 固件内 f407vgt6 → 新名（文本 + .ioc 文件名）
    for p in (root / "firmware").rglob("*"):
        if p.is_file() and p.suffix in (".md", ".txt", ".cmake", ".json", ".py", ".c", ".h", ".ld"):
            try:
                t = p.read_text(encoding="utf-8")
            except Exception:
                continue
            if "f407vgt6" in t:
                p.write_text(t.replace("f407vgt6", name), encoding="utf-8")
    old_ioc = root / "firmware" / "f407vgt6.ioc"
    if old_ioc.exists():
        old_ioc.rename(root / "firmware" / f"{name}.ioc")
    # 空目录
    for d in ("_work", "_archive", "hardware"):
        (root / d).mkdir(parents=True, exist_ok=True)
    print(f"完成。接下来（手工三件）：")
    print(f'  1. 固件验证：cd "{root}/firmware" && python Tools/fw.py build --clean-first && python Tools/fw.py test')
    print(f'  2. 重铺项目门：python C:/Users/funiang/.ai-skills/tools/skillman.py doors "{root}" --apply')
    print(f'  3. cd "{root}" && git init && git add -A && git commit -m "初始骨架（派生自 templet 模板）"')
    print(f"  然后写第一篇 hardware/01-需求冻结-<日期>.md 并登记 docs/INDEX.md")


if __name__ == "__main__":
    main()
