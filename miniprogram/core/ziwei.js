var constants = require("./constants");

var STEMS = constants.HEAVENLY_STEMS;
var BRANCHES = constants.EARTHLY_BRANCHES;
var PALACES = constants.PALACE_NAMES;
var MAIN_STARS = constants.MAIN_STARS;

var BUREAUS = {
  甲乙: ["金四", "水二", "火六", "金四", "水二", "火六"],
  丙丁: ["水二", "火六", "土五", "水二", "火六", "土五"],
  戊己: ["火六", "土五", "木三", "火六", "土五", "木三"],
  庚辛: ["土五", "木三", "金四", "土五", "木三", "金四"],
  壬癸: ["木三", "金四", "水二", "木三", "金四", "水二"],
};

var ZIWEI_POSITIONS = {
  水二: ["丑", "寅", "寅", "卯", "卯", "辰", "辰", "巳", "巳", "午", "午", "未", "未", "申", "申", "酉", "酉", "戌", "戌", "亥", "亥", "子", "子", "丑", "丑", "寅", "寅", "卯", "卯", "辰"],
  木三: ["辰", "丑", "寅", "巳", "寅", "卯", "午", "卯", "辰", "未", "辰", "巳", "申", "巳", "午", "酉", "午", "未", "戌", "未", "申", "亥", "申", "酉", "子", "酉", "戌", "丑", "戌", "亥"],
  金四: ["亥", "辰", "丑", "寅", "子", "巳", "寅", "卯", "丑", "午", "卯", "辰", "寅", "未", "辰", "巳", "卯", "申", "巳", "午", "辰", "酉", "午", "未", "巳", "戌", "未", "申", "午", "亥"],
  土五: ["午", "亥", "辰", "丑", "寅", "未", "子", "巳", "寅", "卯", "申", "丑", "午", "卯", "辰", "酉", "寅", "未", "辰", "巳", "戌", "卯", "申", "巳", "午", "亥", "辰", "酉", "午", "未"],
  火六: ["酉", "午", "亥", "辰", "丑", "寅", "戌", "未", "子", "巳", "寅", "卯", "亥", "申", "丑", "午", "卯", "辰", "子", "酉", "寅", "未", "辰", "巳", "丑", "戌", "卯", "申", "巳", "午"],
};

function mod(value, base) {
  return ((value % base) + base) % base;
}

function branchIndex(branch) {
  return BRANCHES.indexOf(branch);
}

function stemPair(stem) {
  var index = STEMS.indexOf(stem);
  return ["甲乙", "丙丁", "戊己", "庚辛", "壬癸"][Math.floor(index / 2)];
}

function bureauFor(yearStem, lifeBranch) {
  var group = Math.floor(branchIndex(lifeBranch) / 2);
  return BUREAUS[stemPair(yearStem)][group];
}

function bureauNumber(name) {
  return { 水二: 2, 木三: 3, 金四: 4, 土五: 5, 火六: 6 }[name];
}

function palaceMap(lifeBranch) {
  var lifeIndex = branchIndex(lifeBranch);
  return BRANCHES.map(function (branch, index) {
    return { branch: branch, name: PALACES[mod(lifeIndex - index, 12)], mainStars: [], auxiliaryStars: [], transformations: [] };
  });
}

function placeStar(palaces, branch, field, star) {
  var target = palaces[branchIndex(branch)];
  if (target && target[field].indexOf(star) < 0) target[field].push(star);
}

function placeMainStars(palaces, ziweiBranch) {
  var ziweiIndex = branchIndex(ziweiBranch);
  var tianfuIndex = mod(4 - ziweiIndex, 12);
  var positions = [
    ziweiIndex,
    mod(ziweiIndex - 1, 12), mod(ziweiIndex - 3, 12), mod(ziweiIndex - 4, 12),
    mod(ziweiIndex - 5, 12), mod(ziweiIndex - 8, 12), tianfuIndex,
    mod(tianfuIndex + 1, 12), mod(tianfuIndex + 2, 12), mod(tianfuIndex + 3, 12),
    mod(tianfuIndex + 4, 12), mod(tianfuIndex + 5, 12), mod(tianfuIndex + 6, 12),
    mod(tianfuIndex + 10, 12),
  ];
  MAIN_STARS.forEach(function (star, index) {
    placeStar(palaces, BRANCHES[positions[index]], "mainStars", star);
  });
}

