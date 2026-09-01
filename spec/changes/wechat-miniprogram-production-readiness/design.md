# Design: wechat-miniprogram-production-readiness

## Architecture

```text
微信用户
  │ 录入 / 查询 / 支付
  ▼
小程序页面层 ──调用结构化能力──▶ 本地命理模块
  │                               │
  │ HTTPS API                     └──返回可解释的本地结果
  ▼
后端接口层 ──鉴权与校验──▶ 订单 / 专家 / 排班 / 用户记录
  │                           │
  │ JSAPI 下单                └──SQLite 持久化
  ▼
微信支付 [external] ──支付通知──▶ 后端通知处理 ──更新订单──▶ 小程序订单回查

运营人员
  │ ADMIN_TOKEN
  ▼
运营配置页 ──维护──▶ 专家 / 排班 / 配置；只读查看订单
```

本地排盘和线上商业化保持分离。没有 API 地址时，本地排盘、每日运势、起卦、合婚、名号和本地祈福仍可运行；登录、同步、咨询和支付明确显示未配置状态。

## Interfaces

### 小程序运行配置

- `runtimeConfig.apiBaseUrl: string`
  - 必须为空字符串或 `https://` 地址。
  - 发布版本以构建时配置为准。
  - 开发版本允许 Storage 覆盖，覆盖值同样执行协议校验。

### 支付通知内部契约

- `VerifiedPaymentNotification`
  - `notify_id: string`：通知外层 `id`。
  - `app_id: string`：解密资源 `appid`。
  - `mch_id: string`：解密资源 `mchid`。
  - `out_trade_no: string`。
  - `transaction_id: string`。
  - `trade_state: string`。
  - `amount_total: int`。
  - `currency: string`。
  - `success_time: string`。
  - 不变量：签名、时间窗口、平台证书序列号和 AES-GCM 解密全部通过后才构造该对象。
  - 不变量：订单更新前校验 AppID、商户号、金额和币种。

### 用户订单接口

- `GET /api/orders`
  - 鉴权：Bearer 会话。
  - 输出：`{items: OrderSummary[]}`，只返回当前用户订单。
- `GET /api/orders/{order_id}`
  - 鉴权：Bearer 会话。
  - 输出：`{item: OrderDetail}`。
  - 错误：`401` 会话无效，`404` 订单不存在或不属于当前用户。
- `POST /api/orders`
  - 输入：`{subject: string, expert_id: string, schedule_id?: string}`。
  - 输出：`{item: OrderDetail}`。
  - 不变量：价格只从服务器专家记录读取，客户端不得提交金额。
- `POST /api/orders/{order_id}/pay`
  - 输出：`{item: OrderDetail, payment: WxPaymentParams}`。
  - 错误：未配置支付、订单无价格、订单已支付、专家不可用。

`OrderSummary` 和 `OrderDetail` 至少包含：`id/expert_id/schedule_id/subject/amount_cents/payment_status/service_status/created_at/updated_at`；详情额外包含 `transaction_id/paid_at`。不得向小程序返回 `prepay_id`、通知 ID 或用户内部标识。

### 运营专家接口

- `POST /api/ops/experts`
  - 鉴权：`X-Admin-Token`。
  - 输入：`{display_name, bio, avatar_url, status, price_cents}`。
  - 输出：`{item: Expert}`。
- `PUT /api/ops/experts/{expert_id}`
  - 同上，更新后返回 `Expert`。
- `DELETE /api/ops/experts/{expert_id}`
  - 有历史订单时改为 `hidden`，无历史引用时允许删除。

`Expert.status` 只允许 `online/offline/hidden`；`price_cents` 为空表示不可支付，否则必须为正整数。

### 运营排班接口

- `POST /api/ops/schedules`
  - 输入：`{expert_id, starts_at, ends_at, status}`。
- `PUT /api/ops/schedules/{schedule_id}`
  - 更新排班。
- `DELETE /api/ops/schedules/{schedule_id}`
  - 有订单引用时改为 `closed`，无引用时允许删除。

`Schedule.status` 只允许 `available/booked/closed`；结束时间必须晚于开始时间。

### 运营订单接口

- `GET /api/ops/orders?payment_status=&service_status=`
  - 鉴权：`X-Admin-Token`。
  - 输出：`{items: OpsOrder[]}`。
- `PATCH /api/ops/orders/{order_id}`
  - 输入：`{service_status}`。
  - 只允许 `pending/confirmed/completed/cancelled`。
  - 不允许通过运营接口直接把未支付订单改为已支付。

### 工具模块契约

- 每日运势 `sections` 固定包含 `事业/财运/感情/健康/行动建议`。
- 合婚双方输入包含 `name/date/time/locationLabel/longitude/realSolarTime/ziHourMode`；输出包含双方四柱、五行分布、日干关系、日支关系、结构化参考分项和综合提示。
- 名号测算接受可选的最近命盘；输出保留五格与三才，并在关联命盘存在时只展示日主与五行统计，不推导喜用神。

## Data Model

- 复用 `experts`：专家基本资料、状态和服务器价格来源。
- 复用 `expert_schedules`：专家排班，`expert_id` 关联 `experts.id`。
- 复用 `consultation_orders`：用户订单和服务状态；支付状态只由下单流程和微信通知流程改变。
- 复用 `payment_notifications`：`notify_id` 为微信通知外层 ID，承担通知幂等。
- 增加必要索引但不新增重复表：专家状态、排班状态/时间、订单支付状态/服务状态。
- 旧数据库通过 `CREATE TABLE IF NOT EXISTS` 和列检查迁移；已有记录不重写金额或状态。

## Key Decisions

### 支付成功必须由可信服务端事件确认

- Problem：用户完成支付控件后，如果页面直接显示成功或回调字段取错，订单可能长期停留在待支付，也可能出现客户端状态与服务器账目不一致。
- Solution：通知解析区分外层事件和解密交易资源，校验商户身份及金额；小程序只查询服务器订单状态，不自行把订单改成已支付。
- Cost：支付完成到页面显示已确认之间可能有数秒延迟，需要有限轮询和手动刷新。
- Why not the alternatives：只信任 `wx.requestPayment.success` 无法证明服务端到账；继续使用自定义 `notify_id` 会与官方结构不兼容；完全不做回查会让用户无法确认结果。

### 生产地址采用显式构建配置

- Problem：当前发布包必须靠开发者手工写 Storage 才能连接后端，正常用户无法完成该操作，线上功能实际不可达。
- Solution：交付包提供单一运行配置文件并验证 HTTPS；开发调试允许临时覆盖，发布模式不依赖隐藏状态。
- Cost：正式发布前必须把备案 HTTPS 域名写入配置并重新构建小程序。
- Why not the alternatives：硬编码服务器 IP 不满足正式小程序域名要求；继续只读 Storage 不可交付；在页面暴露任意服务器地址输入会扩大安全风险。

## Migration / Compatibility

- 本地命盘和祈福 Storage 键保持不变。
- 现有公开配置、专家查询、排班查询和订单创建接口保持兼容。
- 新增接口不改变旧响应字段；订单响应会过滤内部支付字段，小程序仅使用公开字段。
- 服务器没有正式域名时仍可使用内部验收模式，但文档和状态接口必须明确标记为非生产。
- 生产支付环境变量和证书不进入仓库、日志、Word 文档或交付压缩包。
