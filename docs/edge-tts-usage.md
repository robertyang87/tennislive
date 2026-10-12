# Edge TTS 使用说明

## 当前状态与适配范围

2026-10-12 使用 `edge-tts 7.2.8` 实测：旧合成连接返回 `WSServerHandshakeError` / HTTP 403；加载本仓库适配后，`zh-CN-YunjianNeural`、语速 `+6%`、音高 `+0Hz` 成功生成有效 MP3。这是当时的连通性实测，不代表服务永远可用，也不是发音正确性审核。

适配文件为 [`tools/alcaraz_voice_review/runtime/sitecustomize.py`](../tools/alcaraz_voice_review/runtime/sitecustomize.py)。Python 启动时通过 `PYTHONPATH` 自动加载它，将合成 WebSocket 切换到 `wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1`。它复用库内置的 `TRUSTED_CLIENT_TOKEN`，没有更改 voice、语速、音高、GEC 或 User-Agent。端点迁移依据：[edge-tts 上游 PR #491](https://github.com/rany2/edge-tts/pull/491)。

适配代码已进入仓库，但目前共享 TTS 模块没有自动加载它。**只设置 `TENNISLIVE_TTS_BACKEND=edge` 仅选择后端，不会迁移端点；调用时仍需下面的 `PYTHONPATH`。** 文件所在目录用于当时的阿卡语音审查，直接 `python -m edge_tts` 可以合成其他文本；[`tools/alcaraz_voice_review.py`](../tools/alcaraz_voice_review.py) 本身则只接受那条已冻结视频的九段旁白，不是通用配音命令。

## 单句与文本文件

以下 Bash 命令都在仓库根目录运行。先安装本次验证过的版本：

```bash
python -m pip install edge-tts==7.2.8
```

单句合成：

```bash
PYTHONPATH=tools/alcaraz_voice_review/runtime \
python -m edge_tts \
  --voice zh-CN-YunjianNeural \
  --rate=+6% --pitch=+0Hz \
  --text "阿卡的反扑，停在抢七最后关头。" \
  --write-media test.mp3
```

从 UTF-8 文本文件读取：

```bash
PYTHONPATH=tools/alcaraz_voice_review/runtime \
python -m edge_tts \
  --voice zh-CN-YunjianNeural \
  --rate=+6% --pitch=+0Hz \
  --file narration.txt \
  --write-media narration.mp3
```

`--text` 与 `--file` 二选一。声线、语速和音高可以按实际制作要求调整；文案或参数变化后须重新检查实际语音。若安装了 `ffprobe`，可核对音频有效性与时长：

```bash
ffprobe -v error -show_entries format=duration,size -of json test.mp3
```

MP3 可解码、非空只证明合成成功，不证明多音字、姓名或数字读得正确。

## 原生视频旁白检查

沿用 README 中的项目安装与依赖配置。将适配目录和项目源码一起加入 `PYTHONPATH`，并显式选择 Edge 后端：

```bash
PYTHONPATH=tools/alcaraz_voice_review/runtime:src \
TENNISLIVE_TTS_BACKEND=edge \
python tools/build_match_reel.py --slug <slug> --check-narration
```

正式 spec 应通过以下字段记录后端选择及理由，再使用同一环境运行原有制作命令：

```json
{
  "tts_backend": "edge",
  "_tts_backend_why": "本片采用 Edge TTS，使用已验证的新合成端点"
}
```

这条路径仍由共享 [`src/tennislive/video/tts.py`](../src/tennislive/video/tts.py) 生成音频与词边界，并使用原有内容缓存、重试和词边界校验。`--check-narration` 检查段落时长与切词，不替代待发布语音的读音检查。Edge 路径支持这里示例中的声线、语速和音高；spec 中的 Azure 情绪风格或 `lead_pause` 不能直接照搬到 Edge。

GitHub Actions 的临时调用同样需要将该适配目录加入命令的 `PYTHONPATH`。已有 `alcaraz-voice-review.yml` 使用专用审音包装器，仅服务冻结的阿卡视频；其他制作工作流不会因此自动获得这项端点适配。

## 代理与失败排查

适配文件检测到 `HTTPS_PROXY` 时，会将该代理显式传给 `edge_tts.Communicate`；没有该变量时保持直接连接。代理地址可通过运行环境配置，不要写入仓库。需要代理 CA 的环境沿用 [`tennislive.localca`](../src/tennislive/localca.py) 的配置，在导入 Edge TTS 前加载可信 CA。

- `ModuleNotFoundError: edge_tts`：确认当前 Python 环境已经安装上面的包。
- 仍报 403：先确认命令从仓库根目录执行，且包含适配目录的 `PYTHONPATH`；已加载适配仍失败时记录实际错误，不能把过去的成功当成本次成功。
- 证书错误：检查当前环境的代理与 CA 配置。CA 校验通过和合成端点可用是两项不同检查。

本次实测没有修改系统安装的包文件，也没有关闭 TLS 验证。合成结果继续按原有视频生产和读音复核要求使用。
