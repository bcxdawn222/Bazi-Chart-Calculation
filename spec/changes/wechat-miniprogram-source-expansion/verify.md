# Verification Ledger: wechat-miniprogram-source-expansion

## Round 0 - Proposal Critique

由于当前运行环境没有独立 critic agent，Round 0 按 necessity 与 regression-compat 两个固定视角分别审查，并保留该限制。

| ID | Severity | Status | Finding | Resolution |
|---|---|---|---|---|
| V-1 | major | open | 均时差实现会改变跨日和子时边界结果，但当前没有客户基准样例证明最终口径。 | 已增加 1990-01-01 00:05、东经 80 度样例，验证修正至 1989-12-31 21:21 并标记跨日；客户样例继续作为外部验收条件。 |
| V-2 | major | fixed(r0) | 参考文档列出旺衰、喜用神和格局，但恢复源码只确认到部分页面或结果对象，直接纳入本次实现会产生不可证伪结果。 | proposal 已将这些内容移到后续样例驱动阶段。 |
| V-3 | medium | fixed(r0) | 新增字段如果直接堆入 `bazi.js` 和 `ziwei.js`，会增加文件体积和回归范围。 | design 已拆分 `solar_time.js`、`bazi_details.js` 和 `ziwei_details.js`，现有入口只追加字段。 |
| V-4 | medium | fixed(r1) | 星曜亮度规则可能只有布局字段而没有完整常量表。 | 已从恢复源码中的主星/辅星亮度表提取固定映射，并通过 22 条亮度明细与 12 个宫位关系断言；未命中的星曜保持空缺。 |

## Round 1 - Apply Verification

| ID | Severity | Status | Evidence |
|---|---|---|---|
| A-1 | pass | fixed | python scripts\check_miniprogram.py 全部通过；工程文件、JSON 与路由、WXML、12 个 JavaScript 文件和核心样例均通过。 |
| A-2 | pass | fixed | 核心样例覆盖 599 组常规日期、55 组闰月往返、非法日期/经度、早晚子时、节气切换、动态起运、输入提交和结果页字段绑定。 |
| A-3 | pass | fixed | 固定样例真太阳时为 1990-01-01 11:41；经度修正 -14.4 分钟、均时差 -3.61 分钟、总修正 -18.01 分钟；跨日样例修正至 1989-12-31。 |
| A-4 | pass | fixed | 固定样例包含 9 条藏干、4 条纳音、五行统计和 22 条紫微亮度明细；12 个宫位均有对宫与三合关系。 |
| A-5 | pass | fixed | 已在微信开发者工具工程 `F:\企业微信\20260816\算命\miniprogram` 中完成真实编译，问题面板为 0 个问题。随后通过 `ws://127.0.0.1:9420` 调试通道提交 `1990-01-01 12:00`、经度 `116.40`、真太阳时开启的样例，实际进入 `pages/result/result`；读取到 `hasResult=true`、真太阳时总修正 `-18.01` 分钟、4 条八字明细、12 个紫微宫位、亮度字段和三方四正字段。当前 Nightly 版本在结果页调用 `App.captureScreenshot` 时挂起，因此未将不存在的截图文件作为证据。 |

## Round 2 - Runtime Apply Verification

本轮使用已打开的微信开发者工具和真实小程序运行时完成页面验收；调试通道仅用于读取真实页面状态，不替换业务逻辑。

| ID | Severity | Status | Evidence |
|---|---|---|---|
| R-1 | major | pass | 当前工程真实编译后，首页提交样例成功触发 `submitChart`，页面栈从 `pages/index/index` 进入 `pages/result/result`。 |
| R-2 | major | pass | 结果页真实数据包含 `time.correction`、`baziDetails`、`palaces[].brightnessText` 和 `palaces[].relatedText`；样例读取到 4 条八字明细、12 条宫位关系和 22 条亮度明细。 |
| R-3 | medium | pass | 结果页样例显示真太阳时为 `1990-01-01 11:41`，经度修正 `-14.4` 分钟，均时差 `-3.61` 分钟，总修正 `-18.01` 分钟。 |
| R-4 | medium | noted | Nightly 版本的 `App.captureScreenshot` 在结果页请求挂起，未生成 `F:\企业微信\20260816\算命\tmp\miniprogram-runtime-result.png`；此项为工具截图接口限制，页面编译和数据交互验收已完成。 |
