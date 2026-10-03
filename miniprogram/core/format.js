var calendar = require("./calendar");
var bazi = require("./bazi");
var baziDetails = require("./bazi_details");
var ziwei = require("./ziwei");
var ziweiDetails = require("./ziwei_details");

function elementSummary(counts) {
  var labels = { wood: "木", fire: "火", earth: "土", metal: "金", water: "水" };
  return Object.keys(labels).map(function (key) { return labels[key] + counts[key]; }).join(" ");
}

var ANALYSIS_DISCLAIMER = "传统文化研究与娱乐参考";

function findPalace(palaces, names) {
  if (!Array.isArray(palaces)) return null;
  var index;
  for (index = 0; index < palaces.length; index += 1) {
    var palace = palaces[index];
    if (palace && names.indexOf(palace.name) >= 0) return palace;
  }
  return null;
}

function citePalace(palace, label) {
  if (!palace) return "";
  var text = label;
  if (palace.branch) text += palace.branch;
  if (Array.isArray(palace.mainStars) && palace.mainStars.length) {
    text += "主星" + palace.mainStars.join("、");
  }
  return text;
}

function analysisFor(baziResult, extras) {
  extras = extras || {};
  var pillars = baziResult.pillars;
  var tenGods = baziResult.tenGods;
  var dayPillar = pillars.day;
  var dayBranch = dayPillar.charAt(1);
  var counts = baziResult.details && baziResult.details.elementCounts;
  var elements = counts ? elementSummary(counts) : "";
  var direction = baziResult.dayun && baziResult.dayun.direction ? baziResult.dayun.direction : "";
  var marriagePalace = citePalace(findPalace(extras.palaces, ["夫妻", "夫妻宫"]), "夫妻宫");
  var careerPalace = citePalace(findPalace(extras.palaces, ["官禄", "官禄宫"]), "官禄宫");
  var tenGodText = "十神年" + tenGods.year + "月" + tenGods.month + "日" + tenGods.day + "时" + tenGods.hour;
  return {
    wealth: "财富：日柱" + dayPillar + "，" + tenGodText + "，五行" + elements + "。" + ANALYSIS_DISCLAIMER,
    marriage: "婚姻：日柱" + dayPillar + "，日支" + dayBranch + (marriagePalace ? "，" + marriagePalace : "") + "。" + ANALYSIS_DISCLAIMER,
    career: "运程：日柱" + dayPillar + (careerPalace ? "，" + careerPalace : "") + (direction ? "，大运" + direction : "") + "。" + ANALYSIS_DISCLAIMER,
    personality: "性格：日柱" + dayPillar + "，" + tenGodText + "。" + ANALYSIS_DISCLAIMER,
    health: "健康：五行" + elements + "，仅展示传统排盘结构。" + ANALYSIS_DISCLAIMER,
  };
}

function buildChartKey(result) {
  var time = result.normalizedTime;
  var solar = time.solar;
  return ["ck", solar.year, solar.month, solar.day, time.hour, time.minute,
    result.input.gender, time.ziHourMode || result.input.ziHourMode || "early",
    result.input.dateType || "solar"].join("-").slice(0, 64);
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
    analysis: analysisFor(baziResult, { palaces: ziweiResult.palaces }),
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

module.exports = { buildChart: buildChart, isValidChart: isValidChart, buildChartKey: buildChartKey };
