# base.apk Native 与运行时分析报告

## 样本与核验

主样本：`E:\WXWork\1688856420768484\Cache\File\2026-08\base.apk`

- SHA-256：`df0d5bfe1505886c3e258f3dc1bcdb4154742a49890310669326f290e5821f46`
- 文件大小：`190566267` 字节
- 包名：`yiqi.bazi`
- APK 内标准 DEX：`classes.dex`，大小 `25585276` 字节
- `classes.dex` SHA-256：`8f524a2fcc91f1562e2ef635379484331e776ae684d492baf0b77249d1fbc1cc`
- `class_defs_size`：`4`
- DEX 标准区结束后尾随数据：`25557848` 字节
- APK 内没有第二个普通 DEX 文件；业务载荷位于尾随区或运行时生成区的判断仍需结合壳代码验证。

独立核验结果：`F:\企业微信\20260816\算命\reports\final-apk-analysis.json`

独立核验日志：`F:\企业微信\20260816\算命\logs\final-apk-analysis.log`

## x86_64 壳库

分析文件：`F:\企业微信\20260816\算命\artifacts\container\libjiagu_x64.so`

- ELF64，机器类型 `EM_X86_64`（62）
- 大小：`902392` 字节
- SHA-256：`ea6c0efdf6f608347486a05aec77da45492748466100f8e89b21383f117071ec`
- 运行时从 `/data/data/yiqi.bazi/.jiagu/libjiagu_64.so` 导出的文件与该静态文件哈希完全一致。

分析报告：`F:\企业微信\20260816\算命\reports\native-x86_64-analysis.json`

关键动态符号和函数：

- `JNI_OnLoad`：`0xbdb0`
- `_Z9__arm_a_1P7_JavaVMP7_JNIEnvPvRi`：`0xcc70`
- `_Z9__arm_a_2PcmS_Rii`：`0xb4a0`
- `DynCryptor::__arm_c_0`：`0x8910`
- `__arm_c_0` 相关函数：`0x7f20`

直接引用证据：

- `RMUTGF_KEY` 在 `0xc252` 附近被装入参数寄存器，随后通过 JavaVM/JNIEnv 虚表偏移 `0x538` 调用，再进入 `0xc3f0`。
- `JIAGU_APP_NAME`、`JIAGU_SO_BASE_NAME`、`JIAGU_ENCRYPTED_DEX_NAME`、`JIAGU_HASH_FILE_NAME`、`libijmDataEncryption_enc.so` 和 `JIAGU_FILE_PATH` 在 `0xc58a` 至 `0xcab5` 区间被多次构造和传递。
- 动态导入包含 `mmap`、`fread`、`inflate`、`dlopen`、`inotify`、`mprotect`、`open`、`pread` 等，符合文件载荷读取、解压、动态库加载和运行时映射流程。
- `/proc/self/maps` 在多个代码位置被引用，说明壳会根据进程映射检查或定位运行时对象。

这些证据直接支持“`base.apk` 使用 Native 壳处理加密或动态加载载荷”。具体加密算法、密钥派生和业务 DEX 的最终落点仍未从当前 x86_64 壳库静态分析中完全还原。

## 运行时结果

当前可用 AVD：`Pixel_6`，Android 17，系统镜像为 x86_64，属性为 `x86_64,arm64-v8a`。这不是纯 ARM64 用户空间，ARM64 库由 Berberis 兼容层处理。

成功采集任务：

`F:\企业微信\20260816\算命\artifacts\runtime\20260817T045803Z-df0d5bfe1505\manifest.json`

该任务中：

- `libjiagu_64.so` 成功加载。
- root 导出成功，获得壳库、`base.vdex` 和 `base.odex`。
- 进程内存扫描成功导出一个 DEX：
  `F:\企业微信\20260816\算命\artifacts\runtime\20260817T045803Z-df0d5bfe1505\memory-scan\memory-000-76ec92600040.dex`
