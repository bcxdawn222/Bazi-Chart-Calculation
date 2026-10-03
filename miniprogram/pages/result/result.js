var chart = require("../../core/format");
var api = require("../../core/api");
var orderTracker = require("../../core/order_tracker");

var ANALYSIS_KEYS = ["wealth", "marriage", "career", "personality", "health"];
var ANALYSIS_LABELS = {
  wealth: { label: "财富", mark: "财" },
  marriage: { label: "婚姻", mark: "缘" },
  career: { label: "运程", mark: "运" },
  personality: { label: "性格", mark: "性" },
  health: { label: "健康", mark: "养" }
};
var POLL_MAX_ATTEMPTS = 6;
var POLL_INTERVAL_MS = 1500;

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
        stem: item.pillar.charAt(0),
        branch: item.pillar.charAt(1),
        hiddenStemsText: item.hiddenStems.map(function (hidden) {
          return hidden.stem + "（" + hidden.tenGod + "）";
        }).join(" ") || "—",
      });
    }),
    evidenceLevel: details.evidenceLevel,
  };
}

function analysisCards(source) {
  return ANALYSIS_KEYS.map(function (key) {
    return {
      key: key,
      label: ANALYSIS_LABELS[key].label,
      mark: ANALYSIS_LABELS[key].mark,
      text: source[key]
    };
  });
}

function sectionTexts(sections) {
  if (!sections || typeof sections !== "object") return [];
  return ANALYSIS_KEYS.filter(function (key) {
    return typeof sections[key] === "string" && sections[key];
  }).map(function (key) {
    return {
      key: key,
      label: ANALYSIS_LABELS[key].label,
      mark: ANALYSIS_LABELS[key].mark,
      text: sections[key]
    };
  });
}

function emptyAnalysisState(extra) {
  return Object.assign({
    analysisPaid: false,
    detailedSections: [],
    analysisReason: "",
    analysisUnlockEnabled: false,
    analysisPriceText: "",
    analysisBusy: false,
    analysisSource: "",
    analysisCanContinue: false
  }, extra || {});
}

function loadAnalysisUnlock(page) {
  var environment = api.environmentStatus();
  if (!environment.online) {
    page.setData(emptyAnalysisState({
      analysisReason: api.userMessage(environment.reason)
    }));
    return;
  }
  page.setData({ analysisBusy: true, analysisReason: "" });
  api.login(function (loginResult) {
    if (page.analysisDisposed) return;
    api.getConfig(function (configResult) {
      if (page.analysisDisposed) return;
      if (!configResult.ok) {
        page.setData(emptyAnalysisState({
          analysisBusy: false,
          analysisReason: configResult.message
        }));
        return;
      }
      var analysis = configResult.data && configResult.data.analysis || {};
      var enabled = Boolean(analysis.enabled);
      var priceText = analysis.price_cents == null ? "" : (Number(analysis.price_cents) / 100).toFixed(2);
      if (!loginResult.ok) {
        page.setData({
          analysisBusy: false,
          analysisPaid: false,
          detailedSections: [],
          analysisUnlockEnabled: enabled,
          analysisPriceText: enabled ? priceText : "",
          analysisSource: "",
          analysisCanContinue: false,
          analysisReason: loginResult.message || analysis.reason || ""
        });
        return;
      }
      page.setData({
        analysisUnlockEnabled: enabled,
        analysisPriceText: enabled ? priceText : "",
        analysisReason: enabled ? "" : (analysis.reason || "")
      });
      page.refreshAnalysisState();
    });
  });
}

