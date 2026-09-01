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

module.exports = { buildChart: buildChart };
