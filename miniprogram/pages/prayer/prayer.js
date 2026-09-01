var STORAGE_KEY = "localPrayerRecords";
var api = require("../../core/api");

function readRecords() { return wx.getStorageSync(STORAGE_KEY) || []; }
function saveRecords(records) { wx.setStorageSync(STORAGE_KEY, records.slice(0, 30)); }
function remoteStatus(status) { return status === "completed" ? "已完成" : "进行中"; }
function sameId(left, right) { return String(left) === String(right); }

function remoteToLocal(item) {
  var payload = item.payload || {};
  return Object.assign({}, payload, {
    id: payload.id || item.id, remoteId: item.id, source: "remote",
    type: payload.type === "wish" ? "wish" : "prayer",
    status: remoteStatus(item.status), createdAt: payload.createdAt || item.created_at
  });
}

Page({
  data: {
    mode: "prayer", name: "", wish: "", note: "", records: [],
    syncState: "本地记录", creating: false, recordBusyId: ""
  },

  onLoad: function (options) {
    var mode = options.mode === "wish" ? "wish" : "prayer";
    this.setData({ mode: mode, records: this.recordsForMode(mode) });
    wx.setNavigationBarTitle({ title: mode === "wish" ? "心愿阁" : "祈福明灯" });
  },

  onShow: function () {
    var mode = this.data.mode;
    this.setData({ records: this.recordsForMode(mode) });
    this.loadRemote(mode);
  },

  recordsForMode: function (mode) {
    return readRecords().filter(function (item) { return item.type === mode; });
  },

  loadRemote: function (mode) {
    var self = this;
    var loader = mode === "wish" ? api.listWishes : api.listPrayers;
    loader(function (response) {
      if (!response.ok) {
        self.setData({ syncState: response.reason === "local-mode" ? "本地记录" : response.message });
        return;
      }
      var otherMode = readRecords().filter(function (item) { return item.type !== mode; });
      var pendingLocal = self.recordsForMode(mode).filter(function (item) { return !item.remoteId; });
      saveRecords(otherMode.concat(response.items.map(remoteToLocal)).concat(pendingLocal));
      self.setData({ records: self.recordsForMode(mode), syncState: "已同步" });
    });
  },

  onInput: function (event) {
    var payload = {};
    payload[event.currentTarget.dataset.field] = event.detail.value;
    this.setData(payload);
  },

  createRecord: function () {
    if (this.data.creating) return;
    var name = String(this.data.name || "").trim();
    var wish = String(this.data.wish || "").trim();
    if (!name) { wx.showModal({ title: "请补充信息", content: "请填写祈愿人姓名", showCancel: false }); return; }
    if (!wish) { wx.showModal({ title: "请补充信息", content: "请填写心愿内容", showCancel: false }); return; }
    var record = {
      id: "local-" + Date.now(), name: name, wish: wish, note: String(this.data.note || "").trim(),
      type: this.data.mode, status: "进行中", createdAt: new Date().toLocaleString()
    };
    saveRecords([record].concat(readRecords()));
    this.setData({ records: this.recordsForMode(this.data.mode), name: "", wish: "", note: "", creating: true });
    this.syncCreated(record);
  },

  syncCreated: function (record) {
    var self = this;
    var sync = record.type === "wish" ? api.syncWish : api.syncPrayer;
    sync(record, function (response) {
      if (!response.synced) {
        self.setData({
          creating: false,
          syncState: response.reason === "local-mode" ? "本地记录" : response.response.message
        });
        wx.showToast({ title: "已保存到本机", icon: "none" });
        return;
      }
      var item = response.response.data.item;
      saveRecords(readRecords().map(function (current) {
        return sameId(current.id, record.id) ? Object.assign({}, current, { remoteId: item.id, source: "remote" }) : current;
      }));
      self.setData({ records: self.recordsForMode(self.data.mode), syncState: "已同步", creating: false });
      wx.showToast({ title: "已同步", icon: "success" });
    });
  },

  completeRecord: function (event) {
    this.changeRecordStatus(event.currentTarget.dataset.id, "已完成", "completed");
  },

  changeRecordStatus: function (id, localStatus, remoteStatusValue) {
    var self = this;
    if (this.data.recordBusyId) return;
    var record = readRecords().find(function (item) { return sameId(item.id, id); });
    if (!record) return;
    var applyLocal = function () {
      saveRecords(readRecords().map(function (item) {
        return sameId(item.id, id) ? Object.assign({}, item, { status: localStatus }) : item;
      }));
      self.setData({ records: self.recordsForMode(self.data.mode), recordBusyId: "" });
    };
    if (!record.remoteId) { applyLocal(); return; }
    this.setData({ recordBusyId: String(id) });
    var update = record.type === "wish" ? api.updateWish : api.updatePrayer;
    update(record.remoteId, remoteStatusValue, function (response) {
      if (!response.ok) {
        self.setData({ recordBusyId: "" });
        wx.showToast({ title: response.message, icon: "none" });
        return;
      }
      applyLocal();
      self.setData({ syncState: "已同步" });
    });
  },

  deleteRecord: function (event) {
    var id = event.currentTarget.dataset.id;
    var self = this;
    if (this.data.recordBusyId) return;
    wx.showModal({
      title: "删除记录",
      content: "删除后无法恢复，确认继续吗？",
      success: function (result) { if (result.confirm) self.performDelete(id); }
    });
  },

  performDelete: function (id) {
    var self = this;
    var record = readRecords().find(function (item) { return sameId(item.id, id); });
    if (!record) return;
    var applyLocal = function () {
      saveRecords(readRecords().filter(function (item) { return !sameId(item.id, id); }));
      self.setData({ records: self.recordsForMode(self.data.mode), recordBusyId: "" });
    };
    if (!record.remoteId) { applyLocal(); return; }
    this.setData({ recordBusyId: String(id) });
    var remove = record.type === "wish" ? api.deleteWish : api.deletePrayer;
    remove(record.remoteId, function (response) {
      if (!response.ok) {
        self.setData({ recordBusyId: "" });
        wx.showToast({ title: response.message, icon: "none" });
        return;
      }
      applyLocal();
      self.setData({ syncState: "已同步" });
    });
  },

  switchMode: function (event) {
    var mode = event.currentTarget.dataset.mode;
    this.setData({ mode: mode, records: this.recordsForMode(mode) });
    wx.setNavigationBarTitle({ title: mode === "wish" ? "心愿阁" : "祈福明灯" });
    this.loadRemote(mode);
  }
});
