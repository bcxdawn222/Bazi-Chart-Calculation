---
change: android-apk-runtime-unpack
round: 1
date: 2026-08-16
stage: verify
conclusion: pass_with_open_findings
issues: { critical: 0, major: 1, minor: 1, open: 1 }
---

# Verify: android-apk-runtime-unpack

## Completeness

- `proposal.md` 包含 `Why`、`What`、`How`、`Risk` 四个必需段落，并保留 `<!-- APPROVED: 2026-08-16 17:06 -->`。
- `tasks.md` 中所有任务均已标记为 `[x]`，未完成任务数量为 0。
- 运行时导出、源码与资源恢复、native 证据整理和报告均已生成。
- `base1.apk` 仅作为静态对照样本，未纳入主样本的运行时脱壳链路。

## Correctness

- 执行 `py -3.13 -m py_compile scripts\runtime_unpack.py scripts\recover_sources.py scripts\frida_dump_dex.py scripts\frida_inspect_runtime.py`，返回码为 `0`。
- 对原始样本 `E:\WXWork\1688856420768484\Cache\File\2026-08\base.apk` 重新计算 SHA-256，结果为 `df0d5bfe1505886c3e258f3dc1bcdb4154742a49890310669326f290e5821f46`，与运行时任务清单一致。
- 运行时清单 `F:\企业微信\20260816\算命\artifacts\runtime\20260816T170727Z-df0d5bfe1505\manifest.json` 状态为 `captured`，记录 8 个带大小、来源和 SHA-256 的 artifact；包含 `.jiagu` native 文件、`base.vdex`、`base.odex`、`libmsaoaidsec.so`、进程映射和 logcat。
- 源码恢复清单 `F:\企业微信\20260816\算命\artifacts\recovered\20260816T170727Z-df0d5bfe1505\source-recovery.json` 状态为 `recovered`；10 次 JADX 返回码均为 `0`，apktool 返回码为 `0`，生成 34 个 Java 文件和 11,604 个资源文件。
- 当前恢复出的 Java 主要是 `com.stub.StubApp`、`com.tianyu.util.*` 和辅助壳类，证据支持其属于壳近似源码；未将其标记为业务工程源码。
- Frida 内存扫描捕获多个重复的 4-class 壳 DEX 和一个 1-class 辅助 DEX，尚未捕获包含业务 class 的独立 DEX；该结果与 Android 17 `x86_64` AVD 上的 ARM native 加载异常、缺失 `libjgdtc.so`、页对齐不兼容和主进程退出日志相符。

## Coherence

- 运行时、恢复和报告路径均位于项目目录 `F:\企业微信\20260816\算命\` 下，原始 APK 保持只读。
- `proposal.md` 已明确允许在 ABI 阻塞时保留证据并转入静态壳数据分析；因此业务 DEX 未捕获被记录为阻塞结果，没有通过空 dump 冒充成功。
- 工具版本、任务清单、运行时清单、恢复清单和报告之间的样本哈希一致。
- 独立 spec-verifier：`not run: 当前工具端未提供调度接口`。本轮未将主会话自审冒充为独立代理结论。

## Findings

| ID | Severity | Location | Finding | Status | Rounds |
|----|----------|----------|---------|--------|--------|
| V-1 | major | Android 17 `x86_64` AVD | ARM native 页面对齐、缺失库和进程退出阻断业务 DEX 导出；当前产物为壳 DEX、native、资源和运行日志。 | open | 1 |
| V-2 | minor | Frida runtime hook | Java bridge 不可用，ART 注册符号未在 Frida 可见导出表中出现；硬编码偏移试验导致进程崩溃后已移除，后续采用无侵入内存扫描和静态符号证据。 | documented | 1 |

## Evidence

- 脚本语法检查：`py -3.13 -m py_compile ...`，返回码 `0`。
- 样本完整性：`E:\WXWork\1688856420768484\Cache\File\2026-08\base.apk` SHA-256 为 `df0d5bfe1505886c3e258f3dc1bcdb4154742a49890310669326f290e5821f46`。
- 运行时产物：`F:\企业微信\20260816\算命\artifacts\runtime\20260816T170727Z-df0d5bfe1505\manifest.json`，状态 `captured`。
- 恢复产物：`F:\企业微信\20260816\算命\artifacts\recovered\20260816T170727Z-df0d5bfe1505\source-recovery.json`，状态 `recovered`。
- 报告：`F:\企业微信\20260816\算命\docs\runtime-unpack-report.md`。