Page({
  data: emptyAnalysisState({
    hasResult: false,
    dayMasterStem: "",
    motionPaused: false,
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
  }),

  onShow: function () {
    this.analysisActive = true;
    this.setData({ motionPaused: false });
  },
  onHide: function () {
    this.analysisActive = false;
    this.setData({ motionPaused: true });
    this.stopAnalysisPoll();
  },
  onUnload: function () {
    this.analysisDisposed = true;
    this.analysisActive = false;
    this.stopAnalysisPoll();
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
    wx.navigateBack({ delta: 1, fail: function () { wx.reLaunch({ url: "/pages/index/index" }); } });
  },

  onShareAppMessage: function () {
    return { title: "八字紫微命盘", path: "/pages/index/index" };
  },

  stopAnalysisPoll: function () {
    if (this.analysisPollTimer) clearTimeout(this.analysisPollTimer);
    this.analysisPollTimer = null;
  },

  loadAnalysisUnlock: function () {
    loadAnalysisUnlock(this);
  },

  refreshAnalysisState: function () {
    var page = this;
    var chartKey = this._chartKey;
    if (!chartKey) {
      this.setData({ analysisBusy: false });
      return;
    }
    var pending = 2;
    var orderItem = null;
    var reportItem = null;
    var fetchReason = "";
    var done = function () {
      pending -= 1;
      if (pending) return;
      if (page.analysisDisposed) return;
      page.analysisOrderId = orderItem && orderItem.id || page.analysisOrderId;
      if (orderItem && orderItem.payment_status !== "paid") {
        page.setData({
          analysisBusy: false,
          analysisPaid: false,
          detailedSections: [],
          analysisSource: "",
          analysisCanContinue: true,
          analysisReason: fetchReason || "可继续支付"
        });
        return;
      }
      if (orderItem && orderItem.payment_status === "paid") {
        page.applyPaidServerState(reportItem, fetchReason);
        return;
      }
      page.setData({
        analysisBusy: false,
        analysisPaid: false,
        detailedSections: [],
        analysisSource: "",
        analysisCanContinue: false,
        analysisReason: fetchReason || page.data.analysisReason
      });
    };
    api.getAnalysisOrder(chartKey, function (response) {
      if (!response.ok) fetchReason = response.message;
      else orderItem = response.data && response.data.item;
      done();
    });
    api.getAnalysisReport(chartKey, function (response) {
      if (!response.ok) fetchReason = response.message;
      else reportItem = response.data && response.data.item;
      done();
    });
  },

  applyPaidServerState: function (item, fallbackReason) {
    var detailed = item && item.paid === true ? sectionTexts(item.sections) : [];
    this.setData({
      analysisBusy: false,
      analysisPaid: true,
      detailedSections: detailed,
      analysisSource: item && item.source || "pending",
      analysisCanContinue: false,
      analysisReason: detailed.length ? "" : (item && item.reason || fallbackReason || "详细解读尚未生成")
    });
  },

  applyAnalysisReport: function (item) {
    if (!item || item.paid !== true) {
      this.setData({
        analysisBusy: false,
        detailedSections: [],
        analysisSource: item && item.source || "pending",
        analysisReason: item && item.reason || this.data.analysisReason || "详细解读尚未生成"
      });
      return;
    }
    var detailed = sectionTexts(item.sections);
    this.setData({
      analysisBusy: false,
      analysisPaid: true,
      detailedSections: detailed,
      analysisSource: item.source || "",
      analysisCanContinue: false,
      analysisReason: detailed.length ? "" : (item.reason || "详细解读尚未生成")
    });
  },

  unlockAnalysis: function () {
    if (this.data.analysisBusy || !this.data.analysisUnlockEnabled) return;
    var page = this;
    var chartKey = this._chartKey;
    this.setData({ analysisBusy: true, analysisReason: "" });
    api.createAnalysisOrder({ chart_key: chartKey, subject: "详细解读" }, function (response) {
      if (page.analysisDisposed) return;
      if (!response.ok) {
        page.setData({
          analysisBusy: false,
          analysisReason: response.message,
          analysisCanContinue: true
        });
        page.refreshAnalysisState();
        return;
      }
      var order = response.data && response.data.item;
      page.analysisOrderId = order && order.id;
      page.prepareAnalysisPayment(page.analysisOrderId);
    });
  },

  continueAnalysisPayment: function () {
    if (this.data.analysisBusy || !this.analysisOrderId) return;
    this.prepareAnalysisPayment(this.analysisOrderId);
  },

  prepareAnalysisPayment: function (orderId) {
    var page = this;
    if (!orderId) {
      this.setData({ analysisBusy: false, analysisReason: "订单尚未创建" });
      return;
    }
    if (!this.analysisActive) {
      this.setData({
        analysisBusy: false,
        analysisCanContinue: true,
        analysisReason: "支付已暂停，可返回页面继续支付"
      });
      return;
    }
    this.setData({ analysisBusy: true, analysisCanContinue: false });
    api.prepareOrderPayment(orderId, function (response) {
      if (page.analysisDisposed) return;
      if (!page.analysisActive) {
        page.setData({
          analysisBusy: false,
          analysisCanContinue: true,
          analysisReason: "支付已暂停，可返回页面继续支付"
        });
        return;
      }
      if (!response.ok) {
        page.setData({
          analysisBusy: false,
          analysisCanContinue: true,
          analysisReason: response.message
        });
        return;
      }
      wx.requestPayment(Object.assign({}, response.data.payment, {
        success: function () {
          if (page.analysisDisposed) return;
          page.setData({
            analysisBusy: true,
            analysisPaid: false,
            detailedSections: [],
            analysisReason: "支付结果确认中"
          });
          page.pollAnalysisOrder(orderId, 0);
        },
        fail: function (error) {
          if (page.analysisDisposed) return;
          var cancelled = error && String(error.errMsg || "").indexOf("cancel") >= 0;
          page.setData({
            analysisBusy: false,
            analysisPaid: false,
            detailedSections: [],
            analysisCanContinue: true,
            analysisReason: cancelled ? "支付已取消，可继续支付" : "支付未完成，可继续支付"
          });
        }
      }));
    });
  },

  pollAnalysisOrder: function (orderId, attempt) {
    var page = this;
    if (attempt === 0) this.stopAnalysisPoll();
    api.getOrder(orderId, function (response) {
      if (page.analysisDisposed || !page.analysisActive) return;
      if (!response.ok) {
        page.setData({
          analysisBusy: false,
          analysisPaid: false,
          detailedSections: [],
          analysisReason: response.message
        });
        return;
      }
      var order = response.data.item;
      if (order.payment_status === "paid") {
        page.loadPaidAnalysisReport();
        return;
      }
      if (!orderTracker.shouldPoll(order, attempt, POLL_MAX_ATTEMPTS)) {
        page.setData({
          analysisBusy: false,
          analysisPaid: false,
          detailedSections: [],
          analysisCanContinue: true,
          analysisReason: "支付确认仍在处理中，请稍后重试"
        });
        return;
      }
      page.analysisPollTimer = setTimeout(function () {
        page.pollAnalysisOrder(orderId, attempt + 1);
      }, POLL_INTERVAL_MS);
    });
  },

  loadPaidAnalysisReport: function () {
    var page = this;
    var chartKey = this._chartKey;
    this.setData({
      analysisBusy: true,
      analysisPaid: true,
      detailedSections: [],
      analysisCanContinue: false,
      analysisReason: "详细解读尚未生成"
    });
    api.getAnalysisReport(chartKey, function (response) {
      if (page.analysisDisposed) return;
      if (!response.ok) {
        page.setData({
          analysisBusy: false,
          analysisPaid: true,
          detailedSections: [],
          analysisSource: "pending",
          analysisReason: response.message || "详细解读尚未生成"
        });
        return;
      }
      var item = response.data && response.data.item;
      if (item && item.paid === true && sectionTexts(item.sections).length) {
        page.applyAnalysisReport(item);
        return;
      }
      page.generatePaidReport();
    });
  },

  retryGenerate: function () {
    if (this.data.analysisBusy) return;
    this.generatePaidReport();
  },

  generatePaidReport: function () {
    var page = this;
    this.setData({ analysisBusy: true });
    api.generateAnalysisReport({
      chart_key: this._chartKey,
      chart: this._chartResult
    }, function (response) {
      if (page.analysisDisposed) return;
      if (!response.ok) {
        page.setData({
          analysisBusy: false,
          analysisPaid: true,
          detailedSections: [],
          analysisSource: "pending",
          analysisCanContinue: false,
          analysisReason: response.message || "详细解读尚未生成"
        });
        return;
      }
      page.applyAnalysisReport(response.data && response.data.item);
    });
  },

  onLoad: function () {
    var result = getApp().globalData.chartResult || wx.getStorageSync("latestChartResult");
    if (!result) return;
    if (!chart.isValidChart(result)) {
      getApp().globalData.chartResult = null;
      wx.removeStorageSync("latestChartResult");
      wx.showModal({
        title: "命盘数据已失效",
        content: "本地命盘来自旧版本或已损坏，请返回首页重新排盘。",
        showCancel: false
      });
      return;
    }
    var labels = { year: "年柱", month: "月柱", day: "日柱", hour: "时柱" };
    var pillars = Object.keys(labels).map(function (key) {
      return { label: labels[key], value: result.bazi.pillars[key], tenGod: result.bazi.tenGods[key] };
    });
    var analysis = analysisCards(result.analysis);
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
      { key: "wood", label: "木", color: "#8b9877" },
      { key: "fire", label: "火", color: "#e8825f" },
      { key: "earth", label: "土", color: "#b08968" },
      { key: "metal", label: "金", color: "#d8d3c8" },
      { key: "water", label: "水", color: "#7e9ab0" },
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
    this.analysisDisposed = false;
    this.analysisActive = true;
    this._chartResult = result;
    this._chartKey = chart.buildChartKey(result);
    this.setData(emptyAnalysisState({
      hasResult: true,
      dayMasterStem: result.bazi.pillars.day.charAt(0),
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
    }));
    loadAnalysisUnlock(this);
  }
});
