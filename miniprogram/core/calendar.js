var LUNAR_INFO = [
  19416, 19168, 42352, 21717, 53856, 55632, 91476, 22176, 39632, 21970,
  19168, 42422, 42192, 53840, 119381, 46400, 54944, 44450, 38320, 84343,
  18800, 42160, 46261, 27216, 27968, 109396, 11104, 38256, 21234, 18800,
  25958, 54432, 59984, 28309, 23248, 11104, 100067, 37600, 116951, 51536,
  54432, 120998, 46416, 22176, 107956, 9680, 37584, 53938, 43344, 46423,
  27808, 46416, 86869, 19872, 42448, 83315, 21200, 43432, 59728, 27296,
  44710, 43856, 19296, 43748, 42352, 21088, 62051, 55632, 23383, 22176,
  38608, 19925, 19152, 42192, 54484, 53840, 54616, 46400, 46496, 103846,
  38320, 18864, 43380, 42160, 45690, 27216, 27968, 44870, 43872, 38256,
  19189, 18800, 25776, 29859, 59984, 27480, 21952, 43872, 38613, 37600,
  51552, 55636, 54432, 55888, 30034, 22176, 43959, 9680, 37584, 51893,
  43344, 46240, 47780, 44368, 21977, 19360, 42416, 86390, 21168, 43312,
  31060, 27296, 44368, 23378, 19296, 42726, 42208, 53856, 60005, 54576,
  23200, 30371, 38608, 19415, 19152, 42192, 118966, 53840, 54560, 56645,
  46496, 22224, 21938, 18864, 42359, 42160, 43600, 111189, 27936, 44448
];

var BASE_UTC = Date.UTC(1900, 0, 31);
var DAY_MS = 86400000;
var MIN_LUNAR_YEAR = 1900;
var MAX_LUNAR_YEAR = MIN_LUNAR_YEAR + LUNAR_INFO.length - 1;
var MIN_CHART_UTC = Date.UTC(1901, 0, 6);
var solarTime = require("./solar_time");

function assertYear(year) {
  if (year < MIN_LUNAR_YEAR || year > MAX_LUNAR_YEAR) {
    throw new Error("当前恢复数据支持农历 1900-2049 年");
  }
}

function leapMonth(year) {
  assertYear(year);
  return LUNAR_INFO[year - 1900] & 15;
}

function leapDays(year) {
  var month = leapMonth(year);
  if (!month) return 0;
  return (LUNAR_INFO[year - 1900] & 65536) ? 30 : 29;
}

function monthDays(year, month) {
  assertYear(year);
  return (LUNAR_INFO[year - 1900] & (65536 >> month)) ? 30 : 29;
}

function yearDays(year) {
  var total = 348;
  var info = LUNAR_INFO[year - 1900];
  for (var bit = 32768; bit > 8; bit >>= 1) {
    if (info & bit) total += 1;
  }
  return total + leapDays(year);
}

function parseDateParts(value) {
  var match = String(value || "").trim().match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})$/);
  if (!match) {
    throw new Error("日期格式应为 YYYY-MM-DD HH:mm");
  }
  var parts = match.slice(1).map(function (item) { return Number(item); });
  if (parts[3] < 0 || parts[3] > 23 || parts[4] < 0 || parts[4] > 59) {
    throw new Error("出生时间超出 00:00-23:59 范围");
  }
  return {
    year: parts[0],
    month: parts[1],
    day: parts[2],
    hour: parts[3],
    minute: parts[4],
  };
}

function solarToLunar(year, month, day) {
  var date = Date.UTC(year, month - 1, day);
  var offset = Math.floor((date - BASE_UTC) / DAY_MS);
  if (offset < 0) throw new Error("出生日期早于恢复数据范围");
  var lunarYear = 1900;
  while (lunarYear <= MAX_LUNAR_YEAR) {
    var days = yearDays(lunarYear);
    if (offset < days) break;
    offset -= days;
    lunarYear += 1;
  }
  assertYear(lunarYear);
  var leap = leapMonth(lunarYear);
  var lunarMonth = 1;
  var isLeap = false;
  while (lunarMonth <= 12) {
    var daysInMonth = isLeap ? leapDays(lunarYear) : monthDays(lunarYear, lunarMonth);
    if (offset < daysInMonth) break;
    offset -= daysInMonth;
    if (leap && lunarMonth === leap && !isLeap) {
      isLeap = true;
    } else {
      if (isLeap) isLeap = false;
      lunarMonth += 1;
    }
  }
  return { year: lunarYear, month: lunarMonth, day: offset + 1, isLeap: isLeap };
}

