var chart = require("../../core/format");
var api = require("../../core/api");
var calendar = require("../../core/calendar");
var bazi = require("../../core/bazi");
var fortune = require("../../core/features/fortune");

function yaoLines(bits) {
  return [bits[2], bits[1], bits[0]].map(function (solid, index) {
    return { id: index, solid: !!solid };
  });
}

var YI_BY_ZHI = {
  子: "祭祀 · 会友", 丑: "修造 · 入殓", 寅: "开市 · 出行", 卯: "订盟 · 纳采",
  辰: "立约 · 交易", 巳: "教学 · 求嗣", 午: "远行 · 谈判", 未: "安床 · 冠笄",
  申: "求财 · 开仓", 酉: "成服 · 移徙", 戌: "捕捉 · 畋猎", 亥: "嫁娶 · 进人口"
};
var JI_BY_ZHI = {
  子: "远行 · 开仓", 丑: "词讼 · 开市", 寅: "动土 · 安葬", 卯: "出行 · 词讼",
  辰: "嫁娶 · 开仓", 巳: "远行 · 开市", 午: "动土 · 争讼", 未: "出行 · 词讼",
  申: "安葬 · 开仓", 酉: "动土 · 嫁娶", 戌: "开市 · 远行", 亥: "词讼 · 开仓"
};

var featureItems = [
  { id: "bazi", icon: "/assets/compass/icons/bazi.png", title: "八字排盘", note: "四柱十神 · 紫微十二宫" },
  { id: "daily", icon: "/assets/compass/icons/daily.png", title: "每日运势", note: "当日干支 · 本命十神" },
  { id: "prayer", icon: "/assets/compass/icons/prayer.png", title: "祈福明灯", note: "记录愿心 · 见证行动" },
  { id: "question", icon: "/assets/compass/icons/question.png", title: "有事求卦", note: "一事一问 · 时间起卦" },
  { id: "liuyao", icon: "/assets/compass/icons/liuyao.png", title: "六爻排盘", note: "上下卦象 · 动爻推演" },
  { id: "compatibility", icon: "/assets/compass/icons/compatibility.png", title: "八字合婚", note: "双方四柱 · 五行关系" },
  { id: "wealth", icon: "/assets/compass/icons/wealth.png", title: "财富运程", note: "年度干支 · 财富主题" },
  { id: "consult", icon: "/assets/compass/icons/consult.png", title: "真人咨询", note: "专家排班 · 微信咨询" },
  { id: "naming", icon: "/assets/compass/icons/naming.png", title: "名号测算", note: "康熙笔画 · 五格数理" },
  { id: "wish", icon: "/assets/compass/icons/wish.png", title: "祈福好运", note: "心愿阁 · 个人记录" }
];

var compassSlots = [
  { id: "bazi", label: "八字排盘", gua: "离", note: "四柱十神 · 紫微十二宫", meta: "离为火 · 离中虚 · 正南 · 夏至 · 火", yao: [1, 0, 1], left: 41.67, top: 10.34 },
  { id: "daily", label: "每日运势", gua: "坤", note: "当日干支 · 本命十神", meta: "坤为地 · 坤六断 · 西南 · 立秋 · 土", yao: [0, 0, 0], left: 63.79, top: 19.54 },
  { id: "question", label: "有事求卦", gua: "兑", note: "一事一问 · 时间起卦", meta: "兑为泽 · 兑上缺 · 正西 · 秋分 · 金", yao: [1, 1, 0], left: 72.99, top: 41.67 },
  { id: "wealth", label: "财富运程", gua: "乾", note: "年度干支 · 财富主题", meta: "乾为天 · 乾三连 · 西北 · 立冬 · 金", yao: [1, 1, 1], left: 63.79, top: 63.79 },
  { id: "prayer", label: "祈福明灯", gua: "坎", note: "记录愿心 · 见证行动", meta: "坎为水 · 坎中满 · 正北 · 冬至 · 水", yao: [0, 1, 0], left: 41.67, top: 72.99 },
  { id: "compatibility", label: "八字合婚", gua: "艮", note: "双方四柱 · 五行关系", meta: "艮为山 · 艮覆碗 · 东北 · 立春 · 土", yao: [0, 0, 1], left: 19.54, top: 63.79 },
  { id: "liuyao", label: "六爻排盘", gua: "震", note: "上下卦象 · 动爻推演", meta: "震为雷 · 震仰盂 · 正东 · 春分 · 木", yao: [1, 0, 0], left: 10.34, top: 41.67 },
  { id: "wish", label: "祈福好运", gua: "巽", note: "心愿阁 · 个人记录", meta: "巽为风 · 巽下断 · 东南 · 立夏 · 木", yao: [0, 1, 1], left: 19.54, top: 19.54 }
];

