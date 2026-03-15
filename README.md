# Windows-
本项目是一个 Windows 桌面端实时翻译工具，核心链路为： 系统音频采集 -> 本地 VAD 分段 -> 本地 ASR 转写 -> 本地/在线翻译 -> 实时字幕展示 -> 历史与导出。  ## 1. 主要能力  - Windows 系统音频采集（WASAPI loopback） - 音频归一化（16kHz / mono / PCM16） - VAD 分段（静音切分 + 最长片段保护） - 本地 WebSocket 前后端通信 - 实时字幕、悬浮窗字幕、历史表格 - 历史持久化（SQLite）+ TXT/SRT 导出 - 离线会话记录（Markdown + TXT） - 离线 ASR（Vosk）与离线翻译（Argos） - 异常重试与熔断机制（云端模式）
