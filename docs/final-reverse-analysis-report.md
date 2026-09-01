# 两个 Android APK 逆向恢复总报告

## 样本核验

| 样本 | 大小 | SHA-256 | 包名 | DEX class_defs |
|---|---:|---|---|---:|
| `E:\WXWork\1688856420768484\Cache\File\2026-08\base.apk` | 190,566,267 | `df0d5bfe1505886c3e258f3dc1bcdb4154742a49890310669326f290e5821f46` | `yiqi.bazi` | APK 内壳 DEX 为 4 |
| `E:\WXWork\1688856420768484\Cache\File\2026-08\base1.apk` | 6,719,662 | `d9c9076cb1b0e202c0d67e5a551010d8bced2e7708593a6cbe8eee6799630e6f` | `com.example.mls.mdspaipan` | 4,486 |

原始样本未被修改。独立核验结果和日志位于 `F:\企业微信\20260816\算命\reports\final-apk-analysis.json` 与 `F:\企业微信\20260816\算命\logs\final-apk-analysis.log`。

## base1.apk

- Java 恢复目录：`F:\企业微信\20260816\算命\artifacts\base1-analysis\recovered\java\dex-00\sources\`
- 资源目录：`F:\企业微信\20260816\算命\artifacts\base1-analysis\recovered\resources\`
- 生成 Java 文件约 2,999 个；JADX 返回码为 1，但已保留主体源码。
- 主入口：`com.example.mls.mdspaipan.WelcomeActivity`，随后进入 `MainActivity`。
- 主要模块包括八字排盘、紫微、六爻、奇门、流年、测算、会员、收藏和文章。
- 静态网络接口、数据库和组件清单详见 `F:\企业微信\20260816\算命\docs\base1-analysis-report.md`。

## base.apk 运行时脱壳

### 导出证据

采集脚本 `F:\企业微信\20260816\算命\scripts\frida_hook_art_dex.py` 在 ART 符号 `ClassLinker::RegisterDexFileLocked` 注册点捕获到 8 个 DEX。捕获清单为 `F:\企业微信\20260816\算命\artifacts\runtime\20260817T-frida-art-dex-03\capture-index.json`。

- `dex-00`：4-class 壳 DEX，25,585,276 字节。
- `dex-01`：79 classes，主要为 `com.jg.ids` 辅助库。
- `dex-02`：4,068 classes，直接命中 1,527 个 `yiqi.bazi` 类。
- `dex-03`：4,831 classes，当前归为第三方/辅助代码候选。
- `dex-04`：6,458 classes，当前归为第三方/辅助代码候选。
- `dex-05`：7,182 classes，直接命中 1,196 个 `yiqi.bazi` 类。
- `dex-06`：5,376 classes，当前归为第三方/辅助代码候选。
- `dex-07`：6,467 classes，当前归为第三方/辅助代码候选。

输入副本位于 `F:\企业微信\20260816\算命\artifacts\runtime\20260817T-frida-art-dex-03-input\`，未覆盖旧采集目录。

### 源码与资源

- 恢复目录：`F:\企业微信\20260816\算命\artifacts\base-analysis-recovered\`
- Java 文件总数：15,026 个。
- 业务源码目录：
  - `F:\企业微信\20260816\算命\artifacts\base-analysis-recovered\java\dex-02\sources\yiqi\bazi\`
  - `F:\企业微信\20260816\算命\artifacts\base-analysis-recovered\java\dex-05\sources\yiqibazi\`
- 主要入口源码：
  - `F:\企业微信\20260816\算命\artifacts\base-analysis-recovered\java\dex-02\sources\yiqi\bazi\Launch.java`
  - `F:\企业微信\20260816\算命\artifacts\base-analysis-recovered\java\dex-02\sources\yiqi\bazi\YiQiBaZiApplication.java`
- 解码 Manifest：`F:\企业微信\20260816\算命\artifacts\base-analysis-recovered\resources\AndroidManifest.xml`
- Manifest 入口为 `yiqi.bazi.Launch`，Application 为 `com.stub.StubApp`；解码得到 426 个 Activity、55 个 Service、20 个 Provider 和 19 个 Receiver。

### 接口与 native 关联

- 业务 Java 中存在 `yiqibazi.com`、`soft.yiqibazi.com`、`wap.yiqibazi.com`、`m.yiqibazi.com`、`pay.yiqibazi.com` 等服务地址；完整静态 URL 清单位于 `F:\企业微信\20260816\算命\docs\base-runtime-source-analysis-report.md`。
- `yiqibazi.com.mylibrary.webservice.WebServiceData` 使用 `UrlIntrface.GetKey()`、`GetMasterPassword()` 和 AES 加密构造 SOAP 参数。
- `WebServiceUtil` 使用 `UrlIntrface.GetDecryptionPassword()` 解密响应。
- native 符号和 URL 证据位于 `F:\企业微信\20260816\算命\artifacts\base-analysis-recovered\native-evidence.txt`，包含 `GetKey`、`GetKey1`、`GetMasterPassword`、`GetDecryptionPassword`、`GetRsaPrivate` 以及 `libyiqilibrary.so` 关联字符串。
- 这部分是静态字符串和调用关系证据，不代表本轮主动访问了这些服务。

## 工具与返回码

- JADX：`F:\企业微信\20260816\算命\.tools\reverse\jadx-1.5.1\bin\jadx.bat`；8 个 DEX 均生成了 Java，4 个 DEX 返回码为 1 并保留部分源码。
- apktool：`F:\企业微信\20260816\算命\.tools\reverse\apktool-2.10.0.jar`；base.apk 资源解码返回码为 0。
- Frida server：`F:\企业微信\20260816\算命\.tools\reverse\frida\frida-server-17.17.0-android-x86_64`。
- 运行环境：`emulator-5554`，Android 17，用户空间 `x86_64`，ARM64 库通过兼容层加载。
- 源码恢复状态：`recovered_partial`，详细返回码、命令和日志位于 `F:\企业微信\20260816\算命\artifacts\base-analysis-recovered\source-recovery.json`。

## 可复现实验命令

```powershell
py -3.13 F:\企业微信\20260816\算命\scripts\frida_hook_art_dex.py --package yiqi.bazi --host 127.0.0.1:27042 --seconds 18 --output F:\企业微信\20260816\算命\artifacts\runtime\20260817T-frida-art-dex-03
py -3.13 F:\企业微信\20260816\算命\scripts\recover_sources.py --input F:\企业微信\20260816\算命\artifacts\runtime\20260817T-frida-art-dex-03-input --output F:\企业微信\20260816\算命\artifacts\base-analysis-recovered --tools F:\企业微信\20260816\算命\.tools\reverse
py -3.13 F:\企业微信\20260816\算命\scripts\report_base_runtime_sources.py --recovered F:\企业微信\20260816\算命\artifacts\base-analysis-recovered --capture-index F:\企业微信\20260816\算命\artifacts\runtime\20260817T-frida-art-dex-03\capture-index.json --manifest F:\企业微信\20260816\算命\artifacts\runtime\20260817T051637Z-df0d5bfe1505\manifest.json --json F:\企业微信\20260816\算命\reports\base-runtime-source-analysis.json --markdown F:\企业微信\20260816\算命\docs\base-runtime-source-analysis-report.md
```

首次运行时若设备处于离线状态，运行时采集会在安装阶段结束；该失败任务和原因记录在 `F:\企业微信\20260816\算命\artifacts\runtime\20260817T050058Z-df0d5bfe1505\manifest.json`。成功任务使用的是 `F:\企业微信\20260816\算命\artifacts\runtime\20260817T051637Z-df0d5bfe1505\manifest.json`，本次 DEX 注册点捕获结果则位于 `F:\企业微信\20260816\算命\artifacts\runtime\20260817T-frida-art-dex-03\capture-index.json`。

## 当前结论

`base1.apk` 已完成静态业务源码恢复；`base.apk` 已完成运行时脱壳并取得包含 `yiqi.bazi` 的业务 DEX 与可检索 Java 源码。当前产物属于 JADX 恢复源码，少数类存在反编译错误，尚未恢复原始 Gradle 工程、注释、混淆前命名和完整 native 算法实现。
