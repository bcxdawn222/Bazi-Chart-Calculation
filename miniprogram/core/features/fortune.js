var calendar = require("../calendar");
var bazi = require("../bazi");
var constants = require("../constants");

var STEM_ELEMENTS = {
  甲: "木", 乙: "木", 丙: "火", 丁: "火", 戊: "土",
  己: "土", 庚: "金", 辛: "金", 壬: "水", 癸: "水"
};

var RELATION_TEXT = {
  比肩: "适合检查自己的节奏与边界，重要事项宜明确分工。",
  劫财: "涉及共同资源时宜先确认规则，避免临时改变安排。",
  食神: "适合输出、整理和持续推进已有事项。",
  伤官: "表达欲较强，沟通时宜先确认对方关注点。",
  偏财: "可关注新的资源信息，投入前仍需核对成本与条件。",
  正财: "适合处理预算、账目和可量化的长期安排。",
  七杀: "任务压力可能较集中，宜拆分优先级并保留余量。",
  正官: "适合按规则推进，检查流程和交付要求会更有效。",
  偏印: "适合研究、复盘和补充知识，不宜只凭单一信息判断。",
  正印: "适合学习、整理资料和寻求专业意见。"
};

function assertChart(chart) {
  if (!chart || !chart.bazi || !chart.bazi.pillars || !chart.bazi.details) {
    throw new Error("请先完成八字排盘，再查看运势内容");
  }
}

function parseDate(value) {
  var match = String(value || "").match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (!match) throw new Error("日期格式应为 YYYY-MM-DD");
  var year = Number(match[1]);
  var month = Number(match[2]);
  var day = Number(match[3]);
  var date = new Date(Date.UTC(year, month - 1, day));
  if (date.getUTCFullYear() !== year || date.getUTCMonth() + 1 !== month || date.getUTCDate() !== day) {
    throw new Error("日期不存在");
  }
  return { year: year, month: month, day: day };
}

function dayPillar(parts) {
  var normalized = calendar.normalizeBirthInput({
    dateType: "solar",
    date: parts.year + "-" + String(parts.month).padStart(2, "0") + "-" + String(parts.day).padStart(2, "0") + " 12:00",
    location: "120",
    gender: "male",
    realSolarTime: false,
    ziHourMode: "early",
    leapMonth: false
  });
  return bazi.calculate(normalized, "male").pillars.day;
}

function relationFor(chart, targetStem) {
  return bazi.tenGod(chart.bazi.pillars.day.charAt(0), targetStem);
}

function buildDaily(chart, value) {
  assertChart(chart);
  var parts = parseDate(value);
  var pillar = dayPillar(parts);
  var relation = relationFor(chart, pillar.charAt(0));
  var text = RELATION_TEXT[relation];
  return {
    title: value + " 每日运势",
    pillar: pillar,
    relation: relation,
    summary: "当日天干与日主形成“" + relation + "”关系。" + text,
    sections: [
      { label: "事业", text: relation === "正官" || relation === "七杀" ? "先处理时限明确的任务，再安排弹性事项。" : "围绕一项主任务推进，减少并行事项。" },
      { label: "财运", text: relation === "正财" || relation === "偏财" ? "财星关系较明显，适合核对收支、合同与资源条件。" : "以预算和现金流检查为主，避免把参考内容当作投资依据。" },
      { label: "感情", text: relation === "比肩" || relation === "劫财" ? "沟通中先明确双方责任和可接受边界。" : "适合用具体事实确认彼此预期。" },
      { label: "健康", text: "当日五行属" + STEM_ELEMENTS[pillar.charAt(0)] + "，保持正常作息，并按实际身体状态安排活动。" },
      { label: "行动建议", text: text }
    ],
    evidence: "依据本命日主与当日天干的十神关系生成，不替代财务、医疗或其他专业判断。"
  };
}

function buildYear(chart, year) {
  assertChart(chart);
  var targetYear = Number(year);
  if (!Number.isInteger(targetYear) || targetYear < 1901 || targetYear > 2049) {
    throw new Error("年度应在 1901-2049 之间");
  }
  var pillar = bazi.cycle[((targetYear - 4) % 60 + 60) % 60];
  var relation = relationFor(chart, pillar.charAt(0));
  var focuses = ["年度预算", "稳定收入", "合同条款", "学习投入", "家庭支出", "风险准备", "资源合作", "长期储备", "工作回报", "现金流", "年度复盘", "次年计划"];
  return {
    title: targetYear + " 财富运程",
    pillar: pillar,
    relation: relation,
    summary: "年度干支为" + pillar + "，年度天干与日主形成“" + relation + "”关系。" + RELATION_TEXT[relation],
    wealthNote: relation === "正财" || relation === "偏财"
      ? "财星信息较明显，仍应以实际收入、风险承受能力和合同条件为准。"
      : "本年度重点放在稳定现金流、预算纪律和可复核的长期安排。",
    months: focuses.map(function (focus, index) {
      return { month: index + 1, focus: focus };
    }),
    evidence: "基于本命日主与年度天干关系生成，属于传统文化研究与娱乐参考。"
  };
}

module.exports = { buildDaily: buildDaily, buildYear: buildYear };
