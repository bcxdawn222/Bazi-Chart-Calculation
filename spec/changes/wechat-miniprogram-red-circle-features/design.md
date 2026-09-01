# Design: 红圈功能扩展

## 页面与数据流

首页 `pages/index/index` 只负责入口与原有八字录入；工具入口统一进入 `pages/tools/tools?mode=<mode>`；祈福入口进入 `pages/prayer/prayer?mode=<mode>`。最近命盘通过 `latestChartResult` 本地存储提供给每日运势、财富运程和结果页。

## 模块边界

- `core/features/fortune.js`：每日运势、年度财富，输入结构化命盘。
- `core/features/divination.js`：时间起卦，输入阳历时间和事项。
- `core/features/compatibility.js`：双方命盘和结构化关系。
- `core/features/naming.js`：姓名与用户填写笔画的五格计算。
- `pages/tools/tools.js`：工具模式路由、输入绑定、错误提示和结果视图。
- `pages/prayer/prayer.js`：本地祈福/心愿记录的增删改状态。

## 接口契约

本轮没有远程后端接口。页面与核心模块使用 CommonJS 同步函数：

- `fortune.buildDaily(chart, YYYY-MM-DD)` 返回 `title/pillar/relation/summary/sections/evidence`。
- `fortune.buildYear(chart, year)` 返回 `title/pillar/relation/summary/wealthNote/months/evidence`。
- `divination.buildByTime(YYYY-MM-DD HH:mm, question)` 返回 `upper/lower/movingLine/lines/formula/note`。
- `compatibility.build(leftInput, rightInput)` 返回 `left/right/branchRelation/stemRelation/elements/summary/note`。
- `naming.calculate(surname, givenName, surnameStrokes, givenStrokes)` 返回 `characters/grids/threeTalents/note`。

错误均通过抛出带中文说明的 `Error` 交给页面弹窗；不返回空结果冒充成功。

## 状态存储

- `latestChartResult`：现有排盘结果。
- `recentCharts`：现有最近命盘。
- `localPrayerRecords`：祈福明灯和心愿阁本地记录，字段包括 `id/name/wish/note/type/status/createdAt`。

## 不变项

- 保留原生微信小程序、CommonJS、现有深色水墨鎏金视觉系统。
- 不引入旧 APK 网络接口、支付参数、账号或服务地址。
- 不加入参考图未圈出的功能。
