# Research: paid-analysis-ai

## Practices
- 微信小程序内收款用官方小程序支付（JSAPI 下单 + `wx.requestPayment`）。小程序 webview 不能走 H5/JSAPI 网页支付。https://pay.weixin.qq.com/doc/v3/merchant/4012791910
- 支付宝 JSAPI 面向支付宝小程序，不是微信小程序收银台。https://opendoc.alipay.com/mini/08dcbo?pathHash=66fc32ca
- 工程已有同一套微信支付：`WechatPayClient`、`/api/payments/wechat/notify`、`prepare_order_payment`、`consultation_orders` 待支付/通知幂等。咨询入口已从产品面拆除，这条链路空着。
- `ai.enabled` 只在 `/api/config` 和运营配置里，没有模型调用。基础解读在 `format.analysisFor` 按日主拼五句本地文案。

## Constraints
- 形态是微信小程序：在微信里调不起支付宝收银台；硬接会审核失败或调起失败。
- 咨询下单 `create_order` 仍强制专家+排班，不能直接拿来卖解读。
- `consultation_orders.expert_id` / `schedule_id` 已可空；支付通知按订单号入账，与商品种类无关。
- 未配置 HTTPS / 商户号 / AI 密钥时，本地排盘必须仍可用；不得伪造已支付或 AI 正文。
- 检查入口：`python scripts/check_miniprogram.py`、`python -m scripts.test_payment`、`python -m scripts.test_backend_api`。跳过真实扣款。

## Open [TBD]

## Decided
- [DEC-1] 小程序内只接微信支付；不在微信里做支付宝收银台 | source [TBD-1] | escalated | 客户要双支付，但微信官方限制小程序内支付方式；支付宝只能另做支付宝小程序或外部浏览器 | if wrong: 用户会以为微信里能付支付宝；回滚是改文案/另开形态
- [DEC-2] 一次支付解锁当前命盘五类详细解读，不按类目五次结账 | source [TBD-2] | escalated | 客户说「解析这一类要付费」，不是五个独立商品；少一次待支付冲突 | if wrong: 改成按类目下单即可，订单多一行 kind
- [DEC-3] 详细解读在服务端用环境变量里的模型接口生成，开关复用 `ai.enabled` | source [TBD-3] | auto | 小程序端不藏密钥；没密钥就保持关闭并写 reason | reversibility: 关掉 ai.enabled，页面只留基础解读
- [DEC-4] 价格走 `runtime_config analysis.price_cents`，总闸仍是 `payment.enabled` | source [TBD-4] | auto | 与现网运营配置同一张表 | reversibility: 把 price 改回 0 或关 payment
- [DEC-5] 不恢复真人咨询入口和下单 | source 用户 2026-10-03「真人咨询不要了」 | decided from source
- [DEC-6] 解读订单复用 `consultation_orders` 加 `kind`/`chart_key`，不新建支付表 | source [TBD-6] | auto | 通知和预支付已经认这张表 | reversibility: 停写 kind=analysis 行
- [DEC-7] 未支付或 AI 未配置时只展示本地基础解读，不编造已付费/已生成 | source PRD §8 + 用户「不要伪造」 | decided from source
