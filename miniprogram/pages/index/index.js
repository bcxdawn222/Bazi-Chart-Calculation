var chart = require("../../core/format");
var api = require("../../core/api");

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
    featureItems: [
      { id: "bazi", icon: "/assets/features/bazi.png", title: "八字排盘", note: "四柱十神" },
      { id: "daily", icon: "/assets/features/daily.png", title: "每日运势", note: "今日提示" },
      { id: "prayer", icon: "/assets/features/prayer.png", title: "祈福明灯", note: "祈愿记录" },
      { id: "question", icon: "/assets/features/question.png", title: "有事求卦", note: "时间起卦" },
      { id: "liuyao", icon: "/assets/features/liuyao.png", title: "六爻排盘", note: "卦象动爻" },
      { id: "compatibility", icon: "/assets/features/compatibility.png", title: "八字合婚", note: "双方命盘" },
      { id: "wealth", icon: "/assets/features/wealth.png", title: "2026 财富运程", note: "年度趋势" },
      { id: "consult", icon: "/assets/features/consult.png", title: "真人在线 1v1", note: "微信咨询" },
      { id: "naming", icon: "/assets/features/naming.png", title: "名号测算", note: "五格数理" },
      { id: "wish", icon: "/assets/features/wish.png", title: "祈福好运", note: "心愿阁" }
    ]
  },

  onShow: function () {
    var recentCharts = readRecentCharts();
    wx.setStorageSync("recentCharts", recentCharts);
    this.setData({ recentCharts: recentCharts });
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

  onFeatureTap: function (event) {
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
