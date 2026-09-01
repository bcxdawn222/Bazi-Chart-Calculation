# Design: wechat-miniprogram-source-expansion

## Architecture

本次保持微信小程序原生结构，在现有核心模块旁增加三个职责单一的计算模块：

```text
miniprogram/core/
├── calendar.js          历法转换与输入归一化
├── solar_time.js        经度修正、均时差和修正明细
├── bazi.js              四柱、十神、大运、流年入口
├── bazi_details.js      藏干、藏干十神、纳音、五行统计
├── ziwei.js             十二宫、主辅星、四化、大限入口
├── ziwei_details.js     六吉六煞、亮度和三方四正
└── format.js            页面 ViewModel 组装
```

页面继续只调用统一结果构建入口。恢复源码留在 `artifacts` 中作为证据，不成为运行时依赖。

## Data Flow

```text
出生信息
  -> calendar.normalizeBirthInput
  -> solar_time.correct
  -> bazi.calculate
  -> bazi_details.calculate
  -> ziwei.calculate
  -> ziwei_details.calculate
  -> format.buildResultViewModel
  -> result 页面分区展示
```

## Interfaces

### SolarTimeCorrection

```text
{
  sourceTime: string,
  longitudeMinutes: number,
  equationOfTimeMinutes: number,
  totalCorrectionMinutes: number,
  correctedTime: string,
  crossedDateBoundary: boolean
}
```

### BaziDetails

```text
{
  pillars: Array<{
    key: "year" | "month" | "day" | "hour",
    hiddenStems: Array<{ stem: string, tenGod: string }>,
    nayin: string
  }>,
  elementCounts: { wood: number, fire: number, earth: number, metal: number, water: number },
  evidenceLevel: string
}
```

### ZiweiDetails

```text
{
  palaces: Array<{
    branch: string,
    luckyStars: string[],
    maleficStars: string[],
    brightness: Array<{ star: string, level: string }>,
    relatedPalaces: { opposite: string, trines: string[] }
  }>,
  evidenceLevel: string
}
```

### ChartResult Extension

```text
{
  normalizedTime: object,
  solarTimeCorrection: SolarTimeCorrection,
  bazi: { ...existingFields, details: BaziDetails },
  ziwei: { ...existingFields, details: ZiweiDetails },
  analysis: object
}
```

## Key Decisions

### 真太阳时修正顺序

先把输入历法转换为统一民用时间，再计算相对东经 120 度的经度修正和当天均时差，最后执行跨日与子时判断。这样四柱、农历结果和紫微时辰都使用同一最终时间。页面同时展示每一步修正，便于客户用基准样例定位差异。

旧实现只返回 `realSolarMinutes`，升级后保留该字段作为总修正兼容值，并新增结构化明细。调用方仍可读取原字段，结果页改为优先展示新明细。

### 规则证据门槛

藏干和纳音有明确的固定映射，可进入本地确定性算法。五行统计只统计天干和藏干的客观元素数量，不输出旺衰或喜用结论。紫微扩展字段只有在恢复源码常量表、安星路径或可复核固定映射存在时才返回；只有布局标签的字段保持空缺，不生成猜测结果。

## Compatibility

- `bazi.calculate` 和 `ziwei.calculate` 保留现有字段，只追加 `details`。
- `normalizeBirthInput` 保留 `realSolarMinutes` 和 `note`，新增修正明细。
- 结果页现有八字、运势、紫微和解读区域继续存在。
- 新模块使用 CommonJS `require/module.exports`，与当前微信小程序运行方式一致。

## Verification

- 现有固定样例全部重跑。
- 新增均时差正负值、跨日、23 点子时、藏干、纳音、六吉六煞和三方四正断言。
- 页面模拟检查新增字段绑定和缺失字段时的空状态。
- 微信开发者工具编译记录作为外部界面验收证据。
