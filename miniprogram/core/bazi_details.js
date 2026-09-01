var bazi = require("./bazi");
var constants = require("./constants");

var STEM_ELEMENTS = {
  甲: "wood", 乙: "wood", 丙: "fire", 丁: "fire", 戊: "earth",
  己: "earth", 庚: "metal", 辛: "metal", 壬: "water", 癸: "water",
};

var HIDDEN_STEMS = {
  子: ["癸"], 丑: ["己", "癸", "辛"], 寅: ["甲", "丙", "戊"],
  卯: ["乙"], 辰: ["戊", "乙", "癸"], 巳: ["丙", "戊", "庚"],
  午: ["丁", "己"], 未: ["己", "丁", "乙"], 申: ["庚", "壬", "戊"],
  酉: ["辛"], 戌: ["戊", "辛", "丁"], 亥: ["壬", "甲"],
};

var NAYIN = [
  "海中金", "炉中火", "大林木", "路旁土", "剑锋金", "山头火", "涧下水", "城头土",
  "白蜡金", "杨柳木", "泉中水", "屋上土", "霹雳火", "松柏木", "长流水", "沙中金",
  "山下火", "平地木", "壁上土", "金箔金", "覆灯火", "天河水", "大驿土", "钗钏金",
  "桑柘木", "大溪水", "沙中土", "天上火", "石榴木", "大海水",
];

function countElements(pillars) {
  var counts = { wood: 0, fire: 0, earth: 0, metal: 0, water: 0 };
  pillars.forEach(function (pillar) {
    var stems = [pillar.charAt(0)].concat(HIDDEN_STEMS[pillar.charAt(1)] || []);
    stems.forEach(function (stem) {
      var element = STEM_ELEMENTS[stem];
      if (!element) throw new Error("未找到天干五行映射：" + stem);
      counts[element] += 1;
    });
  });
  return counts;
}

function nayinFor(pillar) {
  var index = bazi.cycle.indexOf(pillar);
  if (index < 0) throw new Error("未找到六十甲子：" + pillar);
  return NAYIN[Math.floor(index / 2)];
}

function detailFor(key, pillar, dayStem) {
  var branch = pillar.charAt(1);
  var hiddenStems = (HIDDEN_STEMS[branch] || []).map(function (stem) {
    return { stem: stem, tenGod: bazi.tenGod(dayStem, stem) };
  });
  return {
    key: key,
    pillar: pillar,
    hiddenStems: hiddenStems,
    nayin: nayinFor(pillar),
  };
}

function calculate(pillars) {
  var order = ["year", "month", "day", "hour"];
  var dayStem = pillars.day.charAt(0);
  var pillarDetails = order.map(function (key) { return detailFor(key, pillars[key], dayStem); });
  return {
    pillars: pillarDetails,
    elementCounts: countElements(order.map(function (key) { return pillars[key]; })),
    evidenceLevel: "base1 activity_bz_show_form.xml 藏干/纳音字段；固定映射仅用于客观展示",
  };
}

module.exports = {
  calculate: calculate,
  hiddenStems: HIDDEN_STEMS,
  nayin: NAYIN,
  elements: STEM_ELEMENTS,
  branches: constants.EARTHLY_BRANCHES,
};
