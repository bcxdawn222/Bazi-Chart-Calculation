# 八字紫微排盘微信小程序

一款专业的八字紫微排盘微信小程序，提供精准的命理分析、专家咨询、祈福许愿等功能。

## ✨ 核心功能

### 📊 排盘分析
- **八字排盘**：根据出生年月日时计算四柱八字、十神、纳音
- **紫微斗数**：十二宫位分析、主星配置、流年运势
- **详细解读**：五行分析、命盘格局、性格特点

### 🔮 命理工具
- **合婚配对**：八字合婚分析、生肖配对
- **六爻占卜**：易经起卦、吉凶预测
- **姓名分析**：五格剖象、康熙笔画

### 🙏 互动服务
- **祈福明灯**：在线祈福、心愿记录
- **专家咨询**：预约专家一对一咨询（支持微信支付）
- **历史记录**：云端同步、多端查看

## 🏗️ 技术架构

### 前端（微信小程序）
- **框架**：原生微信小程序 WXML/WXSS/JS
- **核心算法**：
  - `miniprogram/core/bazi.js` - 八字排盘算法
  - `miniprogram/core/ziwei.js` - 紫微斗数算法
  - `miniprogram/core/calendar.js` - 农历转换与节气计算
  - `miniprogram/core/solar_time.js` - 真太阳时修正
- **UI 设计**：中国风罗盘视觉、渐变配色、动效反馈

### 后端（Python）
- **框架**：Python 标准库 `http.server`（线程安全）
- **数据库**：SQLite3（WAL 模式）
- **支付集成**：微信支付 JSAPI（签名验证、AESGCM 解密）
- **部署**：Ubuntu + Caddy（反向代理 + HTTPS）

### 核心模块
```
backend/
├── app.py              # HTTP API 主入口
├── db.py               # 数据库连接与会话管理
├── wechat_payments.py  # 微信支付（签名、解密、通知处理）
├── order_store.py      # 订单并发控制与状态机
├── commerce_store.py   # 专家、排班管理
└── security.py         # 限流、令牌哈希

miniprogram/
├── pages/
│   ├── index/          # 首页（排盘表单 + 罗盘视觉）
│   ├── result/         # 结果页（八字详解 + 紫微宫位）
│   ├── tools/          # 工具集（合婚、咨询、姓名）
│   └── prayer/         # 祈福页
└── core/
    ├── api.js          # 网络层（401 重试、并发登录合并）
    ├── bazi.js         # 八字核心算法
    └── ziwei.js        # 紫微核心算法
```

## 🚀 快速开始

### 本地开发

1. **克隆仓库**
```bash
git clone https://github.com/bcxdawn222/Bazi-Chart-Calculation.git
cd Bazi-Chart-Calculation
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **启动后端**
```bash
python scripts/manage.py start
# 访问 http://127.0.0.1:8787/health 验证
```

4. **打开小程序**
```bash
# 使用微信开发者工具打开 miniprogram/ 目录
# 或运行自动化脚本
python scripts/open_miniprogram.py
```

### 测试验证

```bash
# 后端测试（数据库、API、支付、部署配置）
python scripts/manage.py test

# 小程序测试（语法、模板、日期回归、界面回归）
python scripts/check_miniprogram.py

# 预览小程序（自动打开开发者工具）
python scripts/preview_miniprogram.py
```

## 📦 生产部署

### 1. 配置环境变量

创建 `.env` 文件（参考 `delivery/待配置清单.txt`）：

```bash
# 微信小程序
WX_APP_ID=wxxxxxxxxxxx
WX_APP_SECRET=xxxxxxxxxxxxxxxx
SESSION_SECRET=xxxxxxxxxxxxxxxx（至少32字符）

# 微信支付
WX_PAY_MCH_ID=xxxxxxxxxx
WX_PAY_SERIAL_NO=xxxxxxxxxxxxxxxx
WX_PAY_PRIVATE_KEY_PATH=/path/to/apiclient_key.pem
WX_PAY_API_V3_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
WX_PAY_NOTIFY_URL=https://yourdomain.com/api/payments/wechat/notify
WX_PAY_PLATFORM_SERIAL_NO=xxxxxxxxxxxxxxxx
WX_PAY_PLATFORM_PUBLIC_KEY_PATH=/path/to/wechatpay_platform.pem

# 运营管理
ADMIN_TOKEN=xxxxxxxxxxxxxxxx（至少32字符）
ALLOWED_ORIGINS=https://yourdomain.com
```

### 2. 配置小程序 API 地址

编辑 `miniprogram/config/runtime.js`：

```javascript
module.exports = {
  apiBaseUrl: "https://yourdomain.com"  // 你的生产域名
};
```

### 3. 部署到服务器

```bash
# 上传代码并启动服务
python scripts/deploy_server.py --host YOUR_SERVER_IP --domain yourdomain.com

