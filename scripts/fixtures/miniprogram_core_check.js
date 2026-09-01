const calendar = require("../../miniprogram/core/calendar");
const format = require("../../miniprogram/core/format");
const solarTerms = require("../../miniprogram/core/solar_terms");
const fortune = require("../../miniprogram/core/features/fortune");
const divination = require("../../miniprogram/core/features/divination");
const compatibility = require("../../miniprogram/core/features/compatibility");
const naming = require("../../miniprogram/core/features/naming");
const api = require("../../miniprogram/core/api");
const runtimeConfig = require("../../miniprogram/config/runtime");
const orderTracker = require("../../miniprogram/core/order_tracker");
const strokeData = require("../../miniprogram/data/kangxi-strokes");

let roundTripCases = 0;
let leapRoundTripCases = 0;
let boundaryRejectCount = 0;
let invalidInputRejectCount = 0;

for (let year = 1900; year <= 2049; year += 1) {
  for (const month of [1, 4, 7, 10]) {
    const day = 15;
    if (year === 1900 && month === 1) continue;
    const lunar = calendar.solarToLunar(year, month, day);
    const solar = calendar.lunarToSolar(lunar.year, lunar.month, lunar.day, lunar.isLeap);
    if (solar.year !== year || solar.month !== month || solar.day !== day) {
      throw new Error(`历法往返不一致：${year}-${month}-${day}`);
    }
    roundTripCases += 1;
  }
  const leap = calendar.leapMonth(year);
  if (leap) {
    const solar = calendar.lunarToSolar(year, leap, 1, true);
    const lunar = calendar.solarToLunar(solar.year, solar.month, solar.day);
    if (lunar.year !== year || lunar.month !== leap || lunar.day !== 1 || !lunar.isLeap) {
      throw new Error(`闰月往返不一致：${year}-${leap}-1`);
    }
    leapRoundTripCases += 1;
  }
}

try {
  calendar.lunarToSolar(2050, 1, 1, false);
} catch (error) {
  boundaryRejectCount += 1;
}

let shortMonthRejected = false;
for (let year = 1900; year <= 2049 && !shortMonthRejected; year += 1) {
  for (let month = 1; month <= 12; month += 1) {
    if (calendar.monthDays(year, month) !== 29) continue;
    try {
      calendar.lunarToSolar(year, month, 30, false);
    } catch (error) {
      shortMonthRejected = true;
      boundaryRejectCount += 1;
    }
    break;
  }
}

const invalidDates = [
  "2023-02-29 12:00", "2023-13-01 12:00",
  "2023-01-01 25:00", "2023-01-01 12:99",
];
for (const date of invalidDates) {
  try {
    calendar.normalizeBirthInput({ dateType: "solar", date, location: "120", realSolarTime: false });
  } catch (error) {
    invalidInputRejectCount += 1;
  }
}
try {
  calendar.normalizeBirthInput({
    dateType: "solar", date: "1990-01-01 12:00", location: "999", realSolarTime: true,
  });
} catch (error) {
  invalidInputRejectCount += 1;
}
try {
  calendar.normalizeBirthInput({
    dateType: "solar", date: "1901-01-05 23:59", location: "120", realSolarTime: false,
  });
} catch (error) {
  invalidInputRejectCount += 1;
}
let unsupportedSolarTermYearRejected = false;
try {
  solarTerms.termDay(1900, 0);
} catch (error) {
  unsupportedSolarTermYearRejected = true;
}

const result = format.buildChart({
  dateType: "solar",
  date: "1990-01-01 12:00",
  location: "116.40",
  gender: "male",
  realSolarTime: true,
  ziHourMode: "early",
  leapMonth: false,
});
const crossDateChart = format.buildChart({
  dateType: "solar",
  date: "1990-01-01 00:05",
  location: "80",
  gender: "male",
  realSolarTime: true,
  ziHourMode: "early",
  leapMonth: false,
});
const ziHourInput = {
  dateType: "solar", date: "1990-01-01 23:30", location: "120.00",
  gender: "male", realSolarTime: false, leapMonth: false,
};
const earlyZi = format.buildChart(Object.assign({}, ziHourInput, { ziHourMode: "early" }));
const lateZi = format.buildChart(Object.assign({}, ziHourInput, { ziHourMode: "late" }));
const lifePalace = result.ziwei.palaces.find(item => item.name === "命宫");
const correction = result.normalizedTime.solarTimeCorrection;
const hiddenStemCount = result.bazi.details.pillars.reduce(
  (total, item) => total + item.hiddenStems.length,
  0,
);
const nayinCount = result.bazi.details.pillars.filter(item => Boolean(item.nayin)).length;
const brightnessCount = result.ziwei.palaces.reduce(
  (total, item) => total + item.brightness.length,
  0,
);
const relatedPalaceCount = result.ziwei.palaces.filter(item => (
  item.relatedPalaces
  && Boolean(item.relatedPalaces.opposite)
  && item.relatedPalaces.trines.length === 2
)).length;

