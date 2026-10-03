# Tasks: paid-analysis-ai

> trigger: 跨栈 + 子任务多于 5。split: 契约 / 后端订单 / 后端 AI / 结果页 / 回归

- [x] 1. 按 design.md Interfaces 固定契约（本会话已写）
- [x] 2. 订单与配置
  - [x] 2.1 schema 增加 kind/chart_key、analysis_reports、analysis.price_cents
  - [x] 2.2 `POST /api/analysis-orders` 与 GET config.analysis        owner: backend  deps: 1
  - [x] 2.3 预下单与通知兼容 kind=analysis                             owner: backend  deps: 2.1
- [x] 3. AI 报告
  - [x] 3.1 GET/POST analysis-reports，未支付拒绝、无密钥 pending     owner: backend  deps: 2.2
- [x] 4. 结果页
  - [x] 4.1 基础五句保持；解锁条、登录、续付、原因文案                 owner: frontend  deps: 1
  - [x] 4.2 已支付后拉详细解读，不接咨询页                             owner: frontend  deps: 3.1, 4.1
- [x] 5. 回归
  - [x] 5.1 支付单测、analysis 夹具、check_miniprogram 无 consult 入口  deps: 2.3, 3.1, 4.2
