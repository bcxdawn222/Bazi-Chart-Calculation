# Research: 红圈功能扩展

## 现状

- 当前工程为原生微信小程序，核心排盘逻辑位于 `miniprogram/core`，首页和结果页位于 `miniprogram/pages`。
- 现有基础排盘已经包含八字、紫微、真太阳时、十神、藏干、纳音、运势和基础解读。
- 参考 APK 恢复源码中可定位到每日运势、时间起卦、六爻、八字合婚、名号测算、祈福台、心愿和真人咨询入口。

## 证据与口径

- 六爻时间起卦：`artifacts/base1-analysis/recovered/java/dex-00/sources/com/example/mls/mdspaipan/pp/NoteForm.java`。上卦使用年支数、农历月、农历日之和取 8；下卦再加时支数取 8；动爻取同一总和取 6。
- 名号测算：`artifacts/base-analysis-recovered/java/dex-05/sources/yiqi/bazi/wxapi/WXPayEntryActivity.java` 及命名模块文本，明确提到生辰八字和五格数理。
- 合婚、祈福、心愿和咨询：`artifacts/base-analysis-recovered/java/dex-02/sources/yiqi/bazi` 下的 `HeHunBaziDialog`、`lamp`、`live` 模块及资源字符串。

## Decided

- 采用独立工具页承载每日运势、财富运势、六爻、求卦、合婚、名号和咨询入口；首页只做入口分组。
- 祈福明灯和心愿阁采用本地存储流程，保留创建、查看、完成和删除状态；不伪造支付成功或服务器点灯结果。
- 真人在线 1v1 使用微信 `open-type="contact"`，费用、排班和订单由运营配置；本轮不接旧 APK 网络服务。
- 每日运势、财富运势和合婚读取现有结构化命盘；不复制八字算法。
- 名号测算采用明确的五格计算接口。缺少字符笔画数据时给出待补充提示，不生成默认分数。
- 有事求卦和六爻共用已恢复的时间起卦规则，但保留两个业务入口。

## 待客户确认

- 五格笔画数据来源、姓名用字范围和最终命理流派样例。
- 合婚评分及解读的客户基准样例。
- 付费内容、价格、支付主体和 AI 接入范围。