function chartAt(date) {
  return format.buildChart({
    dateType: "solar", date, location: "120", gender: "male",
    realSolarTime: false, ziHourMode: "early", leapMonth: false,
  });
}

const beforeLichun = chartAt("2021-02-02 12:00");
const afterLichun = chartAt("2021-02-03 12:00");
const beforeJingzhe = chartAt("2021-03-04 12:00");
const afterJingzhe = chartAt("2021-03-05 12:00");
const solarTermBoundaryCount = Number(beforeLichun.bazi.pillars.year !== afterLichun.bazi.pillars.year)
  + Number(beforeJingzhe.bazi.pillars.month !== afterJingzhe.bazi.pillars.month);
const dayunVaries = chartAt("2021-03-06 12:00").bazi.dayun.startAgeMonths
  !== chartAt("2021-03-20 12:00").bazi.dayun.startAgeMonths;
const dailyFortune = fortune.buildDaily(result, "2026-08-20");
const yearFortune = fortune.buildYear(result, 2026);
const divinationResult = divination.buildByTime("2026-08-20 12:00", "项目进度");
const compatibilityResult = compatibility.build({
  name: "甲方", date: "1990-01-01", time: "12:00", locationLabel: "北京",
  location: "116.40", realSolarTime: true, ziHourMode: "early"
}, {
  name: "乙方", date: "1992-02-02", time: "08:30", locationLabel: "上海",
  location: "121.47", realSolarTime: true, ziHourMode: "late"
});
const namingResult = naming.calculate("李", "明", result);
let invalidNamingRejected = false;
try {
  naming.calculate("李", "𪛖");
} catch (error) {
  invalidNamingRejected = true;
}

let capturedPage = null;
let navigatedUrl = "";
let modalMessage = "";
const storage = {};
const appState = { globalData: { chartResult: result } };
global.Page = function (definition) { capturedPage = definition; };
global.getApp = function () { return appState; };
global.wx = {
  getStorageSync: function (key) { return storage[key] || null; },
  setStorageSync: function (key, value) { storage[key] = value; },
  removeStorageSync: function (key) { delete storage[key]; },
  navigateTo: function (options) { navigatedUrl = options.url; },
  showModal: function (options) { modalMessage = options.content; },
};

require("../../miniprogram/pages/result/result");
const resultPage = capturedPage;
const resultPageContext = {
  setData: function (payload) { this.data = Object.assign({}, this.data, payload); },
};
resultPage.onLoad.call(resultPageContext);
resultPage.onTabChange.call(resultPageContext, { currentTarget: { dataset: { tab: "ziwei" } } });
resultPage.selectPalace.call(resultPageContext, { currentTarget: { dataset: { index: 5 } } });
const resultPageLiunianBound = resultPageContext.data.liunian.length === result.ziwei.liunian.length
  && resultPageContext.data.liunian[0].lifePalace === result.ziwei.liunian[0].lifePalace;
const resultPageDetailsBound = resultPageContext.data.time.correction.totalCorrectionMinutes === -18.01
  && resultPageContext.data.baziDetails.length === 4
  && resultPageContext.data.baziDetails[0].hiddenStemsText.includes("丙")
  && resultPageContext.data.palaces[0].brightnessText.length > 0
  && resultPageContext.data.palaces[0].relatedText.includes("对宫")
  && resultPageContext.data.elementBars.length === 5
  && resultPageContext.data.activeTab === "ziwei"
  && resultPageContext.data.selectedPalace.name === "夫妻";
appState.globalData.chartResult = {};
modalMessage = "";
resultPage.onLoad.call({ setData: function () {} });
const invalidResultHandled = modalMessage.includes("重新排盘") && appState.globalData.chartResult === null;
appState.globalData.chartResult = result;

capturedPage = null;
require("../../miniprogram/pages/index/index");
const indexPage = capturedPage;
const validIndexContext = {
  data: Object.assign({}, indexPage.data),
  saveRecent: indexPage.saveRecent,
};
indexPage.submitChart.call(validIndexContext);
const recent = storage.recentCharts[0];
const restoreContext = {
  data: Object.assign({}, indexPage.data, { recentCharts: storage.recentCharts }),
  setData: function (payload) { this.data = Object.assign({}, this.data, payload); },
};
indexPage.restoreChart.call(restoreContext, { currentTarget: { dataset: { index: 0 } } });
const invalidIndexContext = { data: Object.assign({}, indexPage.data, { date: "2023-02-29" }) };
indexPage.submitChart.call(invalidIndexContext);
const indexFlowValidated = navigatedUrl === "/pages/result/result"
  && modalMessage === "阳历日期不存在"
  && recent.date === "1990-01-01" && recent.time === "12:00"
  && restoreContext.data.date === "1990-01-01" && restoreContext.data.time === "12:00";
