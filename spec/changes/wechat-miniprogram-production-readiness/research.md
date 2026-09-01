# Research: wechat-miniprogram-production-readiness

## Practices

- 微信支付 API v3 通知应先验证 HTTP 头签名，再解密 `resource`；通知唯一标识取外层 `id`，交易状态、商户订单号、微信支付订单号、金额和币种取解密后的交易资源。服务端只有在 AppID、商户号、金额和订单归属全部匹配时才更新支付状态。
- 支付结果以服务端订单状态为准。小程序调起 `wx.requestPayment` 成功只代表支付控件完成，页面仍需查询本系统订单状态，直到后端收到通知并更新订单或达到超时上限。
- 微信小程序生产网络请求使用已配置的 HTTPS 合法域名。发布版本不能依赖开发者工具手工写入 Storage 才能获得 API 地址；未配置时应明确进入本地模式并显示缺少的配置。
- 运营数据采用最小管理面：专家和排班可维护，咨询订单只读查看及更新服务状态；不在本次扩展成完整 CRM、分佣或评价运营系统。
- 第三方康熙笔画数据应固定来源仓库、许可证、提交版本和导入时间，交付包同时包含许可证说明，避免只在界面文案中声明来源。

Key references:

- https://pay.wechatpay.cn/doc/v3/merchant/4012791902
- https://developers.weixin.qq.com/miniprogram/dev/framework/ability/network.html
- https://github.com/shunshi-ai/kangxi-mcp
- https://github.com/shunshi-ai/kangxi-mcp/blob/main/LICENSE
- https://github.com/shunshi-ai/kangxi-mcp/commit/fad0bdf7c34b0ec555edbb2af91db737825a4beb

## Constraints

- 当前 `backend/wechat_payments.py` 只返回解密资源，`backend/payment_api.py` 却读取资源中不存在的 `notify_id`；真实成功通知会在订单入账前失败。
- 当前支付测试把 `notify_id` 人工塞入解密明文，证明的是自定义模拟结构，不是微信官方通知结构；必须改为外层 `id` 的固定样例。
- 当前小程序 `miniprogram/core/api.js` 默认 API 地址为空，只读取 `apiBaseUrl` Storage，工程内没有生产配置入口；因此登录、同步、专家、订单和支付默认不可达。
- 后端已有 `experts`、`expert_schedules`、`consultation_orders` 和 `payment_notifications` 表，也有公开查询和用户订单列表能力；应复用现有表，不另建重复业务模型。
- 当前运营页只维护通用配置键值，没有专家、排班和订单管理能力；空数据库无法让咨询支付页面进入实际选择流程。
- 当前小程序支付后不查询订单，虽然后端已有订单列表接口；需要增加单笔订单契约和有限次数轮询，避免无限请求。
- 合婚当前固定阳历、关闭真太阳时并固定早子时；每日运势缺少独立健康和行动建议；名号测算缺少可选命盘关联和第三方 NOTICE。
- 当前服务器部署记录停留在 2026 年 8 月 20 日，而支付源码更新晚于该记录。部署脚本仅生成 HTTP `:80` 配置且不安装新增依赖；没有备案域名、HTTPS、小程序 AppID、商户号、证书和 API v3 Key 时，不能完成真实交易终验。
- 保留现有原生微信小程序、CommonJS、Python 标准库 HTTP 服务和 SQLite，不新增 Web 框架或前端框架。
- 继续遵守项目文件规模约束；页面逻辑、运营接口和支付解析按职责拆分，避免继续扩大已接近上限的 `backend/app.py` 和工具页文件。
- 所有启动、测试、构建、部署和导出仍从 `scripts/*.py` 与对应 `scripts/*.sh` 进入，日志写入 `logs/`。

## Open [TBD]

无。

## Decided

- [DEC-1] 支付通知解析结果同时保留外层通知 ID 和解密交易字段，订单幂等键使用外层 `id` | source [TBD-1] | decided from status quo: 当前代码字段来源错误，官方通知结构可直接确定
- [DEC-2] 新增小程序构建时运行配置文件，生产 API 地址从该文件读取；Storage 仅保留为开发调试覆盖 | source [TBD-2] | auto | 解决发布版本无后端地址的问题，同时保留本地开发便利 | reversibility: 删除覆盖层即可恢复单一常量
- [DEC-3] 增加受 `X-Admin-Token` 保护的专家、排班维护接口和咨询订单只读接口，复用现有数据库表 | source [TBD-3] | escalated | 当前空数据库没有运营录入路径，咨询支付验收无法开始 | if wrong: 扩大了运营 API 表面，可通过移除新增路由回退，现有公开查询不受影响
- [DEC-4] 支付控件成功后按固定间隔有限轮询单笔订单，并提供最近订单状态展示 | source [TBD-4] | auto | 让用户看到服务端确认结果，轮询有次数上限 | reversibility: 可关闭自动轮询，仅保留手动刷新
- [DEC-5] 合婚补充出生地点、经度、真太阳时和子时口径，并提供可解释的结构化参考分项；不输出未经客户样例确认的专业吉凶定论 | source [TBD-5] | escalated | 补齐 PRD 字段但避免伪造流派结论 | if wrong: 用户可见结果口径会变化，可保留旧摘要并关闭分项展示
- [DEC-6] 康熙笔画来源固定为 `shunshi-ai/kangxi-mcp` 提交 `fad0bdf7c34b0ec555edbb2af91db737825a4beb`，许可证为 MIT | source [TBD-6] | decided from status quo: GitHub 仓库元数据、提交和许可证已核验
- [DEC-7] 部署脚本增加依赖安装和域名参数；提供域名时生成 HTTPS Caddy 配置，没有域名时只允许内部验收模式并明确提示 | source [TBD-7] | escalated | 当前只有 HTTP，不能满足微信生产网络和支付通知条件 | if wrong: 可能改变现有 Caddy 配置生成方式，可用内部模式参数恢复现有 `:80` 行为
- [DEC-8] 未配置 API 地址时继续保留八字排盘和本地祈福能力，但线上功能必须显示“未配置”，不得静默表现为成功 | source [TBD-8] | auto | 保留已有离线价值且避免误导 | reversibility: 配置 HTTPS API 地址后自动进入线上模式
