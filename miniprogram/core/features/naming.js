var strokeData = require("../../data/kangxi-strokes.js");

function assertText(value, label) {
  var text = String(value || "").trim();
  if (!text) throw new Error("请输入" + label);
  if (!/^[\u3400-\u9fff]{1,2}$/.test(text)) throw new Error(label + "应为 1-2 个汉字");
  return text;
}

function lookupCharacter(character) {
  var key = character;
  if (!strokeData.chars[key] && strokeData.alias[key]) key = strokeData.alias[key];
  if (!strokeData.chars[key] && strokeData.traditional[key]) key = strokeData.traditional[key];
  var entry = strokeData.chars[key];
  if (!entry) throw new Error("字库暂未收录“" + character + "”，请核对姓名或补充客户认可字典");
  return { character: character, lookupCharacter: key, stroke: entry.k, traditional: entry.t || key };
}

function lookupText(text) {
  return text.split("").map(lookupCharacter);
}

function elementFor(number) {
  return ["水", "木", "木", "火", "火", "土", "土", "金", "金", "水"][number % 10];
}

function grid(name, number) {
  return { name: name, number: number, element: elementFor(number) };
}

function chartReference(chart) {
  if (!chart) return null;
  if (!chart.bazi || !chart.bazi.pillars || !chart.bazi.details) {
    throw new Error("关联命盘数据不完整，请重新排盘");
  }
  return {
    dayMaster: chart.bazi.pillars.day.charAt(0),
    dayPillar: chart.bazi.pillars.day,
    elementSummary: chart.elementSummary,
    note: "关联命盘只展示日主和五行数量，不据此推导旺衰、喜用神或姓名吉凶。"
  };
}

function calculate(surnameValue, givenValue, chart) {
  var surname = assertText(surnameValue, "姓氏");
  var given = assertText(givenValue, "名字");
  var surnameDetails = lookupText(surname);
  var givenDetails = lookupText(given);
  var surnameStrokes = surnameDetails.map(function (item) { return item.stroke; });
  var givenStrokes = givenDetails.map(function (item) { return item.stroke; });
  var compoundSurname = surname.length === 2;
  var singleGiven = given.length === 1;
  var heaven = compoundSurname ? surnameStrokes[0] + surnameStrokes[1] : surnameStrokes[0] + 1;
  var person = surnameStrokes[surnameStrokes.length - 1] + givenStrokes[0];
  var earth = givenStrokes.reduce(function (sum, item) { return sum + item; }, 0) + (singleGiven ? 1 : 0);
  var outside = compoundSurname
    ? surnameStrokes[0] + (singleGiven ? 1 : givenStrokes[givenStrokes.length - 1])
    : (singleGiven ? 2 : givenStrokes[givenStrokes.length - 1] + 1);
  var total = surnameStrokes.concat(givenStrokes).reduce(function (sum, item) { return sum + item; }, 0);
  return {
    fullName: surname + given,
    characters: surnameDetails.concat(givenDetails),
    grids: [grid("天格", heaven), grid("人格", person), grid("地格", earth), grid("外格", outside), grid("总格", total)],
    threeTalents: elementFor(heaven) + "·" + elementFor(person) + "·" + elementFor(earth),
    chartReference: chartReference(chart),
    note: "笔画由 shunshi-ai/kangxi-mcp 常用字数据自动读取，按康熙笔画口径计算；繁体字与异体字按数据源规则归一。"
  };
}

module.exports = { calculate: calculate, lookupText: lookupText };