# 或手动部署
scp -r backend/ ubuntu@YOUR_SERVER:/home/ubuntu/bazi-ziwei/
ssh ubuntu@YOUR_SERVER 'sudo systemctl restart bazi-ziwei.service'
```

### 4. 微信小程序上传

```bash
# 使用开发者工具上传代码
# 或使用 CLI
python scripts/generate_delivery.py  # 生成交付包
# 在微信开发者工具中上传 delivery/miniprogram/ 目录
```

## 🔐 安全特性

- ✅ 微信支付平台响应验签（RSA2048 + SHA256）
- ✅ 支付通知 AESGCM 解密验证
- ✅ 订单状态并发控制（数据库事务 + 乐观锁）
- ✅ 会话令牌 HMAC 存储（防彩虹表）
- ✅ 401 自动重试 + 并发登录合并（防令牌竞态）
- ✅ 速率限制（120 req/min per IP）
- ✅ SQL 参数化查询（防注入）
- ✅ WAL 模式在线备份（防数据丢失）

## 📊 测试覆盖

### 后端测试
- 数据库 CRUD + 外键约束 + 索引
- HTTP API（登录、排盘、订单、专家、配置）
- 微信支付签名、解密、幂等性
- 部署配置完整性

### 小程序测试
- 24 个 JavaScript 文件语法检查
- 4 个页面配置与模板验证
- 599 组常规日期 + 55 组闰月往返一致性
- 咨询流程（并行加载、订单恢复、支付重试）
- 界面回归（字段错误、输入保留、清空确认、Tab 切换、空状态）
- 参考动效回归（8 个延时入口、重复点击保护、隐藏取消跳转）

### 真实验收
- 开发者工具多窗口、打印窗口验证
- 真机预览完整流程覆盖（见 `spec/changes/miniprogram-ui-refine/screens/`）

## 📝 项目文档

- [产品 PRD](discuss/八字紫微排盘Phase计划-微信小程序版.docx) - 产品需求与 Phase 计划
- [代码审查记录](docs/代码审查记录-2026-10-01.md) - 功能逻辑与使用阻塞审查
- [界面重构目标](docs/界面重构目标-2026-10-02.md) - UI 设计目标与验收标准
- [部署说明](delivery/部署说明.txt) - 生产环境部署步骤
- [运行说明](delivery/运行说明.txt) - 本地开发与测试指南
- [待配置清单](delivery/待配置清单.txt) - 上线前必须配置的环境变量

## 🛠️ 工具脚本

```bash
# 管理工具
scripts/manage.py start        # 启动后端
scripts/manage.py stop         # 停止后端
scripts/manage.py status       # 查看状态
scripts/manage.py backup       # 数据库备份
scripts/manage.py clean        # 清理缓存
scripts/manage.py test         # 运行测试

# 小程序工具
scripts/check_miniprogram.py   # 小程序检查
scripts/open_miniprogram.py    # 打开开发者工具
scripts/preview_miniprogram.py # 预览小程序

# 运营工具
scripts/preview_admin.py       # 预览运营后台

# 部署工具
scripts/deploy_server.py       # 部署到生产服务器
scripts/generate_delivery.py   # 生成交付包
```

## 🎨 UI 特色

- **罗盘视觉**：8 层叠加（太极、地支、卦象、节气等）
- **渐变配色**：#8B7355 → #D4AF37 金色系
- **动效反馈**：页面入场、按钮涟漪、加载骨架屏
- **响应式布局**：适配 iPhone SE 到 iPad Pro
- **暗黑模式支持**：跟随系统主题

## ⚠️ 上线前检查清单

- [ ] 配置 `miniprogram/config/runtime.js` 的 `apiBaseUrl`
- [ ] 配置所有环境变量（微信、支付、会话、运营）
- [ ] 微信支付证书上传并验证
- [ ] 域名备案并解析到服务器
- [ ] HTTPS 证书配置（Let's Encrypt 或商业证书）
- [ ] 微信小程序服务器域名白名单配置
- [ ] 真机测试微信登录与支付流程
- [ ] 运行全量测试：`python scripts/manage.py test && python scripts/check_miniprogram.py`
- [ ] 生成交付包：`python scripts/generate_delivery.py`

## 📄 许可证

本项目代码采用专有许可证，未经授权不得商业使用。

第三方库许可：
- 康熙字典笔画数据：见 [docs/third-party/kangxi-mcp-NOTICE.md](docs/third-party/kangxi-mcp-NOTICE.md)

## 🤝 贡献

欢迎提交 Issue 和 Pull Request。

## 📮 联系方式

- GitHub: https://github.com/bcxdawn222/Bazi-Chart-Calculation
- Issues: https://github.com/bcxdawn222/Bazi-Chart-Calculation/issues

---

**注意**：本项目仅供学习交流使用。八字紫微等命理内容仅为传统文化参考，不构成任何决策建议。
