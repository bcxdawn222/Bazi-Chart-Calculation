# Index: miniprogram-ui-refine

Requirement source: 用户 2026-08-28「继续帮我改ui 继续细化ui /ui-ux-pro-max」；用户 2026-10-01「把所有需求先沉淀成md 然后用loop去自主迭代 loop内做workflow」；用户挂载的 ui-ux-pro-max 行为条款；`docs/八字紫微排盘产品PRD.md` 中仍未落地的展示/报错条款。

## Requirements

- R-1: 继续帮我改ui 继续细化ui /ui-ux-pro-max | source: 用户 2026-08-28
- R-2: 把所有需求先沉淀成md 然后用loop去自主迭代 loop内做workflow | source: 用户 2026-10-01
- R-3: Visible label per input (not placeholder-only) | source: ui-ux-pro-max §8 Forms
- R-4: Show error below the related field | source: ui-ux-pro-max §8 Forms
- R-5: Confirm before destructive actions | source: ui-ux-pro-max §8 Forms
- R-6: Min size 44×44pt (Apple) / 48×48dp (Material) | source: ui-ux-pro-max §2 Touch
- R-7: Minimum 16px body text on mobile | source: ui-ux-pro-max §5 Layout
- R-8: 缺少命盘或输入错误时显示明确空状态和错误提示。 | source: PRD §10.3
- R-9: 输入错误必须明确提示，不得静默修正为其他日期。 | source: PRD §12
- R-10: 采用单页滚动分区展示。 | source: PRD §10.2
- R-11: 每个宫位显示宫名、地支、主星、辅星、四化和大限。 | source: PRD §7.3
- R-12: 两方信息均完整时可生成；任一方缺失时阻止提交并提示字段。 | source: PRD §9.4

## Assets

- A-1: `miniprogram/app.wxss` 语义令牌、`.field-label`、`.gold-btn`、`.chevron`、`.segmented` | use: extend | impact: 四页都读这些变量；改 token 会同时改首页、结果、工具、祈福
- A-2: `pages/index/index.js` `submitChart` / `clearRecent` | use: extend | impact: 首页提交与最近命盘；`clearRecent` 的调用方只有首页
- A-3: `pages/index/index-home.wxss`、`index-form.wxss`、`index.wxml` | use: extend | impact: 仅首页
- A-4: `pages/result/result-base.wxss` + `result-light.wxss` + `onTabChange` | use: extend | impact: 仅结果页；覆盖漏选会露出夜色底稿
- A-5: `pages/tool-shell.wxss`、`pages/tools/tools.wxml`、`tools.js` `runTool` | use: extend | impact: 运势/求卦/合婚/名号/咨询共一页
- A-6: `pages/prayer/prayer.js` `createRecord` / `deleteRecord` 的 `wx.showModal` | use: reuse | impact: 祈福页删除确认已是破坏性确认母版
- A-7: `pages/prayer/prayer.wxml` / `prayer.wxss` | use: extend | impact: 仅祈福页
- A-8: `scripts/check_miniprogram.py` | use: reuse | impact: 结构与日期样例；不能当视觉验收
- A-9: 新建通用 FormError 组件 | use: rejected: 全库无同类组件，DEC-9 用页面 data

## Exemplars

- E-1: 剩余页的标签、输入、主按钮 → `pages/index/index.wxml` 表单区 + `app.wxss` 令牌（已有可见标签与 88rpx 输入）
- E-2: 破坏性确认 → `prayer.js` `deleteRecord` 的 `wx.showModal`

## Carriers

- C-1: 设计令牌 / 触控最小高度 → `app.wxss` `--touch-min` / `--color-*` | reuse
- C-2: 结果分区跳转 → `result.wxml` `id="section-*"` + `onTabChange` | reuse
- C-3: 合婚双方字段 → `tools.js` `leftName`/`leftDate`/`leftTime`/`leftLocation`/`leftZiHourMode` 及 right 对称字段 | reuse — 只补标签，不改字段名
- C-4: 最近命盘清空 → `index.js` `clearRecent` | extend — 套用 E-2 确认
- C-5: 字段级错误文案 → NOT FOUND（搜过 `miniprogram/**` 的 `fieldError`/`formError`/`error-text`，无命中） | minting required — 页面 data `fieldErrors` + `app.wxss` `.field-error`
- C-6: 非字段失败提示 → 现有 `wx.showModal`（`submitChart` / `runTool` / `createRecord`） | reuse
- C-7: 工具页提示槽 → `namingHint` + `.form-tip` | reuse — 名号错误已走此槽
- C-8: 首页字段下方说明槽 → `.field-help` | extend — 经度下已有常驻说明，错误用修饰类，不新建全局 `.field-error`
