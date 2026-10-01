var calendar = require("./calendar");
var bazi = require("./bazi");
var baziDetails = require("./bazi_details");
var ziwei = require("./ziwei");
var ziweiDetails = require("./ziwei_details");

function elementSummary(counts) {
  var labels = { wood: "木", fire: "火", earth: "土", metal: "金", water: "水" };
  return Object.keys(labels).map(function (key) { return labels[key] + counts[key]; }).join(" ");
}

function analysisFor(baziResult) {
  var dayStem = baziResult.pillars.day.charAt(0);
  var texts = {
    甲: "日主为甲木，分析以生长、规划和执行节奏为主。",
    乙: "日主为乙木，分析以协调、适应和持续积累为主。",
    丙: "日主为丙火，分析以表达、行动和外部反馈为主。",
    丁: "日主为丁火，分析以专注、洞察和稳定投入为主。",
    戊: "日主为戊土，分析以承载、秩序和长期建设为主。",
    己: "日主为己土，分析以细化、整合和资源安排为主。",
    庚: "日主为庚金，分析以决断、规则和效率为主。",
    辛: "日主为辛金，分析以品质、边界和精细判断为主。",
    壬: "日主为壬水，分析以流动、连接和全局变化为主。",
    癸: "日主为癸水，分析以观察、信息和渐进调整为主。",
  };
  return {
    wealth: "财富：结合财星、运势阶段和实际选择综合查看。",
    marriage: "婚姻：结合夫妻宫、日支和四化信息综合查看。",
    career: "运程：结合官禄宫、大运和流年信息综合查看。",
    personality: "性格：" + texts[dayStem],
    health: "健康：仅展示传统排盘结构，不作为医学判断。",
  };
}

function buildChart(input) {
  var normalized = calendar.normalizeBirthInput(input);
  var baziResult = bazi.calculate(normalized, input.gender);
  baziResult.details = baziDetails.calculate(baziResult.pillars);
  var ziweiResult = ziwei.calculate(normalized, baziResult, input.gender);
  var ziweiDetailResult = ziweiDetails.calculate(ziweiResult.palaces);
  ziweiResult.palaces = ziweiDetailResult.palaces;
  ziweiResult.details = ziweiDetailResult;
  return {
    input: input,
    normalizedTime: normalized,
    bazi: baziResult,
    ziwei: ziweiResult,
    analysis: analysisFor(baziResult),
    elementSummary: elementSummary(baziResult.details.elementCounts),
    migrationEvidence: [
      "base1: BzTimeInput / BzShowForm",
      "base1: ZwView / u2.m",
      "base: yiqi.bazi 解读入口",
    ],
  };
}

function isObject(value) {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function isText(value) { return typeof value === "string" && value.length > 0; }
function isTextList(value) { return Array.isArray(value) && value.every(isText); }

function isValidChart(result) {
  if (!isObject(result) || !isObject(result.input) || !isObject(result.normalizedTime)
      || !isObject(result.bazi) || !isObject(result.ziwei) || !isObject(result.analysis)) return false;
  var time = result.normalizedTime;
  if (!isObject(time.solar) || !isObject(time.lunar) || !isObject(time.solarTimeCorrection)) return false;
  if (!["year", "month", "day"].every(function (key) {
    return Number.isInteger(time.solar[key]) && Number.isInteger(time.lunar[key]);
  }) || !Number.isInteger(time.hour) || !Number.isInteger(time.minute)) return false;
  var baziResult = result.bazi;
  var details = baziResult.details;
  if (!isObject(baziResult.pillars) || !isObject(baziResult.tenGods) || !isObject(details)
      || !isObject(details.elementCounts) || !isObject(baziResult.dayun)) return false;
  if (!["year", "month", "day", "hour"].every(function (key) {
    return isText(baziResult.pillars[key]) && baziResult.pillars[key].length === 2 && isText(baziResult.tenGods[key]);
  }) || !["wood", "fire", "earth", "metal", "water"].every(function (key) {
    return Number.isFinite(details.elementCounts[key]) && details.elementCounts[key] >= 0;
  })) return false;
  if (!Array.isArray(details.pillars) || details.pillars.length !== 4 || !details.pillars.every(function (item) {
    return isObject(item) && Array.isArray(item.hiddenStems) && item.hiddenStems.every(function (hidden) {
      return isObject(hidden) && isText(hidden.stem) && isText(hidden.tenGod);
    });
  }) || !Array.isArray(baziResult.dayun.items) || !Array.isArray(baziResult.shensha)) return false;
  var ziweiResult = result.ziwei;
  if (!isObject(ziweiResult.details) || !Array.isArray(ziweiResult.liunian)
      || !Array.isArray(ziweiResult.palaces) || ziweiResult.palaces.length !== 12) return false;
  if (!ziweiResult.palaces.every(function (palace) {
    return isObject(palace) && ["mainStars", "auxiliaryStars", "luckyStars", "maleficStars"].every(function (key) {
      return isTextList(palace[key]);
    }) && Array.isArray(palace.brightness) && palace.brightness.every(function (item) {
      return isObject(item) && isText(item.star) && isText(item.level);
    }) && Array.isArray(palace.transformations) && palace.transformations.every(function (item) {
      return isObject(item) && isText(item.name) && isText(item.star);
    }) && isObject(palace.relatedPalaces) && isText(palace.relatedPalaces.opposite)
      && isTextList(palace.relatedPalaces.trines);
  })) return false;
  return ["wealth", "marriage", "career", "personality", "health"].every(function (key) {
    return isText(result.analysis[key]);
  });
}

module.exports = { buildChart: buildChart, isValidChart: isValidChart };
