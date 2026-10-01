# Proposal: miniprogram-ui-refine

## Why

上一轮已经把首页、导航和祈福接到浅色暖金令牌，但结果页仍有夜色底稿、合婚输入只有占位符、排盘失败只弹窗、清空最近命盘不确认。用户要求先把剩余需求写成文档，再按页迭代补完同一套界面。

## What

- 结果页、工具页、首页剩余表面接到现有令牌：补 `result-light` 漏覆盖、功能说明与宫位辅文 ≥32rpx、偏小控件接到 `--touch-min`；Tab 仍只滚动到分区；宫位六项保持现有字段 | refs: R-1, R-6, R-7, R-10, R-11 | verify: 浅色导航下结果页无夜色底稿色块；`.feature-note` / `.palace-aux` 等页面表类 ≥32rpx；点「紫微」滚到 `#section-ziwei` 且八字区仍在同页；每个宫位仍有宫名、地支、主星、辅星，选中宫仍有四化与大限
- 排盘、工具、祈福的字段错误写在对应字段下方；无命盘空状态保持现有引导；非字段失败仍用现有弹窗 | refs: R-4, R-8, R-9 | verify: 经度非法时错误出现在经度下方且日期/经度值不变、不跳转；无命盘时工具页仍有 empty-state 与「去排盘」；结果页无盘仍显示 empty
- 合婚双方姓名、地点、日期、时间、经度、子时补可见标签 | refs: R-3, R-12 | verify: 男方/女方每项输入上方有标签；缺一方日期时不调用 build、错误贴在该日期字段
- 清空最近命盘前弹出确认，取消则记录仍在 | refs: R-5 | verify: 点「清空记录」先确认；取消后 `recentCharts` 条数不变，且不删除 `latestChartResult`
- 需求先落在本 change 文档，批准后按 tasks 逐页改，不另开 loop 目录 | refs: R-2 | verify: `index.md` 已有 R-1–R-12；`tasks.md` 按页拆分；本变更不创建 `loop.md`

**Not in this change**: 不改算法、支付、运营接口、红圈入口集合；不合并结果页双文件、不改 Tab 显隐、不改十二宫列数、不加深色模式、不新建 FormError 组件、不另开 `/spec:loop` 目录、不归档其他 change。

## How

- 令牌色值与 `--touch-min` 不改（DEC-12）；结果页继续 base+light（DEC-2）；Tab 继续滚到 `#section-*`（DEC-1）；字号只改页面表类，不改全局 `.section-caption`。
- 错误文案复用 `.field-help` 修饰类与工具页 `.form-tip`/`namingHint`（C-7/C-8）；没有现成 hint 的页才用 data `fieldErrors`（DEC-9）；不写入 `consultation.initialData`，`tools.js` 不重声明 `onShow`。
- 按现有抛错文案映射字段；未映射的仍走 modal。合婚缺日期在 `runTool` 先拦，不改日历默认经度 120。字段失败不写 storage、不跳转。
- 清空确认复用祈福 `wx.showModal`（E-2），确认后只清 `recentCharts`。合婚只补 `field-label`（C-3）。
- 批准后按 tasks 逐页改（DEC-6）；同步改 `scripts/fixtures/miniprogram_core_check.js` 的非法日期断言；每页跑 `python scripts/check_miniprogram.py`。WXML 新增节点不用 `.join(`。

## Risk

- 改令牌会打到四页，所以本轮不改色值和 `--touch-min`；字号只改列出的页面类。
- `result-light` 漏一条选择器会露出夜色底稿；落地时按 base 选择器对账。
- `check_miniprogram.py` 看不见对比度；视觉对照开发者工具。夹具仍断言弹窗则会假失败，必须同轮改非法日期断言。回滚：还原本变更触及的 wxml/wxss/js 与该夹具。

<!-- APPROVED: 2026-10-01 02:55 -->