function pad2(value) {
  return String(value).length < 2 ? "0" + value : String(value);
}

function todayDateText() {
  var now = new Date();
  return now.getFullYear() + "-" + pad2(now.getMonth() + 1) + "-" + pad2(now.getDate());
}

function todayPillarText() {
  var normalized = calendar.normalizeBirthInput({
    dateType: "solar",
    date: todayDateText() + " 12:00",
    location: "120",
    gender: "male",
    realSolarTime: false,
    ziHourMode: "early",
    leapMonth: false
  });
  return bazi.calculate(normalized, "male").pillars.day;
}

function buildTodayCard() {
  var pillar = "";
  var relation = "";
  try {
    pillar = todayPillarText();
  } catch (error) {
    pillar = "";
  }
  var stored = wx.getStorageSync("latestChartResult");
  if (stored && pillar) {
    try {
      relation = fortune.buildDaily(stored, todayDateText()).relation;
    } catch (error) {
      relation = "";
    }
  }
  var zhi = pillar ? pillar.charAt(1) : "";
  return {
    todayPillar: pillar,
    todayRelation: relation,
    todayMeta: pillar ? pillar + "日" + (relation ? " · " + relation : "") : "",
    todayYi: YI_BY_ZHI[zhi] || "祭祀 · 会友",
    todayJi: JI_BY_ZHI[zhi] || "妄动 · 争讼"
  };
}

function normalizeRecent(item) {
  var parts = String(item.date || "").trim().split(/\s+/);
  return Object.assign({}, item, {
    date: parts[0] || "1990-01-01",
    time: String(item.time || parts[1] || "12:00")
  });
}

function readRecentCharts() {
  return (wx.getStorageSync("recentCharts") || []).map(normalizeRecent);
}

function chartFieldForMessage(message) {
  var text = String(message || "");
  if (text.indexOf("经度") !== -1) return "location";
  if (text.indexOf("历法") !== -1) return "dateType";
  if (text.indexOf("1901") !== -1 || text.indexOf("1900-2049") !== -1 || text.indexOf("日期") !== -1 || text.indexOf("闰月") !== -1) return "date";
  if (text.indexOf("时间") !== -1) return "time";
  return "";
}

