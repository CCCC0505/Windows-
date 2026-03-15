注意：此项目不可直拆直用，在model文件夹中有model压缩文件，需要完成解压之后才可以运行

Windows 电脑端实时翻译（V1）
本项目是一个 Windows 桌面端实时翻译工具，核心链路为：
系统音频采集 -> 本地 VAD 分段 -> 本地 ASR 转写 -> 本地/在线翻译 -> 实时字幕展示 -> 历史与导出。
1. 主要能力
- Windows 系统音频采集（WASAPI loopback）
- 音频归一化（16kHz / mono / PCM16）
- VAD 分段（静音切分 + 最长片段保护）
- 本地 WebSocket 前后端通信
- 实时字幕、悬浮窗字幕、历史表格
- 历史持久化（SQLite）+ TXT/SRT 导出
- 离线会话记录（Markdown + TXT）
- 离线 ASR（Vosk）与离线翻译（Argos）
- 异常重试与熔断机制（云端模式）
2. 运行环境
- Windows 10/11
- Python 3.8+
- 建议内存 8GB 以上（大模型 + 离线翻译更稳）
3. 快速开始
1. 创建并激活虚拟环境
- `python -m venv .venv`

2. 安装基础依赖
- `.\\.venv\\Scripts\\python -m pip install -r requirements.txt`

3. 准备配置文件
- `Copy-Item .\\config.example.toml .\\config.toml`

4. 启动应用
- `.\\.venv\\Scripts\\python -m app.main`

4. Vosk 模型（已升级为高级模型优先）

你当前 `models` 目录建议保持如下结构：

- `models/vosk-model-en-us-0.22`
- `models/vosk-model-cn-0.22`
- `models/vosk-model-small-en-us-0.15`（可选兜底）

当前代码的模型选择逻辑如下：

1. 若 `offline_asr.model_path` 配置了有效目录，优先使用该目录。
2. 若未配置 `model_path`：
- `source_model = "en"` 时优先 `vosk-model-en-us-0.22`，再退到小模型。
- `source_model = "zh"` 时优先 `vosk-model-cn-0.22`，再退到小模型。
3. 若仍未命中，自动在 `models/` 中按“语言匹配 + 非 small + 版本号更高”挑选最佳目录。

另外，若你解压后出现“外层目录 + 内层真实模型目录”的结构（例如 `models/vosk-model-en-us-0.22/vosk-model-en-us-0.22/...`），程序也会自动识别并定位到内层模型目录。

默认配置已改为自动选择高级模型：

- `[offline_asr].model_path = ""`

5. 翻译模式说明

`offline_local`（默认）

- ASR：本地 Vosk
- 翻译：优先 Argos 离线翻译
- 若翻译组件不可用，会自动退化为转写直出（passthrough），保证“语音转文字”不中断

`mock`

- 用于链路验证，输出模拟翻译文本

`tencent`

- 腾讯云 ASR + 腾讯云机器翻译
- 需要配置密钥

`cloud`

- 预留通用 HTTP 适配模式

6. 离线翻译（Argos）部署

如果你要启用稳定离线翻译，建议按下面执行：

1. 安装核心包
- `.\\.venv\\Scripts\\python -m pip install argostranslate==1.9.6 ctranslate2==4.5.0 sentencepiece==0.2.0 sacremoses==0.0.53 stanza==1.10.1 torch==2.4.1`

2. 安装语言包
- `en -> zh`
- `zh -> en`

说明：

- 项目已内置 stanza 的本地化处理与镜像配置，优先避免运行时联网失败。
- 若网络条件差，首次下载模型可能慢，建议先完成模型下载再启动应用。

7. 关键配置项（`config.toml`）

`[provider]`

- `mode`: `offline_local | mock | tencent | cloud`
- `tencent_secret_id / tencent_secret_key`: 腾讯云密钥（tencent 模式需要）

`[offline_asr]`

- `source_model`: `en | zh`
- `model_path`: 留空时自动选择高级模型；也可手动指定目录
- `translate_backend`: `offline | tencent | auto | placeholder`
- `output_dir`: 离线会话输出目录

`[offline_translate]`

- `enabled`: 是否启用离线翻译
- `source_lang / target_lang`: 默认翻译方向
- `timeout_ms`: 离线翻译超时

 8. 日常使用流程

1. 启动应用后点击 `Start/Stop` 开始会话
2. 选择识别模型（English / 中文）
3. 选择目标语言
4. 观察实时字幕与悬浮字幕
5. 按需导出 TXT/SRT

9. 输出文件说明

- 历史数据库：`data/history.db`
- 离线会话记录：
- `exports/session-YYYYMMDD-HHMMSS.md`
- `exports/session-YYYYMMDD-HHMMSS.txt`
- 手动导出：
- `exports/history.txt`
- `exports/history.srt`

 10. 一键启动与自启动

一键启动

- 运行：`launch_app.bat`

创建桌面快捷方式

- `powershell -NoProfile -ExecutionPolicy Bypass -File .\\create_desktop_shortcut.ps1`

开机自启动快捷方式
- 启用：`powershell -NoProfile -ExecutionPolicy Bypass -File .\\create_startup_shortcut.ps1`
- 关闭：`powershell -NoProfile -ExecutionPolicy Bypass -File .\\create_startup_shortcut.ps1 -Disable`
11. 打包发布

1. 测试
- `.\\.venv\\Scripts\\python -m pytest -q`

2. 编译检查
- `.\\.venv\\Scripts\\python -m compileall app tests`

3. 打包
- 目录版：`powershell -NoProfile -ExecutionPolicy Bypass -File .\\build_release.ps1`
- 单文件版：`powershell -NoProfile -ExecutionPolicy Bypass -File .\\build_release.ps1 -OneFile`

打包产物默认在 `dist/`。

12. 常见问题

Q1: 明明有声音，但没有转写

- 检查是否启用了系统回采设备（如 Stereo Mix / 立体声混音）
- 检查是否正在播放可采集的系统音频

Q2: 离线翻译报错，但我只想要转写

- 当前已支持自动退化到 passthrough 转写，不会中断主流程

Q3: 切换英中识别后效果不对

- 确认 `source_model` 与音频语言一致
- 保持 `model_path = ""`，让系统自动切到对应高级模型

Q4: 首次离线翻译较慢

- Argos / stanza 需要首次加载模型，之后速度会明显提升

13. 项目结构（核心）

- `app/main.py`: 程序入口
- `app/server/`: 后端会话与 WS 处理
- `app/providers/`: ASR/翻译 Provider
- `app/ui/`: PySide6 界面
- `app/audio/`: 采集、处理、VAD
- `tests/`: 单元与集成测试

---

