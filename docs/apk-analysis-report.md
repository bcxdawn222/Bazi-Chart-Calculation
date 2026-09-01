# 两个 APK 静态分析报告

## 分析对象

- `base.apk`：`E:/WXWork/1688856420768484/Cache/File/2026-08/base.apk`
- `base1.apk`：`E:/WXWork/1688856420768484/Cache/File/2026-08/base1.apk`

本报告只记录静态分析结果。没有连接 Android 设备，也没有执行应用、网络抓包、Frida hook 或运行时脱壳，因此涉及真实运行行为的结论仍需动态验证。

## 摘要结论

两个 APK 不是同一应用的不同构建产物：包名、版本、签名证书、DEX 格式、代码规模和 native 库布局均不同。

`base.apk` 对应“易奇文化”应用，包名为 `yiqi.bazi`，版本为 `4.9.6`。其 `classes.dex` 只有 4 个 class，但文件尾部多出约 24.4 MiB 未被 DEX 头部数据区解释的数据，同时存在 `assets/.jgapp`、`com.stub.StubApp`、`DexFile`、`DtcLoader` 和多组 native loader 痕迹。这些特征与加固/壳加载方式一致，业务代码当前不能通过普通 DEX 静态读取完整确认。

`base1.apk` 对应“马国峻八字排盘宝”，包名为 `com.example.mls.mdspaipan`，版本为 `2026.5.27`。它包含完整的单个 DEX，约 4,486 个 class、23,338 个 method，无 `lib/*.so`。静态字符串中发现明文 HTTP 地址、硬编码 IP 以及文件上传/下载接口，建议优先做网络行为和服务端接口验证。

## 文件与签名

| 项目 | `base.apk` | `base1.apk` |
|---|---:|---:|
| 文件大小 | 190,566,267 bytes | 6,719,662 bytes |
| SHA-256 | `df0d5bfe1505886c3e258f3dc1bcdb4154742a49890310669326f290e5821f46` | `d9c9076cb1b0e202c0d67e5a551010d8bced2e7708593a6cbe8eee6799630e6f` |
| 包名 | `yiqi.bazi` | `com.example.mls.mdspaipan` |
| 版本 | `4.9.6` / versionCode `228` | `2026.5.27` / versionCode `121` |
| 最低 SDK | 24 | 26 |
| target SDK | 30 | 30 |
| 签名摘要 | `60d7bb58016f6678a712e7d3acd0a965d5607f1fc7ef22cf95a53676e8e98790` | `fd984d3f2db3b4f4432ec7c83b2c7812b87b05a95bd3e1efe1348c7881ce6e51` |
| 签名方案 | v2、v3 | v2 |

签名 DN 分别为 `CN=yiqibazi, OU=yiqibazi, O=yiqibazi, C=CN` 和 `CN=guojun ma, OU=guojun ma, C=086`，证书指纹不同，因此不能按同一发布者或同一软件的升级包处理。

## `base.apk` 分析

### 应用身份与功能范围

- 标签：`易奇文化`
- 启动 Activity：`yiqi.bazi.Launch`
- 组件规模很大，包含八字排盘、姓名、婚姻、运势、黄历、祈福、商城、咨询、直播、消息和支付等模块。
- 集成融云 IM/RTC、友盟推送、华为/小米/魅族/OPPO/VIVO/Honor 推送、支付宝、微信、新浪微博、Mob、移动认证等 SDK。

### 权限风险面

静态 Manifest 中出现以下敏感能力：

- `SYSTEM_ALERT_WINDOW`
- `MANAGE_EXTERNAL_STORAGE`
- 相机、录音、蓝牙、网络和 Wi-Fi 状态
- 电话状态、电话号码、`GET_TASKS`
- `WRITE_SETTINGS`、设置壁纸
- `REQUEST_INSTALL_PACKAGES`
- `QUERY_ALL_PACKAGES`
- 前台服务和多厂商推送权限

