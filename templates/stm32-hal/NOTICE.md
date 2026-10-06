# NOTICE

- 本模板来自 `projects/templet`（2026-10-06 快照）——全项目模板：软件(firmware 四层) + 硬件(hardware/) + 文档(docs/INDEX) + 工作区治理（_work/_archive + tools/tidy_workspace.py）。
- 参考板：立创·梁山派·天空星 F407（STM32F407VGT6）；固件工程名 `f407vgt6`，派生时由 `firmware/Tools/derive.py` 按新工程名改写。
- 派生实例：`projects/G2026`（已验证：build --clean-first 零告警 + selftest 全绿）。
- 派生方式：整项目 `tools/derive_project.py <新名> --go`；仅固件 `firmware/Tools/derive.py <新名> --dest <父目录> --verify`。
