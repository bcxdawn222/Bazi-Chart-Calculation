# Tasks: miniprogram-ui-refine

> deps omitted = sequential, follows the previous item

- [x] 1. 首页剩余字号与触控
  - [x] 1.1 功能说明接到 ≥32rpx；入口触控不低于令牌
- [x] 2. 排盘表单反馈
  - [x] 2.1 `submitChart` 字段错误复用 `.field-help` 修饰类显示在对应字段下
  - [x] 2.2 `clearRecent` 套用祈福删除确认，且不清 `latestChartResult`
- [x] 3. 工具页标签与错误
  - [x] 3.1 合婚双方六项补 `field-label`，占位符不再当标签
  - [x] 3.2 名号错误继续走 `namingHint`/`.form-tip`；其余模式错误贴在对应字段下
- [x] 4. 祈福字段错误
  - [x] 4.1 姓名/心愿校验失败写在字段下，删除确认保持原弹窗
- [x] 5. 结果页剩余表面
  - [x] 5.1 按 `result-base` 选择器补 `result-light` 漏项；宫位辅文 ≥32rpx；Tab 触控；不改滚动分区
- [x] 6. 回归（自动化、预览构建与模拟器视觉自验完成；未做真机或独立代理验收）
  - [x] 6.1 更新 `miniprogram_core_check.js` 非法日期断言后跑通 `python scripts/check_miniprogram.py`
  - [x] 6.2 固化字段错误、输入不变、缓存不变、清空取消/确认、Tab 滚动与空状态回归；补齐合婚/起卦日期时间错误与顶栏触控高度
  - [x] 6.3 最终版本微信预览构建成功并生成二维码与包体信息
  - [x] 6.4 模拟器正常、长文本与空状态截图验收；修复长名称压缩头像与状态标记，补充失败后通过的样式回归；空状态和长名称使用临时 AppData 夹具，未删除用户缓存，截图与限制已写入验收记录
