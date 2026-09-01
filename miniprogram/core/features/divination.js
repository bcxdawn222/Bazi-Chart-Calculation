var calendar = require("../calendar");
var bazi = require("../bazi");
var constants = require("../constants");

var BRANCHES = constants.EARTHLY_BRANCHES;
var TRIGRAMS = {
  1: { name: "乾", nature: "天", lines: [1, 1, 1] },
  2: { name: "兑", nature: "泽", lines: [1, 1, 0] },
  3: { name: "离", nature: "火", lines: [1, 0, 1] },
  4: { name: "震", nature: "雷", lines: [1, 0, 0] },
  5: { name: "巽", nature: "风", lines: [0, 1, 1] },
  6: { name: "坎", nature: "水", lines: [0, 1, 0] },
  7: { name: "艮", nature: "山", lines: [0, 0, 1] },
  8: { name: "坤", nature: "地", lines: [0, 0, 0] }
};

function remainder(value, base) {
  var result = value % base;
  return result === 0 ? base : result;
}

function normalize(value) {
  return calendar.normalizeBirthInput({
    dateType: "solar",
    date: value,
    location: "120",
    gender: "male",
    realSolarTime: false,
    ziHourMode: "early",
    leapMonth: false
  });
}

function lineViews(lower, upper, movingLine) {
  return lower.lines.concat(upper.lines).map(function (solid, index) {
    return {
      position: index + 1,
      symbol: solid ? "━━━━━━" : "━━  ━━",
      moving: movingLine === index + 1
    };
  }).reverse();
}

function buildByTime(dateTime, question) {
  var normalized = normalize(dateTime);
  var yearPillar = bazi.calculate(normalized, "male").pillars.year;
  var yearBranchNumber = BRANCHES.indexOf(yearPillar.charAt(1)) + 1;
  var hourBranchNumber = Math.floor((normalized.hour + 1) / 2) % 12 + 1;
  var upperNumber = remainder(yearBranchNumber + normalized.lunar.month + normalized.lunar.day, 8);
  var total = yearBranchNumber + normalized.lunar.month + normalized.lunar.day + hourBranchNumber;
  var lowerNumber = remainder(total, 8);
  var movingLine = remainder(total, 6);
  var upper = TRIGRAMS[upperNumber];
  var lower = TRIGRAMS[lowerNumber];
  return {
    question: String(question || "").trim() || "未填写具体事项",
    dateTime: dateTime,
    lunarText: normalized.lunar.year + "年" + (normalized.lunar.isLeap ? "闰" : "") + normalized.lunar.month + "月" + normalized.lunar.day + "日",
    yearPillar: yearPillar,
    upper: upper,
    lower: lower,
    movingLine: movingLine,
    title: upper.nature + lower.nature + "相见",
    lines: lineViews(lower, upper, movingLine),
    formula: "上卦=（年支数+农历月+农历日）取8；下卦与动爻再加时支数，分别取8和取6。",
    note: "时间起卦存在不同流派，本结果按恢复源码中的记录生成，仅供传统文化研究与娱乐参考。"
  };
}

module.exports = { buildByTime: buildByTime };
