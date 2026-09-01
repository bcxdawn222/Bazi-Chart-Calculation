var chartBuilder = require("../format");
var bazi = require("../bazi");

var HARMONY = ["子丑", "寅亥", "卯戌", "辰酉", "巳申", "午未"];
var CLASH = ["子午", "丑未", "寅申", "卯酉", "辰戌", "巳亥"];
var ELEMENT_LABELS = { wood: "木", fire: "火", earth: "土", metal: "金", water: "水" };

function buildInput(data, gender) {
  var name = String(data.name || "").trim();
  var locationLabel = String(data.locationLabel || "").trim();
  if (!name) throw new Error(gender === "male" ? "请输入男方姓名" : "请输入女方姓名");
  if (!locationLabel) throw new Error(gender === "male" ? "请输入男方出生地点" : "请输入女方出生地点");
  return {
    name: name,
    locationLabel: locationLabel,
    dateType: "solar",
    date: data.date + " " + data.time,
    location: data.location || "120",
    gender: gender,
    realSolarTime: Boolean(data.realSolarTime),
    ziHourMode: data.ziHourMode === "late" ? "late" : "early",
    leapMonth: false
  };
}

function relationFor(leftBranch, rightBranch) {
  var pair = leftBranch + rightBranch;
  var reverse = rightBranch + leftBranch;
  if (HARMONY.indexOf(pair) >= 0 || HARMONY.indexOf(reverse) >= 0) return "日支六合";
  if (CLASH.indexOf(pair) >= 0 || CLASH.indexOf(reverse) >= 0) return "日支相冲";
  if (leftBranch === rightBranch) return "日支同气";
  return "日支常规关系";
}

function combinedElements(left, right) {
  return Object.keys(ELEMENT_LABELS).map(function (key) {
    return {
      label: ELEMENT_LABELS[key],
      left: left[key],
      right: right[key],
      total: left[key] + right[key]
    };
  });
}

function personResult(chart) {
  return {
    name: chart.input.name,
    pillars: chart.bazi.pillars,
    summary: chart.elementSummary,
    timeBasis: {
      locationLabel: chart.input.locationLabel,
      longitude: chart.normalizedTime.longitude,
      realSolarTime: chart.input.realSolarTime,
      ziHourMode: chart.normalizedTime.ziHourMode,
      correctedTime: chart.normalizedTime.solarTimeCorrection.correctedTime,
      correctionMinutes: chart.normalizedTime.solarTimeCorrection.totalCorrectionMinutes
    }
  };
}

function elementReference(left, right) {
  var complementary = Object.keys(ELEMENT_LABELS).filter(function (key) {
    return (left[key] === 0 && right[key] > 0) || (right[key] === 0 && left[key] > 0);
  }).map(function (key) { return ELEMENT_LABELS[key]; });
  return complementary.length
    ? "双方分布可在“" + complementary.join("、") + "”方面形成数量补充。"
    : "双方五行分布均有覆盖，重点查看数量差异和现实相处方式。";
}

function referenceSections(branchRelation, leftToRight, rightToLeft, leftCounts, rightCounts) {
  return [
    {
      label: "日支关系", value: branchRelation,
      detail: branchRelation === "日支相冲" ? "出现分歧时宜提前约定沟通和决策方式。" : "用于观察双方相处节奏，不作为关系结论。"
    },
    {
      label: "日干关系", value: leftToRight + " / " + rightToLeft,
      detail: "展示双方日主互见十神，描述关注方式，不作吉凶定级。"
    },
    { label: "五行互补", value: "数量参考", detail: elementReference(leftCounts, rightCounts) }
  ];
}

function build(leftInput, rightInput) {
  var left = chartBuilder.buildChart(buildInput(leftInput, "male"));
  var right = chartBuilder.buildChart(buildInput(rightInput, "female"));
  var leftDay = left.bazi.pillars.day;
  var rightDay = right.bazi.pillars.day;
  var branchRelation = relationFor(leftDay.charAt(1), rightDay.charAt(1));
  var leftToRight = bazi.tenGod(leftDay.charAt(0), rightDay.charAt(0));
  var rightToLeft = bazi.tenGod(rightDay.charAt(0), leftDay.charAt(0));
  var leftCounts = left.bazi.details.elementCounts;
  var rightCounts = right.bazi.details.elementCounts;
  return {
    left: personResult(left),
    right: personResult(right),
    branchRelation: branchRelation,
    stemRelation: left.input.name + "看对方为“" + leftToRight + "”，" + right.input.name + "看对方为“" + rightToLeft + "”。",
    elements: combinedElements(leftCounts, rightCounts),
    referenceSections: referenceSections(branchRelation, leftToRight, rightToLeft, leftCounts, rightCounts),
    summary: branchRelation === "日支六合"
      ? "双方日支形成六合，可继续结合沟通方式、现实条件和共同目标观察关系。"
      : branchRelation === "日支相冲"
        ? "双方日支形成相冲，遇到分歧时更需要明确沟通规则和决策边界。"
        : "当前日支未命中六合或六冲，继续结合双方五行分布和现实相处情况查看。",
    note: "本页展示四柱、十神、五行及时间口径的结构化关系，不作为婚姻结果保证。"
  };
}

module.exports = { build: build };
