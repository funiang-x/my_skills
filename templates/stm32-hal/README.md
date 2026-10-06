# templet — 全项目模板（软件 + 硬件 + 文档）

> 新项目从这里派生：`python tools/derive_project.py <新项目名> --dest <父目录> --go`
> （自动带走：治理约定 + 工具 + VS Code 配置 + 固件四层工程树，固件工程名按新项目改写。）

## 目录导览

| 位置 | 内容 | 规则 |
|---|---|---|
| `docs/` | 产品文档（`INDEX.md` 唯一索引） | 编号文档 + INDEX 登记 |
| `hardware/` | 硬件编号文档 + `data/`（被引用数据） | 白名单制，见 AGENTS.md |
| `firmware/` | STM32F407 四层工程（CubeMX + GCC/Ninja + J-Link + RTT），门禁 `firmware/Tools/fw.py` | 内部规矩见 `firmware/AGENTS.md`（R1~R6） |
| `tools/` | `tidy_workspace.py`（工作区归位）· `derive_project.py`（本项目即模板） | 可复用工具的家 |
| `_work/` | AI 会话临时产物唯一落点（git 忽略，14 天自动过期） | — |
| `_archive/` | 历史证据冻结区（git 忽略） | 清单 `MANIFEST.md` 自动生成 |

## 两条入口

- **人读本文件** + [`PROJECT.md`](PROJECT.md)（阶段/基线）
- **AI 读 [`AGENTS.md`](AGENTS.md)**（工作区落点 [MUST]）→ firmware 内部再读 [`firmware/AGENTS.md`](firmware/AGENTS.md)

## 快速上手（固件）

```bash
cd firmware
python Tools/fw.py env && python Tools/fw.py build --clean-first && python Tools/fw.py test
```

## 文档规范（[MUST]）

1. 新文档编号**接续目录最大号**，永不复用；文件名 `NN-主题-YYYYMMDD.md`。
2. H1 `# NN · 标题（YYYY-MM-DD）`；开头写清性质（决策/审计/讲解/拍板）与状态（已执行/待审/未验证）。
3. 写完必到 `docs/INDEX.md` 登记——没登记=不存在。
4. **引用即合同**：文档引用的本地路径必须真实存在。
5. 三态口径：凡"上板/实测"结论一律先标**未验证**，验证后注日期与证据。
