# Design: paid-analysis-ai

## Architecture

```
═══ 用户 / 微信 ═══
  [结果页解读] ──看基础五类──▶ [本地命盘]
  [结果页解读] ──登录并下单──▶ [后端订单]
  [微信收银台] ──用户确认──▶ [微信支付 extra]
═══ 本系统 ═══
  [解读订单] ──预下单──▶ [微信支付 extra]
  [支付通知] ──验签入账──▶ [解读订单]
  [详细解读] ──已支付才写──▶ [解读报告]
  [详细解读] ──ai.enabled──▶ [模型接口 extra]
═══ 配置 ═══
  [运营开关] 支付 / AI / 售价
```

咨询页不再发起支付。本地排盘不经过订单。

## Interfaces

- `GET /api/config`（扩展）
  - Input: 无
  - Output: 现有字段 + `analysis: { enabled: bool, price_cents: int|null, reason: string }`
  - Invariants: `analysis.enabled` 为真当且仅当 `payment.enabled` 且微信商户已配置且 `analysis.price_cents > 0`

- `POST /api/analysis-orders`
  - Input: `{ chart_key: string, subject?: string }`；`chart_key` 为出生要素规范化后的摘要，长度 8–64
  - Output: `{ item: PublicOrder }`，`PublicOrder` = 现有公开订单字段 + `kind: "analysis"` + `chart_key`
  - Error: 400 缺 key / 401 未登录 / 503 支付或售价未配置 / 400 已有待支付解读单
  - Invariants: 不写 expert_id/schedule_id；金额只取 `analysis.price_cents`；不要求 `consultation.enabled`

- `POST /api/orders/{id}/pay`
  - Input: 路径订单号
  - Output: 现有 `{ item, payment }` JSAPI 参数
  - Invariants: `kind=analysis` 与咨询单共用验签；未支付且 pending 才预下单

- `GET /api/analysis-reports?chart_key=`
  - Input: query `chart_key`
  - Output: `{ item: null | { chart_key, paid: bool, sections: {wealth,marriage,career,personality,health: string}, source: "ai"|"pending", reason: string } }`
  - Invariants: `paid=false` 时 `sections` 为空对象；未登录 401

- `POST /api/analysis-reports/generate`
  - Input: `{ chart_key: string, chart: object }`；`chart` 须通过现有 `isValidChart` 同构校验
  - Output: 同 GET item
  - Error: 402 等价 → 400「该命盘尚未支付详细解读」/ 503 AI 未配置 / 401
  - Invariants: 只在该用户该 `chart_key` 存在 `payment_status=paid` 的 analysis 订单后调用模型；失败不写假正文，`source=pending` + reason

`PublicOrder` 字段：`id, kind, chart_key, subject, amount_cents, payment_status, service_status, transaction_id, paid_at, created_at, updated_at`

## Data Model

- `consultation_orders` 增加 `kind TEXT NOT NULL DEFAULT 'consultation'`、`chart_key TEXT`
- 解读单：`kind='analysis'`，`expert_id`/`schedule_id` 空，`amount_cents` = 配置售价
- `analysis_reports`：`id, user_id, chart_key, payload TEXT, source TEXT, created_at, updated_at`；`(user_id, chart_key)` 唯一
- `runtime_config`：`analysis.price_cents`（整数分）、`analysis.reason`
- 价格只来自配置，不来自请求体
- 支付是否到账只认通知写入的 `payment_status`

## Key Decisions

- Problem: 客户要微信+支付宝，但微信小程序里只能走小程序支付，硬接支付宝会调起失败。
- Solution: 小程序只接现有微信支付；配置和文案写明本形态只有微信。支付宝不铸接口。
- Cost: 微信里看不到支付宝按钮，和口头「双支付」不一致。
- Why not the alternatives: 支付宝小程序是另一形态；webview H5 支付被微信禁止。不做支付则与「支付要做」冲突。

- Problem: 咨询下单绑专家排班，解读没有专家，复用会订空排班或改坏咨询校验。
- Solution: 同一张订单表加 kind，解读走新入口，支付通知不看 kind。
- Cost: 表里两种商品，列表要按 kind 过滤。
- Why not the alternatives: 新建支付表要重做通知幂等；继续走 create_order 会强制专家。

## Migration / Compatibility

- 旧 `consultation_orders` 行 `kind` 默认 `consultation`，现网咨询单语义不变
- `POST /api/orders` 咨询入口保持原校验，本轮产品不调用
- 未登录、未配置时结果页仍只显示本地五句基础解读
- 待支付「一用户一单」按 `kind` 切开：残留咨询未付单不挡解读下单
- `GET /api/orders` / `list_orders` 只返回 `kind=consultation`；解读用 `GET /api/analysis-orders?chart_key=`
- 不改 `api.createOrder` / `listOrders` / `prepareOrderPayment` 导出名；`consultation.js` 保留给 `consultation_flow_check`
- 结果页 `data.analysis` 仍是本地五句；详细文和 reason 用并列字段
- ALTER 加 `kind`/`chart_key`，旧行默认 consultation；解读单 `subject` 非空
- 详细正文存在 `analysis_reports`（或等价附属存储），不塞进订单列表行
