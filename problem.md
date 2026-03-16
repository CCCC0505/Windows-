下载后跑不起来的 90% 原因与解决

### 1) 只看到 `[audio_segment 2.5s]`（识别变成占位）
原因：`vosk` Python 包没装，或 Vosk 模型目录不完整/路径不对。

解决：
1. 安装 vosk：
```powershell
.\.venv\Scripts\python -m pip install vosk
```
2. 确认模型目录存在且完整（必须包含 `am/final.mdl` 和 `conf/model.conf`）：
- `models\vosk-model-en-us-0.22\am\final.mdl`
- `models\vosk-model-en-us-0.22\conf\model.conf`
- `models\vosk-model-cn-0.22\am\final.mdl`
- `models\vosk-model-cn-0.22\conf\model.conf`
3. `config.toml` 推荐保持：
- `[offline_asr].model_path = ""`（让程序自动选最优模型）
- 需要强制时再填：`model_path = "models/vosk-model-en-us-0.22"` 或 `...cn-0.22`

### 2) 字幕里显示 `(passthrough)`（翻译看起来“没用上”）
原因：离线翻译后端（Argos）不可用或缺语言包/资源，程序会自动退化为“原文直出”，保证不断流。

解决（离线翻译）：
1. 安装离线翻译依赖（推荐一键装，可能较大）：
```powershell
.\.venv\Scripts\python -m pip install argostranslate==1.9.6 ctranslate2==4.5.0 sentencepiece==0.2.0 sacremoses==0.0.53 stanza==1.10.1 torch==2.4.1
```
2. 安装 Argos 语言包（至少装 `en->zh`，需要双向就再装 `zh->en`）：
- 语言包是 `.argosmodel`，下载安装到 Argos 默认目录即可（通常在用户目录下的 argos-translate packages）。
- 如果你不想让用户手动找包，README 里写明“从哪里下载语言包 + 放到哪里”。

3. 检查配置：
- `config.toml`：
  - `[offline_asr].translate_backend = "offline"`
  - `[offline_translate].enabled = true`
  - `[offline_translate].source_lang = "en"`
  - `[offline_translate].target_lang = "zh"`

### 3) “能启动但没反应/没字幕”，或提示没有可翻译音频
原因：Windows 系统回采设备不可用，没采到系统声音（不是代码问题）。

解决：
1. 确保正在播放系统声音（浏览器/播放器确实有声音）
2. Windows 声音设置里启用回采：
- 经典做法：启用 `Stereo Mix / 立体声混音`
- 或确保默认播放设备支持 WASAPI loopback
3. 若仍不行：在 `config.toml` 里把 `[audio].vad_energy_threshold` 调低一点试试（例如 280 -> 120）

### 4) 打包版 exe 能启动但识别/翻译不可用
原因：打包时没把依赖打进去，或打包机上缺模型/语言包。

解决：
1. 打包前先确保 venv 里依赖齐：
```powershell
.\.venv\Scripts\python -m pip install -r requirements.txt
```
2. 如果需要离线翻译，打包前也要装好 Argos 依赖（同上）
3. 重新打包：
```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build_release.ps1
```

### 5) GitHub 仓库里为什么不包含 `models/*.zip`？
原因：Vosk 模型体积非常大（你现在的 zip 大约 3GB+），直接放 GitHub 很容易 push 失败或下载体验极差。

推荐做法（README 写清楚）：
- 仓库只放代码与配置模板
- 模型让用户自行下载并解压到 `models/`
- 给出明确目录名示例：`models/vosk-model-en-us-0.22`、`models/vosk-model-cn-0.22`
