# Screens: paid-analysis-ai

These are HTML previews of the result-page 解读 block, not live WeChat DevTools captures (pending live-acceptance).

Recapture: in this folder, `npm install playwright` then `npx playwright install chromium` then `node capture.mjs`. Same filenames are overwritten.

| name | prototype ref | file | state |
|---|---|---|---|
| 基础五句 | result 解读分区 | analysis-base.png | base-only：本地五句 + 娱乐参考 + 环境原因，无已付费 |
| 未开放原因 | result 解读分区 | analysis-locked.png | locked+reason：本地五句 + analysis.reason，无解锁按钮 |
| 已付待生成 | result 解读分区 | analysis-pending.png | paid+pending：本地五句 + 详细解读尚未生成 + 重试生成 |
| 已付详细文 | result 解读分区 | analysis-paid.png | paid+five long sections：本地五句之下另出详细解读 |