indexPage.onFeatureTap.call(validIndexContext, { currentTarget: { dataset: { id: "liuyao" } } });
const featureNavigationValidated = navigatedUrl === "/pages/tools/tools?mode=liuyao";
let recordApiMessage = "";
api.listPrayers(function (response) { recordApiMessage = response.message; });

console.log(JSON.stringify({
  roundTripCases,
  leapRoundTripCases,
  boundaryRejectCount,
  invalidInputRejectCount,
  unsupportedSolarTermYearRejected,
  ziHourDiffers: earlyZi.bazi.pillars.day !== lateZi.bazi.pillars.day,
  solar: result.normalizedTime.solar,
  hour: result.normalizedTime.hour,
  minute: result.normalizedTime.minute,
  correction: {
    longitudeMinutes: correction.longitudeMinutes,
    equationOfTimeMinutes: correction.equationOfTimeMinutes,
    totalCorrectionMinutes: correction.totalCorrectionMinutes,
    crossedDateBoundary: correction.crossedDateBoundary,
  },
  crossDateCorrection: {
    solar: crossDateChart.normalizedTime.solar,
    totalCorrectionMinutes: crossDateChart.normalizedTime.solarTimeCorrection.totalCorrectionMinutes,
    crossedDateBoundary: crossDateChart.normalizedTime.solarTimeCorrection.crossedDateBoundary,
  },
  pillars: Object.values(result.bazi.pillars),
  tenGods: Object.values(result.bazi.tenGods),
  hiddenStemCount,
  nayinCount,
  elementCounts: result.bazi.details.elementCounts,
  palaceCount: result.ziwei.palaces.length,
  mainStarCount: result.ziwei.palaces.flatMap(item => item.mainStars).length,
  auxiliaryStarCount: result.ziwei.palaces.flatMap(item => item.auxiliaryStars).length,
  brightnessCount,
  relatedPalaceCount,
  transformationCount: result.ziwei.palaces.flatMap(item => item.transformations).length,
  bureau: result.ziwei.bureau,
  lifePalace: result.ziwei.lifePalace,
  ziweiPosition: result.ziwei.ziweiPosition,
  analysisCount: Object.values(result.analysis).filter(Boolean).length,
  lifeDaxian: lifePalace.daxian,
  ziweiLiunianCount: result.ziwei.liunian.length,
  solarTermBoundaryCount,
  dayunVaries,
  resultPageLiunianBound,
  resultPageDetailsBound,
  invalidResultHandled,
  indexFlowValidated,
  featureNavigationValidated,
  dailyFortuneValidated: dailyFortune.sections.length === 5
    && dailyFortune.sections.some(item => item.label === "健康")
    && dailyFortune.sections.some(item => item.label === "行动建议")
    && Boolean(dailyFortune.relation),
  yearFortuneValidated: yearFortune.months.length === 12 && yearFortune.pillar === "丙午",
  divinationValidated: divinationResult.upper.name === "坎"
    && divinationResult.lower.name === "巽"
    && divinationResult.movingLine === 5,
  compatibilityValidated: compatibilityResult.elements.length === 5
    && compatibilityResult.referenceSections.length >= 3
    && compatibilityResult.left.timeBasis.realSolarTime === true
    && compatibilityResult.right.timeBasis.ziHourMode === "late"
    && Boolean(compatibilityResult.branchRelation),
  namingValidated: namingResult.grids.length === 5
    && namingResult.grids[0].number === 8
    && namingResult.grids[1].number === 15
    && namingResult.chartReference.dayMaster === result.bazi.pillars.day.charAt(0)
    && strokeData.meta.sourceCommit === "fad0bdf7c34b0ec555edbb2af91db737825a4beb"
    && invalidNamingRejected,
  onlineApiValidated: runtimeConfig.apiBaseUrl === ""
    && typeof api.getOrder === "function"
    && typeof api.listOrders === "function"
    && recordApiMessage === "未配置线上服务地址，排盘和本地记录仍可使用"
    && orderTracker.shouldPoll({ payment_status: "pending" }, 0, 6)
    && !orderTracker.shouldPoll({ payment_status: "paid" }, 0, 6)
    && orderTracker.statusLabel("paid") === "已支付",
}));
