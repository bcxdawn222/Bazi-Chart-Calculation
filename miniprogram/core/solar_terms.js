var CENTURY_VALUES = [
  [4.6295, 19.4599, 6.3826, 21.4155, 5.59, 20.888, 6.318, 21.86, 6.5, 22.2, 7.928, 23.65, 8.35, 23.95, 8.44, 23.822, 9.098, 24.218, 8.218, 23.08, 7.9, 22.6, 6.11, 20.84],
  [3.87, 18.73, 5.63, 20.646, 4.81, 20.1, 5.52, 21.04, 5.678, 21.37, 7.108, 22.83, 7.5, 23.13, 7.646, 23.042, 8.318, 23.438, 7.438, 22.36, 7.18, 21.94, 5.4055, 20.12]
];

var INCREASE_OFFSETS = {
  3: [2084], 7: [2008], 8: [1902], 9: [1928], 10: [1925, 2016],
  11: [1922], 12: [2002], 14: [1927], 15: [1942], 17: [2089],
  18: [2089], 19: [1978], 20: [1954], 22: [1982], 23: [2082]
};
var DECREASE_OFFSETS = { 1: [2026], 21: [1918, 2021], 22: [2019] };
var SECTIONAL_TERM_INDEX = [22, 0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20];

function hasYear(map, termIndex, year) {
  return (map[termIndex] || []).indexOf(year) >= 0;
}

function isLeapYear(year) {
  return (year % 4 === 0 && year % 100 !== 0) || year % 400 === 0;
}

function termDay(year, termIndex) {
  if (year < 1901 || year > 2100) throw new Error("恢复的节气算法支持 1901-2100 年");
  if (termIndex < 0 || termIndex > 23) throw new Error("节气序号超出范围");
  var century = year <= 2000 ? 0 : 1;
  var shortYear = year % 100;
  if (isLeapYear(year) && [22, 23, 0, 1].indexOf(termIndex) >= 0) shortYear -= 1;
  var day = Math.floor(shortYear * 0.2422 + CENTURY_VALUES[century][termIndex]) - Math.floor(shortYear / 4);
  if (hasYear(INCREASE_OFFSETS, termIndex, year)) day += 1;
  if (hasYear(DECREASE_OFFSETS, termIndex, year)) day -= 1;
  return day;
}

function sectionalTermDay(year, month) {
  if (month < 1 || month > 12) throw new Error("月份超出范围");
  return termDay(year, SECTIONAL_TERM_INDEX[month - 1]);
}

function sectionalTermTimestamp(year, month) {
  return Date.UTC(year, month - 1, sectionalTermDay(year, month));
}

function birthTimestamp(normalized) {
  return Date.UTC(
    normalized.solar.year, normalized.solar.month - 1, normalized.solar.day,
    normalized.hour, normalized.minute
  );
}

function adjacentSectionalTimestamp(normalized, forward) {
  var year = normalized.solar.year;
  var month = normalized.solar.month;
  var birth = birthTimestamp(normalized);
  var current = sectionalTermTimestamp(year, month);
  if (forward) {
    if (birth < current) return current;
    return month === 12 ? sectionalTermTimestamp(year + 1, 1) : sectionalTermTimestamp(year, month + 1);
  }
  if (birth >= current) return current;
  return month === 1 ? sectionalTermTimestamp(year - 1, 12) : sectionalTermTimestamp(year, month - 1);
}

function distanceToSectionalMinutes(normalized, forward) {
  return Math.abs(adjacentSectionalTimestamp(normalized, forward) - birthTimestamp(normalized)) / 60000;
}

module.exports = {
  termDay: termDay,
  sectionalTermDay: sectionalTermDay,
  distanceToSectionalMinutes: distanceToSectionalMinutes
};
