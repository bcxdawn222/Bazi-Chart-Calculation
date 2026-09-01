var DAY_MS = 86400000;
var PI = Math.PI;

function round(value, digits) {
  var factor = Math.pow(10, digits);
  return Math.round(value * factor) / factor;
}

function dayOfYear(date) {
  var start = Date.UTC(date.getUTCFullYear(), 0, 1);
  var current = Date.UTC(date.getUTCFullYear(), date.getUTCMonth(), date.getUTCDate());
  return Math.floor((current - start) / DAY_MS) + 1;
}

function equationOfTimeMinutes(date) {
  var day = dayOfYear(date);
  var angle = (2 * PI * (day - 81)) / 364;
  return 9.87 * Math.sin(2 * angle) - 7.53 * Math.cos(angle) - 1.5 * Math.sin(angle);
}

function formatUtc(date) {
  var pad = function (value) { return value < 10 ? "0" + value : String(value); };
  return date.getUTCFullYear() + "-" + pad(date.getUTCMonth() + 1) + "-" + pad(date.getUTCDate())
    + " " + pad(date.getUTCHours()) + ":" + pad(date.getUTCMinutes());
}

function sameUtcDate(first, second) {
  return first.getUTCFullYear() === second.getUTCFullYear()
    && first.getUTCMonth() === second.getUTCMonth()
    && first.getUTCDate() === second.getUTCDate();
}

function correct(wallTime, longitude, enabled) {
  var source = new Date(wallTime);
  var longitudeMinutes = enabled ? (longitude - 120) * 4 : 0;
  var equation = enabled ? equationOfTimeMinutes(source) : 0;
  var total = enabled ? round(longitudeMinutes + equation, 2) : 0;
  var adjusted = new Date(wallTime + Math.round(total * 60000));
  return {
    timestamp: adjusted.getTime(),
    sourceTime: formatUtc(source),
    longitudeMinutes: round(longitudeMinutes, 2),
    equationOfTimeMinutes: round(equation, 2),
    totalCorrectionMinutes: total,
    correctedTime: formatUtc(adjusted),
    crossedDateBoundary: !sameUtcDate(source, adjusted),
  };
}

module.exports = {
  correct: correct,
  equationOfTimeMinutes: equationOfTimeMinutes,
};
