# Android 运行时脱壳报告

## 样本

- 输入：`E:/WXWork/1688856420768484/Cache/File/2026-08/base.apk`
- SHA-256：`df0d5bfe1505886c3e258f3dc1bcdb4154742a49890310669326f290e5821f46`
- 包名：`yiqi.bazi`
- AVD：`Pixel_6`，Android 17，`x86_64,arm64-v8a`
- 原始 APK 在任务期间未写入。

## 运行时导出

主任务清单：`F:/企业微信/20260816/算命/artifacts/runtime/20260816T170727Z-df0d5bfe1505/manifest.json`

已导出壳 native 库、`base.vdex`、`base.odex`、`libmsaoaidsec.so`、进程 maps 和完整 logcat。内存扫描得到的标准 DEX 均为壳内容：4 个 class 的重复映射，以及一个 1 class、284 字节的小型辅助 DEX；没有得到包含业务 class 的独立 DEX。

## 源码和资源恢复

恢复清单：`F:/企业微信/20260816/算命/artifacts/recovered/20260816T170727Z-df0d5bfe1505/source-recovery.json`

- JADX 1.5.1：10 个运行时 DEX 输入均返回码 0。
- apktool 2.10.0：资源解码返回码 0。
- Java 目录：`F:/企业微信/20260816/算命/artifacts/recovered/20260816T170727Z-df0d5bfe1505/java/`
- 资源目录：`F:/企业微信/20260816/算命/artifacts/recovered/20260816T170727Z-df0d5bfe1505/resources/`
- native 证据：`F:/企业微信/20260816/算命/artifacts/recovered/20260816T170727Z-df0d5bfe1505/native-evidence.txt`

当前 Java 产物主要是壳入口 `com.stub.StubApp`、`com.tianyu.util.*` 和辅助类，属于近似源码，不是业务工程源码。

## 关键证据与阻塞

- logcat 出现 `caller=/data/data/yiqi.bazi/.jiagu/classes.dex!classes6.dex`、`classes2.dex`，说明壳运行时使用了多 DEX 逻辑。
- 当前 AVD 上 ARM native 通过 Berberis 兼容层运行；`libjgdtc.so` 缺失，部分 native 库因 4096/16384 页面对齐差异加载失败，主进程随后出现 `UnsatisfiedLinkError` 或退出。
- Frida Java bridge 在该进程中不可用，ART 注册符号也未出现在 Frida 可见导出表。一次基址偏移试验导致目标进程 `SIGSEGV`，该路径已移除。
- `libyiqilibrary.so` 的 JNI 字符串包含 `GetDecryptionPassword`、`GetMasterPassword`、`GetRsaPrivate`、`GetKey` 及多个 WebService URL，静态证据位于 native 证据文件。

本轮已完成工具准备、原样本启动、root 文件导出、maps/logcat 采集、壳 DEX 恢复、资源解码和 native 证据整理。业务 DEX/业务源码仍受当前 x86_64 AVD 的 native 兼容性和进程生命周期限制，已标记为可复核阻塞。

## 后续采集补充（2026-08-17）

新增成功任务：

`F:/企业微信/20260816/算命/artifacts/runtime/20260817T045803Z-df0d5bfe1505/manifest.json`

- AVD 启动参数加入 `-memory 4096 -no-window -no-audio -gpu swiftshader_indirect`。
- 采集脚本改为启动后轮询 PID，并在进程存活窗口内重复读取 maps。
- root 导出成功获得 `base.vdex`、`base.odex` 和壳 Native 库。
- `/proc/<pid>/mem` 扫描导出一个完整 DEX，大小 `25585276` 字节，`class_defs_size=4`，SHA-256 为 `8f524a2fcc91f1562e2ef635379484331e776ae684d492baf0b77249d1fbc1cc`。
- 该 DEX 与 APK 内 `classes.dex` 哈希一致，映射来源是 `base.vdex`，因此仍属于壳 DEX，不是业务 DEX。
- logcat 明确出现 `classes.dex!classes6.dex`、`classes2.dex`、`classes5.dex` 和 `yiqi.bazi.YiQiBaZiApplication`，证明业务加载链已经进入 Java 层。

新增静态 Native 分析：

`F:/企业微信/20260816/算命/reports/native-x86_64-analysis.json`

该报告确认 x86_64 壳库中存在 `RMUTGF_KEY`、`JIAGU_ENCRYPTED_DEX_NAME`、`JIAGU_HASH_FILE_NAME`、`libijmDataEncryption_enc.so`、`mmap`、`inflate` 和 `dlopen` 的引用链。

新增中文汇总：

`F:/企业微信/20260816/算命/docs/base-apk-native-analysis-report.md`

当前结论保持不变：`base1.apk` 已恢复业务近似源码；`base.apk` 已确认壳入口、Native 解密相关调用和业务类加载时序，但业务 DEX 字节与业务源码仍未导出。
