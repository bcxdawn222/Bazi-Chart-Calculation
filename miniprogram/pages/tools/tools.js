var fortune = require("../../core/features/fortune");
var divination = require("../../core/features/divination");
var compatibility = require("../../core/features/compatibility");
var naming = require("../../core/features/naming");
var consultation = require("./consultation");

var MODE_META = {
  daily: { mark: "日", title: "每日运势", subtitle: "读取最近命盘，查看当日结构化提示" },
  wealth: { mark: "财", title: "2026 财富运程", subtitle: "按本命日主与年度干支查看财富主题" },
  question: { mark: "问", title: "有事求卦", subtitle: "填写所问事项，按时间起卦" },
  liuyao: { mark: "爻", title: "六爻排盘", subtitle: "按恢复源码的时间起卦口径排出上下卦和动爻" },
  compatibility: { mark: "缘", title: "八字合婚", subtitle: "录入双方出生信息，查看四柱与五行关系" },
  naming: { mark: "名", title: "名号测算", subtitle: "自动读取康熙笔画并计算五格" },
  consult: { mark: "师", title: "真人在线 1v1", subtitle: "通过微信客服咨询，费用与排班以运营配置为准" }
};

function pad(value) { return value < 10 ? "0" + value : String(value); }

function todayParts() {
  var now = new Date();
  return {
    date: now.getFullYear() + "-" + pad(now.getMonth() + 1) + "-" + pad(now.getDate()),
    time: pad(now.getHours()) + ":" + pad(now.getMinutes())
  };
}

function pillarsForView(pillars) {
  return [
    { label: "年柱", value: pillars.year },
    { label: "月柱", value: pillars.month },
    { label: "日柱", value: pillars.day },
    { label: "时柱", value: pillars.hour }
  ];
}

Page(Object.assign({
  data: Object.assign({
    mode: "daily",
    meta: MODE_META.daily,
    date: "",
    time: "",
    year: 2026,
    question: "",
    hasChart: false,
    result: null,
    leftName: "",
    leftDate: "1990-01-01",
    leftTime: "12:00",
    leftLocationLabel: "",
    leftLocation: "120",
    leftRealSolarTime: true,
    leftZiHourMode: "early",
    rightName: "",
    rightDate: "1990-01-01",
    rightTime: "12:00",
    rightLocationLabel: "",
    rightLocation: "120",
    rightRealSolarTime: true,
    rightZiHourMode: "early",
    ziHourLabels: ["早子时", "晚子时"],
    surname: "",
    givenName: "",
    namingHint: "输入姓名后自动查询康熙笔画",
    namingReady: false,
    useNamingChart: true
  }, consultation.initialData),

  onLoad: function (options) {
    var mode = MODE_META[options.mode] ? options.mode : "daily";
    var now = todayParts();
    var chart = wx.getStorageSync("latestChartResult");
    this.setData({
      mode: mode,
      meta: MODE_META[mode],
      date: now.date,
      time: now.time,
      year: new Date().getFullYear(),
      hasChart: Boolean(chart)
    });
    wx.setNavigationBarTitle({ title: MODE_META[mode].title });
    if (mode === "consult") this.loadConsultationData();
  },

  onFieldInput: function (event) {
    var payload = {};
    payload[event.currentTarget.dataset.field] = event.detail.value;
    this.setData(payload, function () {
      if (event.currentTarget.dataset.field === "surname" || event.currentTarget.dataset.field === "givenName") {
        this.updateNamingHint();
      }
    }.bind(this));
  },

  updateNamingHint: function () {
    try {
      var surname = String(this.data.surname || "").trim();
      var given = String(this.data.givenName || "").trim();
      if (!surname || !given) {
        this.setData({ namingHint: "输入姓氏和名字后自动查询康熙笔画", namingReady: false });
        return;
      }
      var details = naming.lookupText(surname + given);
      this.setData({
        namingHint: details.map(function (item) { return item.character + "：" + item.stroke + "画"; }).join("　"),
        namingReady: true
      });
    } catch (error) {
      this.setData({ namingHint: error.message || "部分字符暂未收录", namingReady: false });
    }
  },

  onDateChange: function (event) { this.setData({ date: event.detail.value }); },
  onTimeChange: function (event) { this.setData({ time: event.detail.value }); },
  onLeftDateChange: function (event) { this.setData({ leftDate: event.detail.value }); },
  onLeftTimeChange: function (event) { this.setData({ leftTime: event.detail.value }); },
  onRightDateChange: function (event) { this.setData({ rightDate: event.detail.value }); },
  onRightTimeChange: function (event) { this.setData({ rightTime: event.detail.value }); },
  onCompatibilitySolarChange: function (event) {
    var payload = {};
    payload[event.currentTarget.dataset.field] = event.detail.value;
    this.setData(payload);
  },
  onCompatibilityZiChange: function (event) {
    var payload = {};
    payload[event.currentTarget.dataset.field] = Number(event.detail.value) === 1 ? "late" : "early";
    this.setData(payload);
  },
  onNamingChartChange: function (event) { this.setData({ useNamingChart: event.detail.value }); },

  goToChart: function () {
    wx.navigateBack({ delta: 1 });
  },

  runTool: function () {
    try {
      var mode = this.data.mode;
      var chart = wx.getStorageSync("latestChartResult");
      var result;
      if (mode === "daily") result = fortune.buildDaily(chart, this.data.date);
      if (mode === "wealth") result = fortune.buildYear(chart, this.data.year);
      if (mode === "question" || mode === "liuyao") {
        if (mode === "question" && !String(this.data.question).trim()) throw new Error("请填写所问事项");
        result = divination.buildByTime(this.data.date + " " + this.data.time, this.data.question);
      }
      if (mode === "compatibility") {
        result = compatibility.build({
          name: this.data.leftName, date: this.data.leftDate,
          time: this.data.leftTime, locationLabel: this.data.leftLocationLabel,
          location: this.data.leftLocation, realSolarTime: this.data.leftRealSolarTime,
          ziHourMode: this.data.leftZiHourMode
        }, {
          name: this.data.rightName, date: this.data.rightDate,
          time: this.data.rightTime, locationLabel: this.data.rightLocationLabel,
          location: this.data.rightLocation, realSolarTime: this.data.rightRealSolarTime,
          ziHourMode: this.data.rightZiHourMode
        });
        result.left.pillarList = pillarsForView(result.left.pillars);
        result.right.pillarList = pillarsForView(result.right.pillars);
      }
      if (mode === "naming") {
        result = naming.calculate(this.data.surname, this.data.givenName, this.data.useNamingChart ? chart : null);
      }
      if (!result) throw new Error("当前功能模式无效");
      this.setData({ result: result });
      wx.pageScrollTo({ selector: "#tool-result", duration: 260 });
    } catch (error) {
      wx.showModal({
        title: "生成失败",
        content: error && error.message ? error.message : "请检查输入内容",
        showCancel: false
      });
    }
  },

  onShareAppMessage: function () {
    return { title: this.data.meta.title, path: "/pages/tools/tools?mode=" + this.data.mode };
  }
}, consultation.methods));