这些权限说明应用的可访问面较宽，但仅凭 Manifest 不能证明每一项都会在运行时使用。`READ_PRIVILEGED_PHONE_STATE` 即使写入普通第三方 APK，也不代表应用实际获得系统特权。

### 加固/壳特征

`classes.dex` 结构如下：

- DEX 035
- 4 个 class
- 375 个 method
- 682 个 string
- DEX 头部声明的数据区：17,756 bytes，起始偏移 `0x25c8`
- 文件实际长度：25,585,276 bytes
- 数据区之后尾随数据：25,557,848 bytes
- 尾随数据熵：约 6.837/8
- 尾随区域扫描到 ZIP、ELF、PNG、GZIP 魔数，但这些命中位于高熵数据内部，暂时不能据此确定每个嵌入对象的边界

可见的壳入口或加载相关类/字符串包括：

- `com.stub.StubApp`
- `com.tianyu.util.DtcLoader`
- `dalvik.system.DexFile`
- `loadLibrary`
- `assets/.jgapp`

综合这些证据，`base.apk` 高度疑似把业务 DEX 或配置放在加固数据中，由 Java/native loader 在启动时释放或加载。是否为某个具体厂商加固方案，需要进一步做运行时内存 DEX dump 或 native 入口分析后再确认。

### native 与密钥相关接口

`lib/arm64-v8a/libyiqilibrary.so` 和 `lib/armeabi-v7a/libyiqilibrary.so` 暴露了以下 JNI 方法名：

- `GetDecryptionPassword`
- `GetMasterPassword`
- `GetKey`、`GetKey1`
- `GetRsaPrivate`
- `GetRsaAllpayPublic`
- `GetWSDLUrl1/2/3`
- `GetUrl1/2`、`GetCallUrl1/2`

同一个库内还能看到多个 `soft.yiqibazi.com`、`wap.yiqibazi.com` 和 `yiqijixiang.com` 的明文 URL。方法名显示应用把服务地址、加密密码或支付相关材料放在 native 层，但当前尚未验证这些方法的返回值是否为真实密钥，也尚未判断 RSA 私钥是否为生产密钥。

### 网络与数据安全观察

静态字符串包含以下明文 HTTP 地址：

- `http://soft.yiqibazi.com/AndroidServiceEncrypt.asmx`
- `http://soft.yiqibazi.com/WebService.asmx`
- `http://wap.yiqibazi.com/androidservicev2.asmx/`
- `http://www.yiqijixiang.com/Content/Images`

若这些地址在实际业务路径中传输账号、订单、手机号或加密材料，则存在明文传输和中间人篡改风险；需要通过运行时请求确认是否有 HTTPS 迁移、额外签名或仅用于图片/兼容接口。

## `base1.apk` 分析

### 应用身份与代码结构

- 标签：`马国峻八字排盘宝`
- 启动 Activity：`com.example.mls.mdspaipan.WelcomeActivity`
- 主界面 Activity：`com.example.mls.mdspaipan.MainActivity`
- DEX 038
- 4,486 个 class
- 23,338 个 method
- 33,964 个 string
- 无 `lib/arm64-v8a`、`lib/armeabi-v7a` 或其他 native 库

业务类名基本可见，模块包括八字、七政、奇门、六壬、紫微、流年、罗盘、姓名、文章、用户、会员、悬赏和收藏等。与 `base.apk` 相比，它更适合直接使用 JADX/apktool 做 Java 层控制流和接口调用分析。

### 权限与 Manifest 观察

Manifest 中出现：

- `MANAGE_EXTERNAL_STORAGE`
- `WRITE_EXTERNAL_STORAGE`、`READ_EXTERNAL_STORAGE`
- `REQUEST_INSTALL_PACKAGES`
- `INTERNET`
- `ACCESS_WIFI_STATE`、`ACCESS_NETWORK_STATE`
- 非标准拼写的 `android.permission.WREAD_EXTERNAL_STORAGE`