Page({
  data: {
    dateTypes: [
      { value: "solar", label: "阳历" },
      { value: "lunar", label: "农历" }
    ],
    dateType: "solar",
    date: "1990-01-01",
    time: "12:00",
    name: "",
    locationLabel: "",
    location: "120.00",
    gender: "male",
    realSolarTime: false,
    leapMonth: false,
    ziHourMode: "early",
    ziHourModes: [
      { value: "early", label: "早子时" },
      { value: "late", label: "晚子时" }
    ],
    advancedOpen: false,
    fieldErrors: {},
    recentCharts: [],
    compassSlots: compassSlots,
    selectedFeatureId: "bazi",
    selectedFeatureTitle: "八字排盘",
    selectedFeatureNote: "四柱十神 · 紫微十二宫",
    selectedFeatureMeta: compassSlots[0].meta,
    selectedFeatureIcon: "/assets/compass/icons/bazi.png",
    selectedYao: yaoLines(compassSlots[0].yao),
    todayPillar: "",
    todayRelation: "",
    todayMeta: "",
    todayYi: "祭祀 · 会友",
    todayJi: "妄动 · 争讼",
    dailyMarks: [
      { id: "career", label: "事业", mark: "事", tone: "coral", deg: 281 },
      { id: "love", label: "情感", mark: "情", tone: "ember", deg: 230 },
      { id: "wealth", label: "财运", mark: "财", tone: "ash", deg: 295 }
    ],
    portalItems: featureItems.map(function (item) {
      var slot = compassSlots.find(function (entry) { return entry.id === item.id; });
      return {
        id: item.id,
        title: item.title,
        note: item.note,
        icon: item.icon,
        gua: slot ? slot.gua + " · " + slot.meta.split(" · ")[0] : "",
        yao: slot ? yaoLines(slot.yao) : yaoLines(item.id === "consult" ? [1, 1, 0] : [0, 1, 1])
      };
    }),
    needleDegree: 0,
    showIntro: false,
    motionRunning: false,
    motionPaused: false,
    casting: false,
    featureItems: featureItems
  },

  onLoad: function () {
    var self = this;
    this.setData({ showIntro: true });
    this._spinTimer = setTimeout(function () { self.setData({ motionRunning: true }); }, 3500);
    this._introTimer = setTimeout(function () { self.setData({ showIntro: false }); }, 4400);
  },
  onHide: function () {
    clearTimeout(this._castTimer);
    clearTimeout(this._spinTimer);
    clearTimeout(this._introTimer);
    this.setData({ showIntro: false, casting: false, motionPaused: true, motionRunning: true });
  },
  onUnload: function () { this.onHide(); },
  onShow: function () {
    var recentCharts = readRecentCharts();
    wx.setStorageSync("recentCharts", recentCharts);
    this.setData(Object.assign({ recentCharts: recentCharts, motionPaused: false }, buildTodayCard()));
  },

  onNameInput: function (event) { this.setData({ name: event.detail.value }); },
  onLocationLabelInput: function (event) { this.setData({ locationLabel: event.detail.value }); },
  clearFieldError: function (field) {
    if (!this.data.fieldErrors || !this.data.fieldErrors[field]) return;
    var next = Object.assign({}, this.data.fieldErrors);
    delete next[field];
    this.setData({ fieldErrors: next });
  },
  toggleAdvanced: function () { this.setData({ advancedOpen: !this.data.advancedOpen }); },

  selectCompassTopic: function (event) {
    if (this.data.casting) return;
    var id = event.currentTarget.dataset.id;
    var slotIndex = compassSlots.findIndex(function (slot) { return slot.id === id; });
    var feature = this.data.featureItems.find(function (item) { return item.id === id; });
    if (slotIndex < 0 || !feature) return;
    this.setData({
      selectedFeatureId: id,
      selectedFeatureTitle: feature.title,
      selectedFeatureNote: feature.note,
      selectedFeatureMeta: compassSlots[slotIndex].meta,
      selectedFeatureIcon: feature.icon,
      selectedYao: yaoLines(compassSlots[slotIndex].yao),
      needleDegree: slotIndex * 45
    });
  },

  openCompassFeature: function () {
    if (this.data.casting) return;
    var self = this;
    var id = this.data.selectedFeatureId;
    this.setData({ casting: true });
    this._castTimer = setTimeout(function () {
      self.setData({ casting: false });
      self.onFeatureTap({ currentTarget: { dataset: { id: id } } });
    }, 2500);
  },

  onFeatureTap: function (event) {
    if (this.data.casting) return;
    var id = event.currentTarget.dataset.id;
    if (id === "bazi") {
      wx.pageScrollTo({ selector: "#chart-form", duration: 260 });
      return;
    }
    if (id === "recent" && this.data.recentCharts.length) {
      wx.pageScrollTo({ selector: "#recent-charts", duration: 260 });
      return;
    }
    if (id === "prayer" || id === "wish") {
      wx.navigateTo({ url: "/pages/prayer/prayer?mode=" + id });
      return;
    }
    wx.navigateTo({ url: "/pages/tools/tools?mode=" + id });
  },

  chooseDateType: function (event) {
    this.setData({ dateType: event.currentTarget.dataset.value });
    this.clearFieldError("dateType");
  },

  chooseGender: function (event) {
    this.setData({ gender: event.currentTarget.dataset.value });
  },

  chooseZiHour: function (event) {
    this.setData({ ziHourMode: event.currentTarget.dataset.value });
  },

  onDateChange: function (event) {
    this.setData({ date: event.detail.value });
    this.clearFieldError("date");
  },

  onTimeChange: function (event) {
    this.setData({ time: event.detail.value });
    this.clearFieldError("time");
  },

  onLocationInput: function (event) {
    this.setData({ location: event.detail.value });
    this.clearFieldError("location");
  },

  onRealSolarChange: function (event) {
    this.setData({ realSolarTime: event.detail.value });
  },

  onLeapMonthChange: function (event) {
    this.setData({ leapMonth: event.detail.value });
  },

  restoreChart: function (event) {
    var item = normalizeRecent(this.data.recentCharts[event.currentTarget.dataset.index] || {});
    if (!item) return;
    this.setData({
      name: item.name || "",
      locationLabel: item.locationLabel || "",
      dateType: item.dateType,
      date: item.date,
      time: item.time,
      location: item.location,
      gender: item.gender,
      realSolarTime: item.realSolarTime,
      leapMonth: item.leapMonth,
      ziHourMode: item.ziHourMode,
      advancedOpen: true,
    });
  },

  clearRecent: function () {
    var self = this;
    wx.showModal({
      title: "清空记录",
      content: "清空后无法恢复，确认继续吗？",
      success: function (result) {
        if (!result.confirm) return;
        wx.removeStorageSync("recentCharts");
        self.setData({ recentCharts: [] });
      }
    });
  },

  saveRecent: function (input) {
    var records = readRecentCharts();
    var normalized = normalizeRecent(input);
    var next = [{
      id: Date.now(), name: input.name, locationLabel: input.locationLabel,
      dateType: input.dateType, date: normalized.date, time: normalized.time,
      location: input.location, gender: input.gender, genderLabel: input.gender === "male" ? "男命" : "女命",
      realSolarTime: input.realSolarTime, leapMonth: input.leapMonth, ziHourMode: input.ziHourMode,
    }].concat(records.filter(function (item) {
      return item.date !== normalized.date || item.time !== normalized.time || item.name !== input.name;
    })).slice(0, 6);
    wx.setStorageSync("recentCharts", next);
  },

  submitChart: function () {
    var message;
    var field;
    var errors;
    this.setData({ fieldErrors: {} });
    try {
      var input = {
        name: this.data.name,
        locationLabel: this.data.locationLabel,
        dateType: this.data.dateType,
        date: this.data.date + " " + this.data.time,
        location: this.data.location,
        gender: this.data.gender,
        realSolarTime: this.data.realSolarTime,
        ziHourMode: this.data.ziHourMode,
        leapMonth: this.data.leapMonth
      };
      var result = chart.buildChart(input);
      this.saveRecent(input);
      getApp().globalData.chartResult = result;
      wx.setStorageSync("latestChartResult", result);
      api.syncChart({ input: input, result: result }, function () {});
      wx.navigateTo({ url: "/pages/result/result" });
    } catch (error) {
      message = error && error.message ? error.message : "请检查出生信息";
      field = chartFieldForMessage(message);
      if (field) {
        errors = {};
        errors[field] = message;
        this.setData({ fieldErrors: errors });
        return;
      }
      wx.showModal({
        title: "排盘失败",
        content: message,
        showCancel: false
      });
    }
  }
});
