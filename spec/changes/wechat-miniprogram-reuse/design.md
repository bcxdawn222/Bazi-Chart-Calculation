# Design: wechat-miniprogram-reuse

## Architecture

工程采用微信小程序原生目录，业务代码与恢复源码隔离：

```text
miniprogram/
├── app.js / app.json / app.wxss
├── pages/
│   ├── index/        出生信息输入
│   └── result/       单页分区排盘结果
├── core/
│   ├── calendar.js   阳历/农历、闰月、真太阳时、子时处理
│   ├── solar_terms.js 1901-2100 年节气日期与起运距离
│   ├── bazi.js       四柱、十神、大运、流年、神煞
│   ├── ziwei.js      十二宫、主星、辅星、四化、大限
│   └── format.js     统一结果结构和展示文本
└── data/
    └── constants.js  天干地支、宫位和星曜常量
```

恢复的 Android Java 和 XML 只作为迁移证据，不作为小程序运行时依赖。`base1.apk` 的 `BzInputActivity`、`BzTimeInput`、`BzShowForm`、`ZwView`、`ShiErGongView` 对应输入、时间、八字结果、紫微结果和十二宫展示；这些职责映射到小程序页面和 `core` 模块。

## Data Flow

```text
index 输入
  → calendar.normalizeBirthInput
  → solar_terms 节气边界与起运距离
  → bazi.calculate / ziwei.calculate
  → format.buildResultViewModel
  → result 单页分区展示
```

## Interfaces

### BirthInput

```text
{
  dateType: "solar" | "lunar",
  date: string,
  time: string,
  location: string,
  gender: "male" | "female",
  realSolarTime: boolean,
  ziHourMode: "early" | "late",
  leapMonth: boolean
}
```

### ChartResult

```text
{
  normalizedTime: object,
  bazi: {
    pillars: { year, month, day, hour },
    tenGods: { year, month, day, hour },
    dayun: { direction, items, startAgeMonths, startAgeStatus },
    liunian: Array,
    shensha: Array,
    confidence: object
  },
  ziwei: {
    lifePalace, bodyPalace, bureau, ziweiPosition,
    palaces: Array<{ branch, name, mainStars, auxiliaryStars, transformations, daxian }>,
    liunian: Array<{ year, pillar, lifePalace }>,
    confidence: string
  },
  analysis: { wealth, marriage, career, personality, health }
}
```

## Key Decisions

- 使用原生小程序文件结构，不引入第三方 UI 框架，减少从 Android 迁移时的运行环境差异。
- 首版核心计算放在本地 `core` 模块，页面只负责输入、调用和展示，后续接支付或 AI 时保留边界。
- 先迁移可由恢复源码和常量证据支撑的字段与流程；无法从恢复结果确认的规则标记为待核验，不用旧服务响应冒充算法结果。
- 农历数据表保留 1900-2049 年转换能力；完整排盘按恢复的 `SolarTerms.java` 范围使用 1901-2100 年节气算法，并要求真太阳时调整后的时间不早于 1901-01-06，避免把 1900 年公式外推当作恢复结果。
- 年柱在立春日切换，月柱在对应月份节气日切换；大运起运年龄按出生时刻到顺逆方向节气的分钟距离折算。恢复源码只提供节气日期，因此分钟精度仍需客户样例终验。
