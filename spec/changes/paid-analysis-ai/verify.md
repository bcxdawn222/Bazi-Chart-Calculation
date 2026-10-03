# Verify: paid-analysis-ai

## Round 0（stage: propose）

| ID | severity | status | topic | finding |
|---|---|---|---|---|
| V-1 | judgement | rejected | reuse | 建议把详细文写进订单行以免新表。未采纳：订单列表/运营会带长文；How 改为附属 `analysis_reports`，查询走已付 analysis 单。 |
| V-2 | judgement | fixed(r0) | reuse | 建议抽出 `consultation.js` 预下单/轮询。已写入 How。 |
| V-3 | judgement | fixed(r0) | fidelity | 基础与详细须标明娱乐参考（R-11）。已写入 What。 |
| V-4 | judgement | fixed(r0) | fidelity | 基础句只引用当次字段（R-10）。已写入 What。 |
| V-5 | judgement | fixed(r0) | fidelity | 地址空时排盘可用、登录同步支付给 reason（R-14）。已写入 What。 |

compat 落地步骤已写入 design Migration 与 proposal How，不记为对抗 What 的发现。

## Round 1（stage: apply）

| ID | severity | status | topic | finding |
|---|---|---|---|---|
| — | — | pass | — | 无幸存 critical/major/minor。独立 verifier 结论 pass。 |

conclusion: pass

defended:
- generate 无密钥返回 503 而非 body.source=pending → design.md Interfaces「Error: 503 AI 未配置」+ What「不编造正文」；test_analysis 503 且 analysis_reports=0，GET 为 paid+pending+空 sections
- 未登录仍可显示解锁按钮 → What「登录/同步/支付给 reason，不装已付费」；node 夹具 analysisPaid=false、detailedSections=[]、reason 非空
- AnalysisAIError 捕获后 200 pending → proposal ## Risk「失败保持 pending+reason」；app.py 打 warning 且不写假 sections
- IFNULL(kind,'consultation') → design Migration「旧行默认 consultation」
- analysis_ai.py / analysis_store.py 新文件 → index Carriers C-6/C-8 minting；无未使用的等价载体（create_order 仍强制专家）
- 首页/工具/祈福样式大改 → 非 endpoint/schema/permission 类能力，且不在 Not in this change 清单内；九项入口与去咨询由 R-8 覆盖

evidence:
- `python scripts/check_miniprogram.py` → exit 0；「通过 [付费解读] 基础五句、无支付宝、取消不揭文通过」；「全部检查通过」
- `python -m scripts.test_payment` → exit 0；「wechat payment signing, decrypt and idempotency checks passed」
- `python -m scripts.test_analysis` → exit 0；「analysis report and AI fixture checks passed」
- `python -m scripts.test_backend_api` → exit 0；「backend API checks passed」（config 含 analysis、无 alipay；未支付 generate 400；无密钥 generate 503 且表空）
- node 空地址/未登录夹具 → exit 0；empty-address paid=false detailed=0 unlock=false reason=未配置线上服务地址；unlogged paid=false detailed=0 reason=微信登录尚未配置
- `rg alipay|支付宝|requestAlipay miniprogram/ backend/` → 0
- `rg DEVLOG: backend/ miniprogram/ scripts/` → 0
- `ast-grep scan --config C:/Users/22812/.cursor/sdd-cursor/rules/sgconfig.yml <changed files>` → exit 0；无命中
- `git diff --stat` → 29 files / +1178 -401；另未跟踪 backend/analysis_ai.py analysis_store.py scripts/test_analysis.py scripts/fixtures/paid_analysis_check.js
- 截图审阅 screens/analysis-{base,locked,pending,paid}.png：基础五句+娱乐参考；locked 无解锁钮；pending 重试生成；paid 五类长文均含标语
- spec/knowledge.md → 不存在（无 ruling 可援）
- not run: 微信开发者工具真机/预览验收 — screens.md 写明 HTML preview，非 DevTools 实拍
- pending live check: 真机结果页解读（解锁/续付/支付通知后揭文）需微信开发者工具人工看一眼

concern deferred to acceptance (not adopted this round):
- concern rejected: GET /api/ops/orders 仍会列出 kind=analysis（运营列表加 kind 条件）
- concern rejected: 同 chart_key 未付单直接复用，不按新售价改 amount_cents
- concern rejected: GET /api/analysis-reports 对合法 chart_key 始终返回 item 对象而非 null

## Round 2（stage: apply，接手会话独立复核）

round: 2

| ID | severity | status | topic | finding |
|---|---|---|---|---|
| V-6 | major | fixed(r2) | fidelity | 新运营后台把已支付解读单当咨询单：订单页显示「确认服务」，概览「待确认服务」计入解读单。`allowedTransitions` 对 kind=analysis 返回空、显示「自动交付」；概览按 kind 排除。 |
| V-7 | major | fixed(r2) | permission | `update_order_service_status` 未区分 kind，可经 `PATCH /api/ops/orders/{id}` 人工确认/完成解读单，与 design「无专家履约」冲突。后端拒绝解读单的 confirmed/completed；取消仍走原「仅未发起支付」规则。 |
| V-8 | minor | resolved | reuse | Round 1 推迟项「ops 列表含 kind=analysis」：保留列出（运营需对账），由 V-6 标注区分，不再误导操作。 |
| V-9 | minor | deferred | fidelity | Round 1 推迟项「同 chart_key 未付单复用旧价」：保留。改价后需运营核对未付单；真实上线前随商户联调复查。 |
| V-10 | minor | defended | contract | Round 1 推迟项「GET report 始终返回对象」：design 输出为 `null \| {...}`，对象分支在契约内，且 paid=false 时 sections 为空。 |

conclusion: pass（V-9 留待商户联调验收）

evidence:
- `python -m scripts.test_analysis` → exit 0；新增断言：已支付解读单人工 confirmed / cancelled 均抛 ValueError
- `python -m scripts.test_payment` → exit 0
- `python -m scripts.test_backend_api` → exit 0
- `python -m scripts.test_backend` → exit 0
- `python scripts/check_miniprogram.py` → exit 0；含「通过 [付费解读] 基础五句、无支付宝、取消不揭文通过」
- node 内联用例 `allowedTransitions` 5 例 → ok（咨询 pending/paid→confirmed；未配置→cancelled；confirmed→completed；解读 paid→[]；解读 pending→[]）
- not run: 微信开发者工具真机结果页、真实支付通知、真实模型接口——需商户参数与 AI 密钥
- 线上服务器仍为 2026-08-28 后端，本变更未部署
