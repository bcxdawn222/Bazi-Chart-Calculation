var STORAGE_KEY = "localPrayerRecords";
var api = require("../../core/api");

function readRecords() {
  var records = wx.getStorageSync(STORAGE_KEY);
  return Array.isArray(records) ? records.filter(function (item) {
    return item && (item.type === "prayer" || item.type === "wish") && item.id;
  }) : [];
}
function saveRecords(records) {
  var counts = { prayer: 0, wish: 0 };
  wx.setStorageSync(STORAGE_KEY, records.filter(function (item) {
    counts[item.type] += 1;
    return counts[item.type] <= 30;
  }));
}
function remoteStatus(status) { return status === "completed" ? "已完成" : "进行中"; }
function sameId(left, right) { return String(left) === String(right); }

function remoteToLocal(item, mode) {
  var payload = item.payload || {};
  return Object.assign({}, payload, {
    id: payload.id || item.id, remoteId: item.id, source: "remote",
    type: mode,
    status: remoteStatus(item.status), createdAt: payload.createdAt || item.created_at
  });
}

Page({
  data: {
    mode: "prayer", name: "", wish: "", note: "", records: [],
    syncState: "本地记录", creating: false, recordBusyId: "", fieldErrors: {}
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
    var loadId = (this.remoteLoadId || 0) + 1;
    var revision = this.recordRevision || 0;
    this.remoteLoadId = loadId;
    var loader = mode === "wish" ? api.listWishes : api.listPrayers;
    loader(function (response) {
      if (self.remoteLoadId !== loadId || self.data.mode !== mode
          || (self.recordRevision || 0) !== revision || self.data.creating || self.data.recordBusyId) return;
      if (!response.ok) {
        self.setData({ syncState: response.reason === "local-mode" ? "本地记录" : response.message });
        return;
      }
      var otherMode = readRecords().filter(function (item) { return item.type !== mode; });
      var pendingLocal = self.recordsForMode(mode).filter(function (item) { return !item.remoteId; });
      var remote = response.items.map(function (item) { return remoteToLocal(item, mode); });
      pendingLocal = pendingLocal.filter(function (item) {
        return !remote.some(function (saved) { return sameId(saved.id, item.id); });
      });
      saveRecords(pendingLocal.concat(remote).concat(otherMode));
      self.setData({ records: self.recordsForMode(mode), syncState: "已同步" });
    });
  },

  onInput: function (event) {
    var field = event.currentTarget.dataset.field;
    var payload = {};
    var nextErrors;
    payload[field] = event.detail.value;
    if (this.data.fieldErrors && this.data.fieldErrors[field]) {
      nextErrors = Object.assign({}, this.data.fieldErrors);
      delete nextErrors[field];
      payload.fieldErrors = nextErrors;
    }
    this.setData(payload);
  },

  createRecord: function () {
    var errors;
    if (this.data.creating || this.data.recordBusyId) return;
    var name = String(this.data.name || "").trim();
    var wish = String(this.data.wish || "").trim();
    errors = {};
    if (!name) errors.name = "请填写祈愿人姓名";
    if (!wish) errors.wish = "请填写心愿内容";
    if (errors.name || errors.wish) {
      this.setData({ fieldErrors: errors });
      return;
    }
    var record = {
      id: "local-" + Date.now(), name: name, wish: wish, note: String(this.data.note || "").trim(),
      type: this.data.mode, status: "进行中", createdAt: new Date().toLocaleString()
    };
    this.recordRevision = (this.recordRevision || 0) + 1;
    saveRecords([record].concat(readRecords()));
    this.setData({ records: this.recordsForMode(this.data.mode), name: "", wish: "", note: "", creating: true, fieldErrors: {} });
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
      self.recordRevision = (self.recordRevision || 0) + 1;
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
    if (this.data.recordBusyId || this.data.creating) return;
    var record = readRecords().find(function (item) { return sameId(item.id, id); });
    if (!record) return;
    var applyLocal = function () {
      self.recordRevision = (self.recordRevision || 0) + 1;
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
    if (this.data.recordBusyId || this.data.creating) return;
    wx.showModal({
      title: "删除记录",
      content: "删除后无法恢复，确认继续吗？",
      success: function (result) { if (result.confirm) self.performDelete(id); }
    });
  },

  performDelete: function (id) {
    var self = this;
    if (this.data.recordBusyId || this.data.creating) return;
    var record = readRecords().find(function (item) { return sameId(item.id, id); });
    if (!record) return;
    var applyLocal = function () {
      self.recordRevision = (self.recordRevision || 0) + 1;
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
    this.setData({ mode: mode, records: this.recordsForMode(mode), fieldErrors: {} });
    wx.setNavigationBarTitle({ title: mode === "wish" ? "心愿阁" : "祈福明灯" });
    this.loadRemote(mode);
  },

  onUnload: function () {
    this.remoteLoadId = (this.remoteLoadId || 0) + 1;
  }
});
