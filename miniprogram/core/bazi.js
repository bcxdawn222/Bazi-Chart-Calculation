var constants = require("./constants");
var solarTerms = require("./solar_terms");

var STEMS = constants.HEAVENLY_STEMS;
var BRANCHES = constants.EARTHLY_BRANCHES;
var ELEMENTS = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4];
var CYCLE = [];
for (var i = 0; i < 60; i += 1) CYCLE.push(STEMS[i % 10] + BRANCHES[i % 12]);

function mod(value, base) {
  return ((value % base) + base) % base;
}

function cycleIndex(stemIndex, branchIndex) {
  for (var index = 0; index < 60; index += 1) {
    if (index % 10 === stemIndex && index % 12 === branchIndex) return index;
  }
  return 0;
}

function yearPillar(normalized) {
  var year = normalized.solar.year;
  var lichunDay = solarTerms.sectionalTermDay(year, 2);
  if (normalized.solar.month < 2 || (normalized.solar.month === 2 && normalized.solar.day < lichunDay)) year -= 1;
  return CYCLE[mod(year - 4, 60)];
}

function monthPillar(normalized, yearValue) {
  var month = normalized.solar.month;
  if (normalized.solar.day < solarTerms.sectionalTermDay(normalized.solar.year, month)) month -= 1;
  if (month < 1) month = 12;
  var branchIndex = month % 12;
  var monthOrder = mod(branchIndex - 2, 12);
  var yearStemIndex = STEMS.indexOf(yearValue.charAt(0));
  var starts = [2, 4, 6, 8, 0];
  var startStem = starts[yearStemIndex % 5];
  return STEMS[mod(startStem + monthOrder, 10)] + BRANCHES[branchIndex];
}

function dayPillar(normalized) {
  var date = Date.UTC(normalized.solar.year, normalized.solar.month - 1, normalized.solar.day);
  if (normalized.ziHourMode === "late" && normalized.hour >= 23) date += 86400000;
  var base = Date.UTC(2000, 0, 1);
  var days = Math.floor((date - base) / 86400000);
  return CYCLE[mod(54 + days, 60)];
}

function hourPillar(normalized, dayValue) {
  var branchIndex = Math.floor((normalized.hour + 1) / 2) % 12;
  var dayStemIndex = STEMS.indexOf(dayValue.charAt(0));
  var starts = [0, 2, 4, 6, 8];
  var stemIndex = mod(starts[dayStemIndex % 5] + branchIndex, 10);
  return STEMS[stemIndex] + BRANCHES[branchIndex];
}

function tenGod(dayStem, otherStem) {
  var dayIndex = STEMS.indexOf(dayStem);
  var otherIndex = STEMS.indexOf(otherStem);
  var dayElement = ELEMENTS[dayIndex];
  var otherElement = ELEMENTS[otherIndex];
  var samePolarity = dayIndex % 2 === otherIndex % 2;
  if (dayElement === otherElement) return samePolarity ? "比肩" : "劫财";
  if ((dayElement + 1) % 5 === otherElement) return samePolarity ? "食神" : "伤官";
  if ((dayElement + 2) % 5 === otherElement) return samePolarity ? "偏财" : "正财";
  if ((otherElement + 2) % 5 === dayElement) return samePolarity ? "七杀" : "正官";
  return samePolarity ? "偏印" : "正印";
}

function formatAge(totalMonths) {
  var years = Math.floor(totalMonths / 12);
  var months = totalMonths % 12;
  return years + "岁" + (months ? months + "个月" : "");
}

function buildDayun(monthValue, yearValue, gender, normalized) {
  var monthIndex = CYCLE.indexOf(monthValue);
  var yearStemIndex = STEMS.indexOf(yearValue.charAt(0));
  var yangYear = yearStemIndex % 2 === 0;
  var forward = (gender === "male" && yangYear) || (gender === "female" && !yangYear);
  var startAgeMonths = Math.max(0, Math.round(solarTerms.distanceToSectionalMinutes(normalized, forward) / 360));
  var result = [];
  for (var i = 1; i <= 8; i += 1) {
    var itemStartMonths = startAgeMonths + (i - 1) * 120;
    result.push({
      pillar: CYCLE[mod(monthIndex + (forward ? i : -i), 60)],
      startAge: Math.floor(itemStartMonths / 12),
      endAge: Math.floor((itemStartMonths + 119) / 12),
      ageRange: formatAge(itemStartMonths) + "-" + formatAge(itemStartMonths + 119),
    });
  }
  return {
    direction: forward ? "顺排" : "逆排",
    items: result,
    startAgeMonths: startAgeMonths,
    startAgeStatus: "起运约" + formatAge(startAgeMonths) + "（按恢复节气日期折算，节气分钟待样例核验）"
  };
}

function buildLiunian() {
  var currentYear = new Date().getFullYear();
  var result = [];
  for (var i = 0; i < 6; i += 1) {
    result.push({ year: currentYear + i, pillar: CYCLE[mod(currentYear + i - 4, 60)] });
  }
  return result;
}

function buildShensha(pillars) {
  var dayStem = pillars.day.charAt(0);
  var branches = [pillars.year, pillars.month, pillars.day, pillars.hour].map(function (item) { return item.charAt(1); });
  var rules = {
    天乙: { 甲: "丑未", 戊: "丑未", 乙: "子申", 己: "子申", 丙: "亥酉", 丁: "亥酉", 壬: "卯巳", 癸: "卯巳", 庚: "寅午", 辛: "寅午" },
    文昌: { 甲: "巳", 乙: "午", 丙: "申", 丁: "酉", 戊: "申", 己: "酉", 庚: "亥", 辛: "子", 壬: "寅", 癸: "卯" },
    禄神: { 甲: "寅", 乙: "卯", 丙: "巳", 丁: "午", 戊: "巳", 己: "午", 庚: "申", 辛: "酉", 壬: "亥", 癸: "子" },
  };
  var result = [];
  Object.keys(rules).forEach(function (name) {
    branches.forEach(function (branch, index) {
      if ((rules[name][dayStem] || "").indexOf(branch) >= 0) {
        result.push({ name: name, position: ["年", "月", "日", "时"][index] + "支" });
      }
    });
  });
  return result;
}

function calculate(normalized, gender) {
  var year = yearPillar(normalized);
  var month = monthPillar(normalized, year);
  var day = dayPillar(normalized);
  var hour = hourPillar(normalized, day);
  var pillars = { year: year, month: month, day: day, hour: hour };
  var dayStem = day.charAt(0);
  return {
    pillars: pillars,
    tenGods: {
      year: tenGod(dayStem, year.charAt(0)),
      month: tenGod(dayStem, month.charAt(0)),
      day: "日主",
      hour: tenGod(dayStem, hour.charAt(0)),
    },
    dayun: buildDayun(month, year, gender, normalized),
    liunian: buildLiunian(),
    shensha: buildShensha(pillars),
    confidence: {
      pillars: "按恢复源码节气日期规则计算，节气分钟待样例核验",
      tenGods: "本地算法",
      dayunStartAge: "按恢复节气日期折算，节气分钟待样例核验",
    },
  };
}

module.exports = { calculate: calculate, tenGod: tenGod, cycle: CYCLE };
