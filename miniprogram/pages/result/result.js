function formatTime(normalized) {
  var solar = normalized.solar;
  var lunar = normalized.lunar;
  var pad = function (value) { return value < 10 ? "0" + value : String(value); };
  return {
    solar: solar.year + "-" + pad(solar.month) + "-" + pad(solar.day) + " " + pad(normalized.hour) + ":" + pad(normalized.minute),
    lunar: lunar.year + "年" + (lunar.isLeap ? "闰" : "") + lunar.month + "月" + lunar.day + "日",
    note: normalized.note + "（" + normalized.realSolarMinutes + " 分钟）",
    correction: normalized.solarTimeCorrection,
  };
}

function formatBaziDetails(details) {
  var labels = { year: "年柱", month: "月柱", day: "日柱", hour: "时柱" };
  return {
    pillars: details.pillars.map(function (item) {
      return Object.assign({}, item, {
        label: labels[item.key],
        hiddenStemsText: item.hiddenStems.map(function (hidden) {
          return hidden.stem + "（" + hidden.tenGod + "）";
        }).join(" ") || "—",
      });
    }),
    evidenceLevel: details.evidenceLevel,
  };
}

Page({
  data: {
    hasResult: false,
    time: {},
    pillars: [],
    dayun: [],
    liunian: [],
    shensha: [],
    palaces: [],
    analysis: [],
    elementSummary: "",
    bureau: "",
    lifePalace: "",
    bodyPalace: "",
    ziweiPosition: "",
    confidence: "",
    chartName: "",
    locationLabel: "",
    genderLabel: "",
    activeTab: "overview",
    selectedPalace: null,
    elementBars: [],
    fourTransformations: []
  },

  onTabChange: function (event) {
    var tab = event.currentTarget.dataset.tab;
    this.setData({ activeTab: tab });
    if (wx.pageScrollTo) {
      wx.pageScrollTo({ selector: "#section-" + tab, duration: 260 });
    }
  },

  selectPalace: function (event) {
    var item = this.data.palaces[event.currentTarget.dataset.index];
    if (item) this.setData({ selectedPalace: item });
  },

  backToInput: function () {
    wx.navigateBack({ delta: 1 });
  },

  onShareAppMessage: function () {
    return { title: "八字紫微命盘", path: "/pages/index/index" };
  },

  onLoad: function () {
    var result = getApp().globalData.chartResult || wx.getStorageSync("latestChartResult");
    if (!result) return;
    var labels = { year: "年柱", month: "月柱", day: "日柱", hour: "时柱" };
    var pillars = Object.keys(labels).map(function (key) {
      return { label: labels[key], value: result.bazi.pillars[key], tenGod: result.bazi.tenGods[key] };
    });
    var analysisLabels = {
      wealth: { label: "财富", mark: "财" },
      marriage: { label: "婚姻", mark: "缘" },
      career: { label: "运程", mark: "运" },
      personality: { label: "性格", mark: "性" },
      health: { label: "健康", mark: "养" }
    };
    var analysis = Object.keys(analysisLabels).map(function (key) {
      return {
        label: analysisLabels[key].label,
        mark: analysisLabels[key].mark,
        text: result.analysis[key]
      };
    });
    var palaces = result.ziwei.palaces.map(function (palace) {
      return Object.assign({}, palace, {
        mainStarsText: palace.mainStars.length ? palace.mainStars.join(" ") : "—",
        auxiliaryStarsText: palace.auxiliaryStars.length ? palace.auxiliaryStars.join(" ") : "—",
        luckyStarsText: palace.luckyStars.length ? palace.luckyStars.join(" ") : "—",
        maleficStarsText: palace.maleficStars.length ? palace.maleficStars.join(" ") : "—",
        brightnessText: palace.brightness.length
          ? palace.brightness.map(function (item) { return item.star + "·" + item.level; }).join(" ")
          : "—",
        relatedText: "对宫 " + palace.relatedPalaces.opposite + "；三合 " + palace.relatedPalaces.trines.join("、"),
      });
    });
    var baziDetailView = formatBaziDetails(result.bazi.details);
    var fourTransformations = [];
    palaces.forEach(function (palace) {
      palace.transformations.forEach(function (item) {
        fourTransformations.push({
          name: item.name,
          star: item.star,
          palace: palace.name
        });
      });
    });
    var elementLabels = [
      { key: "wood", label: "木", color: "#4f8b68" },
      { key: "fire", label: "火", color: "#b85b42" },
      { key: "earth", label: "土", color: "#b87935" },
      { key: "metal", label: "金", color: "#8a8f98" },
      { key: "water", label: "水", color: "#537997" },
    ];
    var maxElement = Math.max.apply(null, elementLabels.map(function (item) {
      return result.bazi.details.elementCounts[item.key];
    }).concat([1]));
    var elementBars = elementLabels.map(function (item) {
      var value = result.bazi.details.elementCounts[item.key];
      var total = elementLabels.reduce(function (sum, current) {
        return sum + result.bazi.details.elementCounts[current.key];
      }, 0) || 1;
      return Object.assign({}, item, {
        value: value,
        width: Math.round(value / maxElement * 100),
        percent: Math.round(value / total * 100)
      });
    });
    this.setData({
      hasResult: true,
      time: formatTime(result.normalizedTime),
      baziDetails: baziDetailView.pillars,
      baziDetailsEvidence: baziDetailView.evidenceLevel,
      pillars: pillars,
      dayun: result.bazi.dayun.items,
      dayunDirection: result.bazi.dayun.direction,
      dayunStatus: result.bazi.dayun.startAgeStatus,
      liunian: result.ziwei.liunian,
      shensha: result.bazi.shensha,
      palaces: palaces,
      analysis: analysis,
      elementSummary: result.elementSummary,
      bureau: result.ziwei.bureau,
      lifePalace: result.ziwei.lifePalace,
      bodyPalace: result.ziwei.bodyPalace,
      ziweiPosition: result.ziwei.ziweiPosition,
      confidence: result.ziwei.confidence,
      ziweiDetailsEvidence: result.ziwei.details.evidenceLevel,
      chartName: result.input.name || "本命盘",
      locationLabel: result.input.locationLabel || "出生地未标注",
      genderLabel: result.input.gender === "female" ? "女命" : "男命",
      activeTab: "overview",
      selectedPalace: palaces[0] || null,
      elementBars: elementBars,
      fourTransformations: fourTransformations,
    });
  }
});