- 该 DEX 大小为 `25585276` 字节，`class_defs_size=4`，SHA-256 为 `8f524a2fcc91f1562e2ef635379484331e776ae684d492baf0b77249d1fbc1cc`，与 APK 中 `classes.dex` 完全一致。
- DEX 位置对应 `base.vdex` 映射，不是新增业务 DEX。

内存扫描清单：

`F:\企业微信\20260816\算命\artifacts\runtime\20260817T045803Z-df0d5bfe1505\memory-scan\memory-scan-index.json`

进程 maps：

`F:\企业微信\20260816\算命\artifacts\runtime\20260817T045803Z-df0d5bfe1505\proc\2753.latest.maps`

运行日志：

`F:\企业微信\20260816\算命\artifacts\runtime\20260817T045803Z-df0d5bfe1505\logcat.txt`

日志直接记录了以下事实：

- `libjiagu_64.so` 在 Berberis 下成功加载。
- 壳调用路径出现 `/data/data/yiqi.bazi/.jiagu/classes.dex!classes6.dex`、`classes2.dex` 和 `classes5.dex`。
- 日志栈出现 `yiqi.bazi.YiQiBaZiApplication.SDKInfo`、`yiqi.bazi.YiQiBaZiApplication.onCreate` 和 `com.stub.StubApp.onCreate`。
- `libjgdtc.so` 缺失。
- 部分 ARM64 native 库因程序对齐为 `4096` 而系统页大小为 `16384`，出现 `UnsatisfiedLinkError`。

上述日志直接证明运行时曾加载隐藏 DEX 和业务应用类，但当前采集没有得到这些 DEX 的独立字节文件。业务 DEX 的具体数量、完整哈希和源码内容暂未验证。

一次后续采集任务：

`F:\企业微信\20260816\算命\artifacts\runtime\20260817T050058Z-df0d5bfe1505\manifest.json`

该任务因 AVD 短暂处于 `device offline` 在安装阶段结束，未产生新的样本证据。

## 与 base1.apk 的关系

对照样本 `base1.apk` 的包名为 `com.example.mls.mdspaipan`，业务源码位于：

`F:\企业微信\20260816\算命\artifacts\base1-analysis\recovered\java\dex-00\sources\com\example\mls\mdspaipan\`

它与 `base.apk` 没有共同业务包名、共同服务域名或共同 Native 库名称。`base1.apk` 的源码只能作为独立对照样本，不能当作 `base.apk` 的业务源码。

## 结论分级

### 直接证据

- 两个 APK 的 SHA-256、大小、DEX 数量和 `class_defs_size` 已由 `F:\企业微信\20260816\算命\reports\final-apk-analysis.json` 独立核验。
- `base1.apk` 已恢复业务近似源码、资源、Manifest、入口组件、接口 URL 和数据库信息。
- `base.apk` 的 APK 内 DEX 和运行时导出的 DEX 都是 4-class 壳 DEX。
- `base.apk` 运行时确实加载了 `classes.dex!classes6.dex` 等隐藏 DEX，并执行到 `yiqi.bazi.YiQiBaZiApplication`。

### 基于证据的推断

- `base.apk` 的业务 DEX 可能在 Native 壳解密后以匿名内存、临时文件或特殊私有映射形式存在。
- `.oabugaij/.fsgkea` 与 `files/jgobfppppp (deleted)` 曾出现在进程 maps 中，可能是壳的加密载荷、索引或校验材料；这些文件的实际内容尚未导出，性质不能定论。

### 尚未验证

- 业务 DEX 的完整字节内容、数量、哈希和最终源码。
- `RMUTGF_KEY` 的具体派生算法。
- ARM64 原生环境下是否能稳定捕获业务 DEX。

## 下一步

优先级最高的是使用纯 ARM64 Android 环境或 ARM64 真机，在壳成功加载且不触发 16KB 页面对齐错误的条件下，按 `JNI_OnLoad`、`mmap`、`inflate`、`dlopen` 和 DEX 注册点进行早期内存采集。当前 x86_64 AVD 已能验证壳入口和业务启动时序，但还不足以完成 `base.apk` 业务源码恢复。
