# 本地自备图片（仅本地渲染用，不提交、不上传）

这个文件夹被 `.gitignore` 忽略：放进来的图片**不会被 `git commit`、也不会推送到远端**，
只存在你本地机器上，用来渲染你**自己私下学习/家庭观看**用的视频。

## 怎么用

把图片按下面的文件名放进本文件夹（`assets/local/`），支持 `.jpg` / `.jpeg` / `.png` / `.webp`：

| 文件名 | 会替换成 |
|---|---|
| `ao.jpg` | 澳网：四宫格「澳网」格 + 罗德·拉沃球场名片 |
| `rg.jpg` | 法网：菲利普·夏蒂埃球场名片 |
| `wim.jpg` | 温网：中央球场名片 |
| `uso.jpg` | 美网：阿瑟·阿什球场名片 |

然后重新渲染：

```bash
python tools/build_grand_slam_short.py --overwrite
```

有对应文件时自动优先用你本地的图；没有就用仓库里自由许可的默认图。

## 离线中文配音（piper 神经语音，可选）

把 piper 的中文模型放到 `assets/local/piper/`（同样不入库），渲染加 `--tts` 会自动优先用它
（音质远好于 gTTS；本环境微软 edge-tts 被拒时的首选）：

```bash
pip install piper-tts
mkdir -p assets/local/piper && cd assets/local/piper
# 从 Hugging Face rhasspy/piper-voices 下载 zh_CN 音色（约 60MB）：
#   zh_CN-huayan-medium.onnx 与 zh_CN-huayan-medium.onnx.json
```

引擎优先级：edge-tts（若可用）→ piper（若有模型）→ gTTS（兜底）。

## 权利提醒

放什么图、如何使用你本地渲染出的成片，由你自行判断与负责。仓库里公开、会被推送的那一版，
始终只用自由许可（CC / CC0 / 公有领域）素材；受版权保护的图片请不要提交进仓库。
