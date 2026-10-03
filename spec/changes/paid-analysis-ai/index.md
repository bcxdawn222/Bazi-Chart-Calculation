# Index: paid-analysis-ai

Requirement source: `docs/需求沉淀-20261003.md`（2026-10-03）；客户微信 2026-08-16；`docs/八字紫微排盘产品PRD-微信小程序版.docx` V1.3；本会话改口。

## Requirements
- R-1: 包含八字四柱、十神、紫微12宫、主星辅星、四化、大运流年 | source: 李敏毓 8/16 22:52:45
- R-2: 八字、紫微斗数、真太阳时换算、早晚子时、闰月处理、大限大运、四化、12宫安星 | source: 李敏毓 8/16 22:52:21
- R-3: 像这个解析呀，什么这一类的就是要付费的，不用做成一模一样。 | source: 李敏毓 8/16 23:40:35
- R-4: 那如果说付费的话，他能不能也一块儿做到呢。就是同时支持微信和支付宝。 | source: 李敏毓 8/16 23:35:26–23:35:31
- R-5: 如果可以也可以接ai大数据 | source: 李敏毓 8/16 23:00:37
- R-6: 需要解读或分析 | source: 李敏毓 8/16 22:59:37
- R-7: 不用全要做，挑几个就可以了。 | source: 李敏毓 8/16 23:43:46
- R-8: 真人咨询不要了，不接入这个 | source: 用户 2026-10-03
- R-9: 支付和 AI 要做 | source: 用户 2026-10-03
- R-10: 基础解读只能引用本次排盘已经生成的结构化字段。 | source: PRD §8
- R-11: 文案标明“传统文化研究与娱乐参考”，不作保证性或决策性表述。 | source: PRD §8
- R-12: 深度报告、AI 生成内容和付费解锁不在本次交付范围；页面不伪造支付成功或 AI 返回结果。 | source: PRD §8（本轮用户改口覆盖前半句，后半句「不伪造」仍有效）
- R-13: 结果确认：以微信支付 API v3 支付通知为准，服务端验签、解密、校验订单金额并幂等更新订单状态。 | source: PRD §9.8
- R-14: 地址为空或非法时，本地排盘可用，登录、同步、咨询和支付显示明确原因。 | source: PRD §13
- R-15: 不加入参考图未圈出的婚姻树、好运福袋、一生财运、招财树等功能。 | source: PRD §9.1

## Assets
- A-1: `backend/wechat_payments.py` `WechatPayClient` | use: reuse | 影响：`prepare_order_payment`、notify、现有支付单测
- A-2: `backend/payment_api.py` `prepare_order_payment` / `process_wechat_notification` | use: extend | 影响：凡以 `consultation_orders.id` 为 out_trade_no 的入账
- A-3: `backend/order_store.py` `create_order` | use: extend | 影响：现咨询下单仍要求专家排班；解读单必须另入口，不能误开咨询
- A-4: `backend/db.py` `runtime_config` `payment.enabled` / `ai.enabled` | use: extend | 影响：`/api/config`、运营页
- A-5: `miniprogram/core/format.js` `analysisFor` | use: reuse | 影响：结果页五类基础文案
- A-6: `miniprogram/core/api.js` `createOrder` / `prepareOrderPayment` / `wx.requestPayment` | use: extend | 影响：结果页解锁，不再从咨询页调用
- A-7: `miniprogram/pages/tools/consultation.js` | use: rejected: 咨询已下线，不把解读支付挂回该页
- A-8: `miniprogram/pages/result/result.wxml` 解读分区 | use: extend | 影响：结果 Tab「解读」现有五条本地文案
- A-9: 支付宝 SDK / 新支付表 | use: rejected: 微信小程序调不起支付宝；支付表已有 consultation_orders

## Exemplars
- E-1: 解读付费下单 → 现有 `prepare_order_payment` + `consultation_flow_check.js` 的取消/续付，不新建收银台页型
- E-2: 结果页解锁条 → 现有 `result.wxml` 解读分区与工具页空状态「未配置则明文原因」

## Carriers
- C-1: 微信支付预下单 → `prepare_order_payment` + `WechatPayClient.create_jsapi_payment` | derive/reuse
- C-2: 支付通知入账 → `process_wechat_notification` + `consultation_orders.payment_status` | derive/reuse
- C-3: 支付总闸 → `runtime_config payment.enabled` | derive/reuse
- C-4: AI 总闸 → `runtime_config ai.enabled` | derive/reuse
- C-5: 基础解读五类正文 → `result.analysis`（wealth/marriage/career/personality/health） | derive/reuse
- C-6: 解读商品订单 → `consultation_orders` 加 `kind`/`chart_key`（现 `create_order` 只认专家排班，已搜 order_store/schema） | minting required
- C-7: 解读售价 → `runtime_config analysis.price_cents`（现价只在 experts.price_cents） | minting required
- C-8: AI 详细解读正文 → 新表或订单附属 `analysis_reports`（搜 charts.payload / runtime_config / format.js，无已付费长文载体） | minting required
- C-9: 支付宝收银台 → NOT FOUND（微信小程序无官方载体，见 research Practices） | minting required — 本轮不铸，闸门上声明不做
