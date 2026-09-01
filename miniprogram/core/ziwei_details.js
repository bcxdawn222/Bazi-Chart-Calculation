var constants = require("./constants");

var BRANCHES = constants.EARTHLY_BRANCHES;
var MAIN_STARS = constants.MAIN_STARS;
var AUXILIARY_STARS = ["左辅", "右弼", "文昌", "文曲", "天魁", "天钺", "擎羊", "陀罗", "火星", "铃星"];
var LUCKY_STARS = ["左辅", "右弼", "文昌", "文曲", "天魁", "天钺"];
var MALEFIC_STARS = ["擎羊", "陀罗", "火星", "铃星"];

var MAIN_BRIGHTNESS = [
  ["平", "庙", "陷", "旺", "旺", "平", "庙", "庙", "旺", "旺", "庙", "庙", "旺", "庙"],
  ["庙", "陷", "不", "庙", "不", "利", "庙", "庙", "庙", "不", "庙", "旺", "庙", "旺"],
  ["旺", "得", "旺", "得", "利", "庙", "庙", "陷", "平", "庙", "庙", "庙", "庙", "得"],
  ["旺", "旺", "庙", "利", "平", "平", "得", "陷", "利", "庙", "陷", "庙", "旺", "陷"],
  ["得", "利", "旺", "庙", "平", "利", "庙", "陷", "庙", "平", "得", "庙", "庙", "旺"],
  ["旺", "平", "旺", "平", "庙", "陷", "得", "陷", "陷", "旺", "得", "陷", "平", "平"],
  ["庙", "庙", "旺", "旺", "陷", "平", "旺", "不", "旺", "旺", "庙", "庙", "旺", "庙"],
  ["庙", "陷", "得", "庙", "不", "利", "庙", "利", "庙", "不", "得", "旺", "庙", "旺"],
  ["旺", "得", "得", "得", "旺", "庙", "得", "利", "平", "庙", "庙", "陷", "庙", "得"],
  ["旺", "旺", "平", "利", "平", "平", "旺", "旺", "利", "庙", "陷", "平", "旺", "陷"],
  ["得", "利", "不", "庙", "平", "利", "庙", "旺", "庙", "平", "得", "庙", "庙", "旺"],
  ["旺", "平", "陷", "平", "庙", "陷", "得", "庙", "陷", "旺", "得", "陷", "平", "平"],
];

var AUXILIARY_BRIGHTNESS = [
  ["旺", "旺", "得", "得", "庙", "庙", "陷", "", "陷", "陷"],
  ["庙", "庙", "庙", "庙", "旺", "旺", "庙", "庙", "得", "得"],
  ["旺", "旺", "陷", "平", "庙", "庙", "得", "陷", "庙", "庙"],
  ["庙", "庙", "利", "旺", "庙", "庙", "陷", "", "利", "旺"],
  ["庙", "庙", "得", "得", "庙", "庙", "庙", "庙", "陷", "陷"],
  ["旺", "旺", "庙", "庙", "庙", "庙", "", "陷", "得", "得"],
  ["旺", "旺", "陷", "陷", "庙", "庙", "陷", "", "庙", "庙"],
  ["庙", "庙", "利", "旺", "旺", "旺", "庙", "庙", "利", "旺"],
  ["旺", "旺", "得", "得", "庙", "庙", "", "陷", "陷", "陷"],
  ["旺", "旺", "庙", "庙", "庙", "庙", "陷", "", "得", "得"],
  ["庙", "庙", "陷", "陷", "庙", "庙", "庙", "庙", "庙", "庙"],
  ["旺", "旺", "利", "旺", "庙", "庙", "", "陷", "利", "旺"],
];

function mod(value, base) {
  return ((value % base) + base) % base;
}

function branchIndex(branch) {
  var index = BRANCHES.indexOf(branch);
  if (index < 0) throw new Error("未找到地支：" + branch);
  return index;
}

function brightnessFor(branch, mainStars, auxiliaryStars) {
  var index = branchIndex(branch);
  var brightness = [];
  mainStars.forEach(function (star) {
    var starIndex = MAIN_STARS.indexOf(star);
    if (starIndex >= 0 && MAIN_BRIGHTNESS[index][starIndex]) {
      brightness.push({ star: star, level: MAIN_BRIGHTNESS[index][starIndex] });
    }
  });
  auxiliaryStars.forEach(function (star) {
    var starIndex = AUXILIARY_STARS.indexOf(star);
    if (starIndex >= 0 && AUXILIARY_BRIGHTNESS[index][starIndex]) {
      brightness.push({ star: star, level: AUXILIARY_BRIGHTNESS[index][starIndex] });
    }
  });
  return brightness;
}

function relatedPalaces(palaceIndex) {
  return {
    opposite: BRANCHES[mod(palaceIndex + 6, 12)],
    trines: [BRANCHES[mod(palaceIndex + 4, 12)], BRANCHES[mod(palaceIndex + 8, 12)]],
  };
}

function calculate(palaces) {
  return {
    palaces: palaces.map(function (palace, index) {
      var luckyStars = palace.auxiliaryStars.filter(function (star) { return LUCKY_STARS.indexOf(star) >= 0; });
      var maleficStars = palace.auxiliaryStars.filter(function (star) { return MALEFIC_STARS.indexOf(star) >= 0; });
      return Object.assign({}, palace, {
        luckyStars: luckyStars,
        maleficStars: maleficStars,
        brightness: brightnessFor(palace.branch, palace.mainStars, palace.auxiliaryStars),
        relatedPalaces: relatedPalaces(index),
      });
    }),
    luckyStars: LUCKY_STARS,
    maleficStars: MALEFIC_STARS,
    evidenceLevel: "base1 ZwView.y 与 u2/m.java 星曜亮度表；当前仅返回已有安星路径命中的星曜",
  };
}

module.exports = { calculate: calculate, luckyStars: LUCKY_STARS, maleficStars: MALEFIC_STARS };
