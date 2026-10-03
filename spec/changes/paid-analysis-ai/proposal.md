# Proposal: paid-analysis-ai

## Why
客户要付费详细解析和 AI 解读，并问过微信加支付宝。排盘和九项入口已经在小程序里。咨询支付链路在，但咨询已下线，解读仍是本地五句，AI 开关是空的。本轮把支付和 AI 接到结果页解读，不恢复咨询。

## What
- 保持已落地排盘字段与九项入口，不恢复真人咨询 | refs: R-1, R-2, R-7, R-8, R-15 | verify: `python scripts/check_miniprogram.py` 仍过；首页 featureItems 无 consult
- 结果页五类基础解读免费保留，只引用当次已生成字段，并标明「传统文化研究与娱乐参考」；详细解读一次微信支付解锁当前命盘；地址空或非法时本地排盘与基础句仍可用，登录/同步/支付给 reason，不装已付费 | refs: R-3, R-6, R-9, R-10, R-11, R-12, R-14 | verify: 基础与详细文均含该标语；未登录/地址空夹具只见基础五句和 reason；paid 后可见详细分区
- 解读单复用 `consultation_orders`（kind=analysis）及现有 JSAPI 预下单与 v3 通知入账；金额只读 `analysis.price_cents` | refs: R-4, R-13 | verify: `python -m scripts.test_payment` 与新增 analysis-order 夹具过；通知仍按订单号幂等
- 已支付后服务端按命盘调环境变量模型接口，写入五类详细解读；无密钥则 `ai.enabled` 关闭并给 reason，不编造正文 | refs: R-5, R-9, R-12 | verify: 无密钥 generate 返回 pending+reason 且库中无假 sections；有夹具密钥时五类均非空且含娱乐参考句
- 微信内不提供支付宝按钮或支付宝下单接口 | refs: R-4 | verify: 小程序与 `/api/config` 无 alipay 调起字段

**Not in this change**: 真人咨询/排班履约；支付宝收银台或支付宝小程序；App/H5；旺衰喜用神格局流月；会员订阅。

## How
- 选复用现有微信预下单和通知，不新开支付表：通知已按订单号入账，咨询页不再调用。
- 选一张订单表加 kind/chart_key，不走原 `create_order`：那条强制专家排班。
- 选服务端环境变量调模型，不在小程序藏密钥：没配就关 AI。
- 选一次付清五类：少待支付冲突。微信里不做支付宝：平台禁止。
- 落地：待支付锁按 kind 切开；`list_orders` 仍只出咨询行；结果页不改写本地 `analysis` 数组；抽出预下单/轮询，保留 `consultation.js` 给现有夹具；长文不进订单列表。

## Risk
- 若误把咨询 `POST /api/orders` 接到解读，会再次要求专家。缓解：新路径 `/api/analysis-orders`，产品不恢复咨询入口。
- 若只信 `wx.requestPayment.success` 就揭文，通知失败会白送。缓解：揭文只看服务端 paid。
- 模型超时或胡写。缓解：失败保持 pending+reason；正文必须带娱乐参考句，且只能用请求里已校验命盘字段。
- 回滚：关 `payment.enabled`/`ai.enabled`，停写 kind=analysis；旧咨询行默认 kind=consultation。

<!-- APPROVED: 2026-10-03 21:16 -->
