# 界面截图：miniprogram-ui-refine

以下为微信开发者工具 iPhone X 模拟器实际画面，由主智能体操作与自验。正常、错误态使用真实页面操作；标有“夹具”的状态仅通过 AppData 修改临时显示数据，不删除缓存，不冒充自然端到端流程。未做手机真机或独立代理验收。

| 页面 | 设计与需求来源 | 完整截图路径 | 状态与观察 |
|---|---|---|---|
| 首页入口 | R-1/R-7，现有色板与四列布局 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-home.png` | 正常；四列入口，说明能显示；也是工具页“去排盘”返回后的页面 |
| 首页经度错误 | R-4/R-9 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-home-longitude-error.png` | 错误；经度 200 与日期原值保留，错误贴在经度下方 |
| 首页最近命盘 | R-5 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-home-recent-before.png` | 正常；确认前页面 data 为两条记录 |
| 首页清空弹窗 | R-5 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-home-clear-confirm.png` | 确认；取消/确定可见，未执行确定 |
| 首页取消清空 | R-5 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-home-clear-cancel.png` | 取消；列表仍在，页面 data 仍为两条 |
| 合婚男方资料 | R-3/R-12 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-compat-normal.png` | 正常；姓名、地点、日期、时间、经度、子时六项有标签 |
| 合婚女方资料 | R-3/R-12 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-compat-female.png` | 正常；六项标签与提交按钮可见 |
| 合婚姓名错误 | R-4/R-12 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-compat-error.png` | 错误；男方姓名下方显示提示，无总弹窗 |
| 祈福表单 | R-1/R-4 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-prayer-normal.png` | 正常；标签、输入区与按钮完整 |
| 祈福字段错误 | R-4/R-9 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-prayer-errors.png` | 错误；姓名、心愿分别在字段下报错，未遮挡其他内容 |
| 结果概览 | R-1/R-6/R-10 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-result-overview.png` | 正常；浅色顶部与八字表，长名称夹具已恢复 |
| 十二宫 | R-7/R-10/R-11 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-result-palaces.png` | 多行；十二宫仍为四列，辅星与亮度换行，无观察到跨格重叠 |
| 宫位详情 | R-11 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-result-detail.png` | 正常；福德酉宫，武曲七杀、辅星槽、武曲化禄、大限及四化分布可见 |
| 紫微后返回八字 | R-10 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-result-bazi-return.png` | 交互；点击八字只滚动，四柱、大运流年仍在同页 |
| 解读分区 | R-1/R-10 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-result-analysis.png` | 正常；五项内容与底部说明在浅色分区中显示 |
| 结果页长名称 | R-1/R-7，长文本压力检查 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-result-long-name-fixture.png` | 长文本夹具；二十字合成名称，修复后头像不压缩、状态不分行；检查后恢复原值 |
| 结果页无命盘 | R-8 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-result-empty-fixture.png` | 空状态夹具；临时 hasResult=false，提示完整；截图后恢复 true |
| 运势页有命盘 | R-8 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-tools-normal.png` | 正常；卸载空状态夹具后再次进入，能读取缓存命盘 |
| 运势页无命盘 | R-8 | `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\verified-tools-empty-fixture.png` | 空状态夹具；临时 hasChart=false，提示、“去排盘”与禁用按钮显示；点击文字可返回首页 |

## 复现与限制

- 长名称夹具内容为“长文本验收样例甲乙丙丁戊己庚辛壬癸测试盘”，只改结果页临时 chartName，不写入缓存。
- 空状态只改临时 hasResult/hasChart，不移除 latestChartResult；结果页立即恢复，工具页导航卸载后重新进入并确认正常状态。
- 清空弹窗只验证取消路径；确定分支保留自动化夹具覆盖，不执行真实删除。
- 截图反映 iPhone X 模拟器，不外推为手机真机或其他屏宽验证。
- 同一逻辑截图更新原文件，长名称截图为修复后的最终状态。

## 未纳入的历史产物

目录 `F:\企业微信\20260816\算命\spec\changes\miniprogram-ui-refine\screens\` 内原有的 live、devtools 与 win 前缀产物保留原状；其中存在重复首页、连接失败或其他窗口画面，不纳入本次结论，也不批量加入提交。此前项目信任提示截图不属于应用页面证据。