function lunarToSolar(year, month, day, isLeap) {
  assertYear(year);
  if (month < 1 || month > 12 || day < 1 || day > 30) throw new Error("农历日期超出范围");
  if (isLeap && leapMonth(year) !== month) throw new Error("该年份没有对应闰月");
  var maxDay = isLeap ? leapDays(year) : monthDays(year, month);
  if (day > maxDay) throw new Error("农历日期超过当月天数");
  var offset = 0;
  for (var y = 1900; y < year; y += 1) offset += yearDays(y);
  for (var m = 1; m < month; m += 1) {
    offset += monthDays(year, m);
    if (leapMonth(year) === m) offset += leapDays(year);
  }
  if (isLeap) offset += monthDays(year, month);
  offset += day - 1;
  var date = new Date(BASE_UTC + offset * DAY_MS);
  return { year: date.getUTCFullYear(), month: date.getUTCMonth() + 1, day: date.getUTCDate() };
}

function longitudeFromLocation(location) {
  var text = String(location || "").trim();
  if (!text) return 120;
  if (!/^-?\d+(?:\.\d+)?$/.test(text)) throw new Error("出生地点经度应为数字");
  var longitude = Number(text);
  if (longitude < -180 || longitude > 180) throw new Error("出生地点经度应在 -180 至 180 之间");
  return longitude;
}

function normalizeBirthInput(input) {
  var date = parseDateParts(input.date);
  if (input.dateType !== "solar" && input.dateType !== "lunar") throw new Error("历法类型无效");
  if (input.dateType === "solar") {
    var sourceDate = new Date(Date.UTC(date.year, date.month - 1, date.day));
    if (sourceDate.getUTCFullYear() !== date.year || sourceDate.getUTCMonth() + 1 !== date.month || sourceDate.getUTCDate() !== date.day) {
      throw new Error("阳历日期不存在");
    }
  }
  var solar = input.dateType === "lunar"
    ? lunarToSolar(date.year, date.month, date.day, Boolean(input.leapMonth))
    : { year: date.year, month: date.month, day: date.day };
  var longitude = longitudeFromLocation(input.location);
  var wallTime = Date.UTC(solar.year, solar.month - 1, solar.day, date.hour, date.minute);
  var correction = solarTime.correct(wallTime, longitude, Boolean(input.realSolarTime));
  var adjusted = new Date(correction.timestamp);
  if (adjusted.getTime() < MIN_CHART_UTC) {
    throw new Error("完整排盘支持真太阳时调整后不早于 1901-01-06 的出生时间");
  }
  return {
    source: { year: date.year, month: date.month, day: date.day },
    solar: { year: adjusted.getUTCFullYear(), month: adjusted.getUTCMonth() + 1, day: adjusted.getUTCDate() },
    hour: adjusted.getUTCHours(),
    minute: adjusted.getUTCMinutes(),
    lunar: solarToLunar(adjusted.getUTCFullYear(), adjusted.getUTCMonth() + 1, adjusted.getUTCDate()),
    longitude: longitude,
    realSolarMinutes: correction.totalCorrectionMinutes,
    solarTimeCorrection: correction,
    ziHourMode: input.ziHourMode || "early",
    note: input.realSolarTime ? "已按经度及均时差换算真太阳时" : "未启用真太阳时换算",
  };
}

module.exports = {
  lunarInfo: LUNAR_INFO,
  leapMonth: leapMonth,
  leapDays: leapDays,
  monthDays: monthDays,
  yearDays: yearDays,
  solarToLunar: solarToLunar,
  lunarToSolar: lunarToSolar,
  normalizeBirthInput: normalizeBirthInput,
};
