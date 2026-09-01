# Verification Ledger: wechat-miniprogram-reuse

## Open Acceptance Conditions

| ID | Severity | Status | Finding | Evidence |
|---|---|---|---|---|
| V-1 | major | external | 恢复源码与本地断言尚未证明所有历法、紫微及节气时刻分支和原 APK 完全一致，需要客户基准样例终验。 | `F:\企业微信\20260816\算命\docs\final-reverse-analysis-report.md` 记录 native/混淆恢复限制；当前起运状态在 `F:\企业微信\20260816\算命\miniprogram\core\bazi.js` 明确标注节气分钟待样例核验。 |
| V-10 | medium | external | 当前使用 `touristappid`，开发者工具日志没有在最终文件变动后给出完整输入、结果页和真机流程证据。 | `F:\企业微信\20260816\算命\miniprogram\project.config.json` 使用 `touristappid`；`F:\企业微信\20260816\算命\logs\open-miniprogram.log` 证明工程重开成功，但 `F:\企业微信\20260816\算命\logs\wechat-devtools-raw.log` 没有最终 `webview page ready`。 |

## Round 0 - Proposal Critique

| ID | Severity | Status | Finding | Resolution |
|---|---|---|---|---|
| V-1 | major | external | 部分算法分支可能位于 native、混淆代码或旧服务端。 | 本地实现只迁移可追溯规则，结果保留可信度说明，客户样例作为外部验收条件。 |
| V-2 | medium | resolved | 缺少可执行的小程序工程检查入口。 | 已增加 `F:\企业微信\20260816\算命\scripts\check_miniprogram.py`、`F:\企业微信\20260816\算命\scripts\check_miniprogram.sh` 和核心 fixture。 |

## Round 1 - Independent Verification

第一轮报告：`F:\企业微信\20260816\算命\logs\independent-verifier.md`

| ID | Severity | Status | Finding | Resolution |
|---|---|---|---|---|
| V-3 | blocker | resolved | 紫微大限按绝对地支下标起排。 | 改为以命宫为相对起点；固定样例命宫大限为 `6-15`。 |
| V-4 | blocker | resolved | 年柱、月柱使用固定日期切换。 | 增加 `F:\企业微信\20260816\算命\miniprogram\core\solar_terms.js`，按恢复源码的当年节气日期切换。 |
| V-5 | major | resolved-with-limit | 大运起运年龄固定为 3 岁。 | 改为按出生时刻到顺逆方向节气的距离折算；节气时刻精度保留为 V-1。 |
| V-6 | major | resolved | 紫微流年字段缺失。 | 增加紫微流年命宫字段并由结果页展示。 |
| V-7 | medium | resolved | 非法日期、时间、农历日数和经度会被静默归一化。 | 增加严格输入校验和自动拒绝断言。 |
| V-8 | medium | resolved | 自动检查未覆盖核心回归规则。 | 增加命宫大限、节气切柱、动态起运、紫微流年、非法输入和 1900 年范围断言。 |

## Round 2 - Scoped Reverification

第二轮报告：`F:\企业微信\20260816\算命\logs\independent-verifier-round2.md`

独立复核确认 V-3 至 V-8 的算法修复通过，并确认：

- 2021 年立春日为 2 月 3 日，年柱由 `庚子` 切为 `辛丑`。
- 2021 年惊蛰日为 3 月 5 日，月柱由 `庚寅` 切为 `辛卯`。
- 两个出生日期的起运月数分别为 6 和 62，不再固定。
- 1900 年节气计算被拒绝，同时农历 1900 年数据仍可双向转换。

| ID | Severity | Status | Finding | Resolution |
|---|---|---|---|---|
| V-9 | medium | resolved | 自动检查未实际执行输入页提交、错误弹窗和结果页紫微流年绑定。 | `F:\企业微信\20260816\算命\scripts\fixtures\miniprogram_core_check.js` 模拟 `Page/getApp/wx`，调用 `submitChart` 与 `onLoad`，输出 `indexFlowValidated=true`、`resultPageLiunianBound=true`。 |
| V-10 | medium | external | 最终版本缺少正式 AppID 下的页面就绪和真机交互证据。 | 工程已通过 `python scripts\open_miniprogram.py --reopen` 成功关闭并重开；正式 AppID/真机流程保留为外部验收条件。 |

修复复核记录：

- `F:\企业微信\20260816\算命\logs\independent-verifier-round2-fix1.md`
- `F:\企业微信\20260816\算命\logs\independent-verifier-round2-fix2.md`

两次隔离复核环境分别因未继承 Node PATH、无权访问 `C:\Program Files\nodejs\node.exe` 而未完成 Node 命令；这两份报告没有发现新的业务代码错误。按 Spec 的两轮自动修复上限停止重复环境尝试，以当前实际开发环境的最终执行结果为交付证据。

## Final Local Verification

2026-08-18 20:16:14 至 20:16:15 执行：

```powershell
python scripts\check_miniprogram.py
```

结果：

- 基础文件 10 项齐全。
- 2 个页面路由完整。
- 2 个 WXML 模板结构有效。
- 9 个 JavaScript 文件通过 `node --check`。
- 599 组常规日期、55 组闰月往返一致。
- 固定样例四柱为 `己巳 丙子 丙寅 甲午`，火六局、命宫未、紫微在丑、命宫大限 `6-15`。
- 非法输入拒绝数为 6，1900 年节气外推被拒绝。
- 节气边界计数为 2，起运年龄随日期变化。
- `resultPageLiunianBound=true`、`indexFlowValidated=true`。

最终日志：`F:\企业微信\20260816\算命\logs\check-miniprogram.log`

## Acceptance State

本地核心实现和自动验证完成。当前变更等待用户验收；不自动归档。
