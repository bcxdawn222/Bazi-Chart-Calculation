# Research: android-apk-runtime-unpack

## Practices

- 先做运行环境确认，再做脱壳：使用现有 Android SDK、`adb` 和 `Pixel_6` AVD 启动样本，记录安装结果、启动日志、进程映射和应用私有目录变化。这样可以区分“样本自身启动失败”和“工具链缺失”。
- 运行时优先观察 DEX 加载边界：关注 `DexClassLoader`、`InMemoryDexClassLoader`、`BaseDexClassLoader`、`System.loadLibrary`、`dlopen` 和新生成的 `classes*.dex`。这些位置直接连接壳数据与业务代码。
- 导出结果分层保存：原始内存/文件 dump、可反编译 DEX、资源解码结果、native 分析结果分别保存，避免把推测性的反编译文本误称为原始源码。
- `base.apk` 先处理，`base1.apk` 作为对照样本。前者的 DEX 只有 4 个 class 且存在约 24.4 MiB 尾随数据；后者是完整单 DEX、无 native 库，适合作为工具链和网络接口分析的校验样本。
- 当前不做外部行业调研：本阶段的主要决策由本地样本结构、已有 SDK 和 AVD 约束决定，外部资料不会改变第一轮脱壳路径。

## Constraints

- 输入样本固定为 `E:/WXWork/1688856420768484/Cache/File/2026-08/base.apk` 和 `E:/WXWork/1688856420768484/Cache/File/2026-08/base1.apk`；原始文件只读，不覆盖或重签原样本。
- 现有 `Pixel_6` AVD 为 Android 37、x86_64；`base.apk` 只包含 `arm64-v8a` 和 `armeabi-v7a` native 库。若系统没有 ARM native bridge，安装或启动阶段可能因 ABI 不匹配中断。
- 当前 `adb` 已安装但没有在线设备；`frida`、`frida-tools`、`jadx`、`apktool` 和 `baksmali` 不在 PATH。新增工具属于本地分析依赖，安装位置必须留在项目或分析工具目录，不写入客户运行前置条件。
- `base.apk` 的原始签名为 v2/v3，重打包或重签可能触发完整性检查、壳校验或服务端校验；第一轮优先使用原样本观察，只有证据表明必须修改时才建立副本。
- “获取源码”定义为从运行时 DEX 和资源恢复可反编译的 Java/Kotlin 近似源码；原始开发工程、注释、符号和构建配置不在 APK 可保证的交付范围内。
- 所有启动、停止、抓取、反编译和验证操作通过 `scripts/` 入口组织，并写入 `logs/`；固定偏移、样本专属哈希或临时补丁必须在任务记录中注明仅适用于当前样本。

## Open [TBD]

## Decided

- [DEC-1] 第一目标为 `base.apk` 的运行时业务 DEX 与资源恢复，`base1.apk` 只用于对照和工具链校验 | source: status quo | decided from static report: `base.apk` 的壳/尾随数据是当前主要阻塞点，`base1.apk` 不存在同类壳结构。
- [DEC-2] 第一轮运行时验证使用现有 `Pixel_6` AVD 和 `adb`，不先假设 ARM native bridge 存在；若 ABI 不匹配，保留完整错误证据并切换到静态壳数据分析 | source: status quo | auto | reversibility: 可改用 ARM64 真机或兼容 AVD，不改变样本。
- [DEC-3] 需要 `jadx`、`apktool`、`frida-tools` 时，安装到项目隔离工具目录或 Python `.venv`，不写入客户运行路径 | source: tool availability | escalated | rationale: 新增依赖是获取可读源码和运行时 hook 的必要条件，但会增加安装体积和环境差异 | if wrong: 可删除隔离工具目录并回到仅 SDK/ADB 的路径。
- [DEC-4] 第一轮不修改原始 APK；如需绕过启动校验，只对副本做最小、可回滚的样本专属修改，并在任务文件记录偏移、原字节和新字节 | source: signature/packer risk | escalated | rationale: 原样本更适合观察真实壳行为，修改会改变签名和校验路径 | if wrong: 保留原样本与副本，可重新从原样本开始。
- [DEC-5] 交付物以“原始 dump + DEX/资源恢复 + 反编译近似源码 + 证据报告”分层，不声称恢复原始工程源码 | source: APK artifact limits | auto | reversibility: 可在后续动态证据充分后追加更精确的恢复结果。