`REQUEST_INSTALL_PACKAGES` 是需要重点核查的权限。静态字符串里出现下载文件相关路径，但当前报告尚未证明应用一定会自动安装下载内容，需要继续追踪 `PackageInstaller`、`Intent.ACTION_VIEW`、APK MIME 类型和下载完成回调。

### 明文网络地址

DEX 字符串中发现：

- `http://139.129.166.205`
- `http://47.104.12.215/collection/DownloadFile`
- `http://47.104.12.215/collection/QueryFileList`
- `http://47.104.12.215/collection/UploadFileSingle`
- `http://www.madashi.net`
- `http://www.madashi.net/mds_paipan/privacy/privacy_mdspp_2025.html`
- `/mds_paipan/api`

其中 `UploadFileSingle`、`DownloadFile` 和 `QueryFileList` 直接表明存在文件集合的上传、下载和查询接口命名。因为使用的是明文 HTTP，建议动态测试请求参数、鉴权字段、文件类型限制、服务端目录映射和错误回显。

### 支付与第三方 SDK

应用包含支付宝和微信相关组件/字符串，支付宝域名和 SDK 测试域名较多。这些大部分可以由支付 SDK 自身带入，不能单独视为异常；应把重点放在应用自有调用点是否把订单金额、用户标识或文件操作参数拼接到外部请求中。

## 对比判断

| 维度 | `base.apk` | `base1.apk` |
|---|---|---|
| 代码可见性 | 业务代码被壳/尾随数据隐藏的可能性高 | Java/Dex 代码基本直接可分析 |
| native | 38 个，双 ABI | 无 |
| 网络 | `yiqibazi.com` 相关接口，存在 HTTP | 明文 IP、文件上传下载接口、`madashi.net` |
| 权限 | 很宽，包含悬浮窗、录音、电话、安装包等 | 较少，但包含全盘存储和安装包权限 |
| 主要分析风险 | 需要运行时脱壳与 native 分析 | 需要追踪 HTTP、文件下载和安装流程 |
| 当前恶意性判断 | 静态证据不足以定性恶意；加固和密钥接口值得重点审查 | 静态证据不足以定性恶意；明文文件接口和安装包能力属于高优先级核查项 |

## 建议的下一步

1. 对 `base1.apk` 使用 JADX/apktool，搜索 `139.129.166.205`、`47.104.12.215`、`UploadFileSingle`、`DownloadFile`、`REQUEST_INSTALL_PACKAGES` 和 `PackageInstaller` 的调用链。
2. 对 `base.apk` 在隔离 Android 模拟器中观察 `yiqi.bazi.Launch` 启动过程，重点记录新生成的 DEX、`DexClassLoader`、`InMemoryDexClassLoader`、`System.loadLibrary` 和 `/data/data/yiqi.bazi` 下的释放文件。
3. 反汇编 `libyiqilibrary.so`，检查上述 JNI 方法的返回值来源、字符串解密逻辑、RSA 私钥是否硬编码，以及是否存在服务端证书校验。
4. 对两个 APK 做动态网络抓包，确认明文 HTTP 是否真实发出，以及是否存在证书固定、请求签名、设备标识和文件上传行为。

## 生成的分析产物

- 基线 JSON：`F:/企业微信/20260816/算命/reports/apk-analysis.json`
- Manifest/签名 JSON：`F:/企业微信/20260816/算命/reports/deep-apk-analysis.json`
- 基线日志：`F:/企业微信/20260816/算命/logs/apk-analysis.log`
- Manifest/签名日志：`F:/企业微信/20260816/算命/logs/deep-apk-analysis.log`
- 可重复执行脚本：`F:/企业微信/20260816/算命/scripts/analyze_apks.py`
- 组件与签名脚本：`F:/企业微信/20260816/算命/scripts/deep_apk_report.py`
