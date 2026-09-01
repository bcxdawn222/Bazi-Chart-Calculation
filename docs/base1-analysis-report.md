# base1.apk 静态恢复报告

## 样本核验

| 样本 | 大小 | SHA-256 | DEX class_defs |
|---|---:|---|---:|
| `E:\WXWork\1688856420768484\Cache\File\2026-08\base.apk` | 190,566,267 | `df0d5bfe1505886c3e258f3dc1bcdb4154742a49890310669326f290e5821f46` | 4 |
| `E:\WXWork\1688856420768484\Cache\File\2026-08\base1.apk` | 6,719,662 | `d9c9076cb1b0e202c0d67e5a551010d8bced2e7708593a6cbe8eee6799630e6f` | 4,486 |

核验脚本为 `F:\企业微信\20260816\算命\scripts\analyze_apks.py`，结果保存于 `F:\企业微信\20260816\算命\artifacts\base1-analysis\static-analysis.json`。原始 APK 未被写入。

## base1.apk 身份

- 包名：`com.example.mls.mdspaipan`
- 应用名：`马国峻八字排盘宝`
- 主入口：`com.example.mls.mdspaipan.WelcomeActivity`
- 主流程：`WelcomeActivity` 检查 `app_set/bz_pravcy`，随后进入 `MainActivity`。
- Manifest 组件：155 个 Activity、3 个 Service、2 个 Provider。
- 业务包源码：`com.example.mls.mdspaipan` 下 163 个 Java 文件。
- 主要功能模块：八字排盘、紫微、六爻、奇门、九宫、流年、测算、会员、收藏数据库、文章和悬赏。

Manifest 解码结果位于 `F:\企业微信\20260816\算命\artifacts\base1-analysis\recovered\resources\AndroidManifest.xml`。

## 源码与资源

恢复入口为 `F:\企业微信\20260816\算命\scripts\recover_sources.py`。

- Java 目录：`F:\企业微信\20260816\算命\artifacts\base1-analysis\recovered\java\dex-00\sources\`
- 资源目录：`F:\企业微信\20260816\算命\artifacts\base1-analysis\recovered\resources\`
- 源码恢复清单：`F:\企业微信\20260816\算命\artifacts\base1-analysis\recovered\source-recovery.json`
- JADX 日志：`F:\企业微信\20260816\算命\artifacts\base1-analysis\recovered\logs\jadx-00.log`
- apktool 日志：`F:\企业微信\20260816\算命\artifacts\base1-analysis\recovered\logs\apktool.log`

JADX 1.5.1 在 Java 17.0.14 下生成约 2,999 个 Java 文件，并报告 7 个反编译错误，返回码为 `1`。这些错误没有阻止已生成源码和资源继续保存，清单状态为 `recovered_partial`。apktool 2.10.0 返回码为 `0`。`base1.apk` 不包含 `lib/*.so`，因此 native 文件清单为空。

## 网络与业务接口

网络请求集中在 `F:\企业微信\20260816\算命\artifacts\base1-analysis\recovered\java\dex-00\sources\b\b\a\a\a2\j0.java` 及其调用类中，使用 `HttpURLConnection`，支持 POST 参数、Cookie 会话和服务器切换。

已确认的服务地址和路径包括：

- `http://www.madashi.net`
- `http://139.129.166.205`
- `http://47.104.12.215/collection/UploadFileSingle`
- `http://47.104.12.215/collection/QueryFileList`
- `http://47.104.12.215/collection/DownloadFile`
- `/cesuan/QueryBasicCs`
- `/cesuan/QuerySingleCsRes`
- `/mds_paipan/api/query_version_query.php`
- `/mdss/collection/SubmitCollection`
- `/mdss/collection/QueryACollection`
- `/bzpp/user/ValidateCodeDo`
- `/bzpp/user/ValidateCodeImg`
- `/bzpp/user/ValidateMbb`

这些地址是 APK 内的静态字符串和调用参数，不代表本次执行访问过这些服务。

## 本地数据

`F:\企业微信\20260816\算命\artifacts\base1-analysis\recovered\java\dex-00\sources\b\b\a\a\a2\h0.java` 和 `F:\企业微信\20260816\算命\artifacts\base1-analysis\recovered\java\dex-00\sources\b\b\a\a\a2\e0.java` 显示，应用在外部存储根目录下使用以下目录和数据库：

- `/mds_paipan/dbs/mds_user.sqlite`
- `/mds_paipan/dbs/mds_pp_history.sqlite`
- `/mds_paipan/dbs/mds_user_e1.sqlite`
- `/mds_paipan/arts_bz/`
- `/mds_paipan/temp/`
- `/mds_paipan/dbs_bak/2025.5.19/`

`e0.java` 明确创建 `pp_history` 表，字段包括 `h_id`、`h_name`、`h_location`、`h_bz`、`h_param` 和 `h_time`。

## 与 base.apk 的关系

当前证据显示两者是不同应用或不同产品线的样本：

- `base.apk` 的包名为 `yiqi.bazi`，应用名为“易奇文化”，壳 native 证据包含 `libyiqilibrary.so`、`yiqibazi` JNI 名称和 `yiqibazi.com` 服务地址。
- `base1.apk` 的包名为 `com.example.mls.mdspaipan`，应用名为“马国峻八字排盘宝”，业务服务地址集中在 `madashi.net` 和 `139.129.166.205`。
- 两者没有发现共同的业务包名、共同的服务域名或共同的 native 库名称。

因此，当前不把 `base1.apk` 的业务源码作为 `base.apk` 的源码映射。`base.apk` 的业务 DEX 仍需单独通过 ARM64 运行环境或 native 解密链继续分析。

## 工具与验证

- JADX：1.5.1
- apktool：2.10.0
- Java：17.0.14
- Android build-tools：37.0.0，aapt 版本 `0.2-15087165`
- 脚本语法检查：`py -3.13 -m py_compile scripts\recover_sources.py scripts\analyze_apks.py scripts\deep_apk_report.py`，返回码 `0`
- base1 APK 签名验证：Android SDK `apksigner.bat` 返回 `Verifies`，使用 v2 签名方案
- 运行时和静态日志目录：`F:\企业微信\20260816\算命\logs\`

## 结论

`base1.apk` 已获得可检索的业务近似源码、资源、Manifest、入口组件、网络接口和本地数据库结构。JADX 的 7 个错误只影响少数类的反编译完整性，主业务包和主要 Activity 已生成。`base.apk` 仍是独立的加固样本，当前主线应转向 ARM64 真机/环境运行时导出或 `libyiqilibrary.so` 的 native 解密链分析。
