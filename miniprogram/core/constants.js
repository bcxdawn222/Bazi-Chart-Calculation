var HEAVENLY_STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"];
var EARTHLY_BRANCHES = ["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"];
var FIVE_ELEMENTS = ["木", "木", "火", "火", "土", "土", "金", "金", "水", "水"];
var PALACE_NAMES = ["命宫", "兄弟", "夫妻", "子女", "财帛", "疾厄", "迁移", "奴仆", "官禄", "田宅", "福德", "父母"];
var MAIN_STARS = ["紫微", "天机", "太阳", "武曲", "天同", "廉贞", "天府", "太阴", "贪狼", "巨门", "天相", "天梁", "七杀", "破军"];
var AUXILIARY_STARS = ["文昌", "文曲", "左辅", "右弼", "天魁", "天钺", "禄存", "擎羊", "陀罗", "火星", "铃星"];
var TRANSFORMATION_TABLE = {
  甲: ["廉贞", "破军", "武曲", "太阳"],
  乙: ["天机", "天梁", "紫微", "太阴"],
  丙: ["天同", "天机", "文昌", "廉贞"],
  丁: ["太阴", "天同", "天机", "巨门"],
  戊: ["贪狼", "太阴", "右弼", "天机"],
  己: ["武曲", "贪狼", "天梁", "文曲"],
  庚: ["太阳", "武曲", "天同", "天相"],
  辛: ["巨门", "太阳", "文曲", "文昌"],
  壬: ["天梁", "紫微", "左辅", "武曲"],
  癸: ["破军", "巨门", "太阴", "贪狼"]
};

module.exports = {
  HEAVENLY_STEMS: HEAVENLY_STEMS,
  EARTHLY_BRANCHES: EARTHLY_BRANCHES,
  FIVE_ELEMENTS: FIVE_ELEMENTS,
  PALACE_NAMES: PALACE_NAMES,
  MAIN_STARS: MAIN_STARS,
  AUXILIARY_STARS: AUXILIARY_STARS,
  TRANSFORMATION_TABLE: TRANSFORMATION_TABLE,
};
