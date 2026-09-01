# Tasks: android-apk-runtime-unpack

> deps omitted = sequential, follows the previous item

- [x] 1. 环境与工具检查
  - [x] 1.1 检查 `adb`、`Pixel_6` AVD、Java 和 Python 运行时
  - [x] 1.2 在隔离目录准备 JADX、apktool、frida-tools；记录版本和安装日志
- [x] 2. 运行时任务入口
  - [x] 2.1 实现 AVD 启停、ADB 等待、样本哈希和输出目录管理
  - [x] 2.2 实现安装、启动、logcat、设备 ABI 和包路径检查
- [x] 3. DEX/native 导出
  - [x] 3.1 采集进程、`/proc/<pid>/maps`、私有目录和可读取的 `classes*.dex`
  - [x] 3.2 记录 native 加载证据；业务 DEX 未导出时生成可复核阻塞状态
- [x] 4. 源码与资源恢复
  - [x] 4.1 对有效 DEX 执行反编译并保存工具日志
  - [x] 4.2 解码资源、整理 Manifest、native 文件和导出文件索引
- [x] 5. native 与壳证据关联
  - [x] 5.1 分析 `libyiqilibrary.so` 的 JNI 导出、字符串和加载调用链
  - [x] 5.2 将静态符号、运行时加载事件和导出 DEX 建立来源关联；业务 DEX 关联暂缺并已记录

> 验证记录：运行时 `libart.so` 导出表未暴露 `RegisterDexFile`，离线符号偏移试验导致目标进程 `SIGSEGV`，已移除该偏移 hook；后续只采用无侵入内存扫描和静态符号证据。
- [x] 6. 端到端验证与报告
  - [x] 6.1 重复运行并校验输入 APK SHA-256 不变
  - [x] 6.2 输出恢复结果、阻塞原因、工具版本和后续人工检查项