function placeAuxiliaryStars(palaces, lunarMonth, hourIndex, yearStem) {
  placeStar(palaces, BRANCHES[mod(lunarMonth + 3, 12)], "auxiliaryStars", "左辅");
  placeStar(palaces, BRANCHES[mod(11 - lunarMonth, 12)], "auxiliaryStars", "右弼");
  placeStar(palaces, BRANCHES[mod(10 - hourIndex, 12)], "auxiliaryStars", "文昌");
  placeStar(palaces, BRANCHES[mod(4 + hourIndex, 12)], "auxiliaryStars", "文曲");
  var stemRules = {
    甲: ["卯", "丑", "未", "丑", "寅"], 乙: ["辰", "寅", "申", "子", "卯"],
    丙: ["午", "辰", "酉", "亥", "巳"], 丁: ["未", "巳", "酉", "亥", "午"],
    戊: ["午", "辰", "未", "丑", "巳"], 己: ["未", "巳", "申", "子", "午"],
    庚: ["酉", "未", "未", "丑", "申"], 辛: ["戌", "申", "寅", "午", "酉"],
    壬: ["子", "戌", "巳", "卯", "亥"], 癸: ["丑", "亥", "巳", "卯", "子"],
  };
  ["擎羊", "陀罗", "天钺", "天魁", "禄存"].forEach(function (star, index) {
    placeStar(palaces, stemRules[yearStem][index], "auxiliaryStars", star);
  });
}

function applyTransformations(palaces, yearStem) {
  var names = ["化禄", "化权", "化科", "化忌"];
  var stars = constants.TRANSFORMATION_TABLE[yearStem];
  stars.forEach(function (star, index) {
    palaces.forEach(function (palace) {
      if (palace.mainStars.indexOf(star) >= 0 || palace.auxiliaryStars.indexOf(star) >= 0) {
        palace.transformations.push({ name: names[index], star: star });
      }
    });
  });
}

function buildLiunian(baziResult) {
  return baziResult.liunian.map(function (item) {
    return { year: item.year, pillar: item.pillar, lifePalace: item.pillar.charAt(1) };
  });
}

function calculate(normalized, baziResult, gender) {
  var lunar = normalized.lunar;
  var hourIndex = Math.floor((normalized.hour + 1) / 2) % 12;
  var lifeIndex = mod(2 + lunar.month - 1 - hourIndex, 12);
  var bodyIndex = mod(2 + lunar.month - 1 + hourIndex, 12);
  var lifeBranch = BRANCHES[lifeIndex];
  var bodyBranch = BRANCHES[bodyIndex];
  var yearStem = baziResult.pillars.year.charAt(0);
  var bureau = bureauFor(yearStem, lifeBranch);
  var ziweiBranch = ZIWEI_POSITIONS[bureau][Math.max(1, Math.min(30, lunar.day)) - 1];
  var palaces = palaceMap(lifeBranch);
  placeMainStars(palaces, ziweiBranch);
  placeAuxiliaryStars(palaces, lunar.month, hourIndex, yearStem);
  applyTransformations(palaces, yearStem);
  var yearStemIndex = STEMS.indexOf(yearStem);
  var forward = (gender === "male" && yearStemIndex % 2 === 0) || (gender === "female" && yearStemIndex % 2 === 1);
  palaces.forEach(function (palace, index) {
    var order = forward ? mod(index - lifeIndex, 12) : mod(lifeIndex - index, 12);
    var start = bureauNumber(bureau) + order * 10;
    palace.daxian = start + "-" + (start + 9);
  });
  return {
    lifePalace: lifeBranch,
    bodyPalace: bodyBranch,
    bureau: bureau,
    ziweiPosition: ziweiBranch,
    palaces: palaces,
    mainStars: MAIN_STARS,
    auxiliaryStars: constants.AUXILIARY_STARS,
    transformations: ["化禄", "化权", "化科", "化忌"],
    liunian: buildLiunian(baziResult),
    confidence: "依据恢复源码 u2.m 表格迁移，待客户样例终验",
  };
}

module.exports = { calculate: calculate };
