var chart = require("../../core/format");
var api = require("../../core/api");

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
    this.setData({ recentCharts: wx.getStorageSync("recentCharts") || [] });
  },

  onNameInput: function (event) { this.setData({ name: event.detail.value }); },
  onLocationLabelInput: function (event) { this.setData({ locationLabel: event.detail.value }); },
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
  },

  chooseGender: function (event) {
    this.setData({ gender: event.currentTarget.dataset.value });
  },

  chooseZiHour: function (event) {
    this.setData({ ziHourMode: event.currentTarget.dataset.value });
  },

  onDateChange: function (event) {
    this.setData({ date: event.detail.value });
  },

  onTimeChange: function (event) {
    this.setData({ time: event.detail.value });
  },

  onLocationInput: function (event) {
    this.setData({ location: event.detail.value });
  },

  onRealSolarChange: function (event) {
    this.setData({ realSolarTime: event.detail.value });
  },

  onLeapMonthChange: function (event) {
    this.setData({ leapMonth: event.detail.value });
  },

  restoreChart: function (event) {
    var item = this.data.recentCharts[event.currentTarget.dataset.index];
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
    wx.removeStorageSync("recentCharts");
    this.setData({ recentCharts: [] });
  },

  saveRecent: function (input) {
    var records = wx.getStorageSync("recentCharts") || [];
    var next = [{
      id: Date.now(), name: input.name, locationLabel: input.locationLabel,
      dateType: input.dateType, date: input.date, time: input.time,
      location: input.location, gender: input.gender, genderLabel: input.gender === "male" ? "男命" : "女命",
      realSolarTime: input.realSolarTime, leapMonth: input.leapMonth, ziHourMode: input.ziHourMode,
    }].concat(records.filter(function (item) {
      return item.date !== input.date || item.time !== input.time || item.name !== input.name;
    })).slice(0, 6);
    wx.setStorageSync("recentCharts", next);
  },

  submitChart: function () {
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
      wx.showModal({
        title: "排盘失败",
        content: error && error.message ? error.message : "请检查出生信息",
        showCancel: false
      });
    }
  }
});
