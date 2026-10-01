# Research: miniprogram-ui-refine

## Practices

- Option A: 沿用本轮已落地的 `app.wxss` 语义令牌 + 结果页 `result-base` 结构 / `result-light` 浅色覆盖 | 不改信息架构，只补对比度、触控、表单反馈；代价是双文件覆盖漏选时仍露出夜色底稿
- Option B: 把结果页重写成单一浅色文件并改 Tab 为显隐分区 | 视觉干净；代价是违背 PRD「单页滚动分区」，回归面大于本轮 UI 细化
- Option C: 为字段错误新建通用组件/页面 | 工程上完整；项目无此先例，检索 `fieldError`/`formError` 为空，属于新实体

Key references: 无外部调研（内部既有小程序 UI 细化，决策空间全在仓库内）。未扫描 `admin/`、`backend/` 实现细节。

## Constraints

- 原生微信小程序，无新 npm 依赖 | 引入依赖会改变打包与审核面
- PRD §10.2「采用单页滚动分区展示」 | 结果 Tab 改成隐藏分区会丢掉一屏可读的八字+紫微
- `scripts/check_miniprogram.py` 只做 WXML 闭合、工程结构、固定日期样例 | 「检查通过」不能证明对比度或触控
- 首页 10 个红圈入口、4 列网格已交付 | 改列数会动已验收布局
- 合婚页日期/时间/经度/子时目前只有 placeholder | 违反「可见标签」时审核与无障碍都会漏字段名
- `submitChart` / `runTool` / 祈福创建用 `wx.showModal` 报错，页内无 `fieldErrors` | 用户看不到是哪一格错了
- `clearRecent` 无确认 | 误触直接清掉最近命盘
- `result-base.wxss` 仍是夜色底稿，`result-light.wxss` 只覆盖颜色 | 漏覆盖选择器会在浅色导航下露出深色块
- 功能说明 17rpx、宫位辅文 17rpx | 低于约 16px 正文下限，小屏难读
- 已有 5 个未归档 change 并行 | 本变更不得改算法、支付、运营接口
- 无 `spec/knowledge.md` | 事实以本调研的现状扫描为准

## Open [TBD]

## Decided

- [DEC-1] 结果 Tab 继续只滚动到 `#section-*`，不显隐分区 | source PRD §10.2 | decided from source
- [DEC-2] 保留 result-base 结构 + result-light 覆盖，不合并成单文件 | source [TBD-2] | auto | 现成模式；可逆：以后再合并文件
- [DEC-3] 首页功能网格保持 4 列，只提高字号与触控，不改列数 | source [TBD-3] | auto | 可逆：改 `grid-template-columns`
- [DEC-4] 排盘/工具/祈福的字段错误写在对应字段下方；非字段失败仍用现有 modal | source [TBD-4] | auto | 可逆：删 `fieldErrors` 绑定
- [DEC-5] 十二宫保持 4 列，只加高单元格与字号 | source [TBD-5] | auto | 可逆
- [DEC-6] 批准后由 `/spec:apply` 按 tasks 逐页落地，不另开 `/spec:loop` 目录 | source [TBD-6] | auto | 路径已知后 loop 会重复仪式；可逆：用户可改口要求 loop
- [DEC-7] 不做深色模式开关 | source [TBD-7] | auto | skip-or-minimal；需求源是浅色暖金细化
- [DEC-8] 旧 change 保持并行，本轮不归档 | source [TBD-8] | auto | 归档需用户说 archive
- [DEC-9] 字段错误用页面 data `fieldErrors` + 全局 `.field-error`，不新建组件 | source [TBD-9] | auto | 检索无现成载体；可逆：删 data 与样式
- [DEC-10] 解读顶栏保持展示、不加点击跳转 | source [TBD-10] | auto | skip；需求源未要求新交互
- [DEC-11] 继续用「灯 / 愿 / 乾坤」字印，不换成 emoji 或新图标库 | source 现状 ≥2 处且无反例 | decided from status quo
- [DEC-12] 色板保持赭红+暖金+米白，不采用 ui-ux-pro-max 默认粉 | source 已交付令牌与前轮 UI | decided from status quo
