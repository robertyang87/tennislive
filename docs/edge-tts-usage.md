# Edge TTS 使用说明

## 当前状态与适配范围

2026-10-12 使用 `edge-tts 7.2.8` 实测：旧合成连接返回 `WSServerHandshakeError` / HTTP 403；加载本仓库适配后，`zh-CN-YunjianNeural`、语速 `+6%`、音高 `+0Hz` 成功生成有效 MP3。这是当时的连通性实测，不代表服务永远可用，也不是发音正确性审核。

同日用共享原生入口、不加载专用 `sitecustomize` 再测一次：短句“赛场之上，继续下一场。”在 1.644 秒内生成可解码的 2.832 秒 MP3，并返回 6 条词边界。该探测只确认技术连通，没有重新合成已冻结成片，也不作人工听审或声调正确性结论。

原生视频入口已由共享 [`src/tennislive/video/tts.py`](../src/tennislive/video/tts.py) 自动迁移已知的旧合成端点到 `wss://api.msedgeservices.com/tts/cognitiveservices/websocket/v1`，无需额外加载专用审音目录。迁移复用库内置的 `TRUSTED_CLIENT_TOKEN`，保留 voice、语速、音高、GEC、User-Agent 与内容缓存；上游的新端点和调用方明确配置的端点保持原样。端点迁移依据：[edge-tts 上游 PR #491](https://github.com/rany2/edge-tts/pull/491)。

下面直接调用第三方 `python -m edge_tts` 的示例仍使用 [`tools/alcaraz_voice_review/runtime/sitecustomize.py`](../tools/alcaraz_voice_review/runtime/sitecustomize.py) 作为 CLI 适配。该目录用于当时的阿卡语音审查；[`tools/alcaraz_voice_review.py`](../tools/alcaraz_voice_review.py) 本身只接受那条已冻结视频的九段旁白，不是通用配音命令。

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

`tools/measure_polyphone.py` 的参考合成也直接复用原生 Edge 的已知端点迁移、显式代理和失败分类，无需专用 shim。它保留原始参考文本及 `(文本, 声线, 语速, 音高)` 缓存键，不套纠音换字，也不切换后端。证书或库已判定不可恢复的失败立即返回；暂时连接失败最多再试两次，等待 2 秒和 6 秒，用尽后不再等待。已有精确缓存命中不发网络请求。

## 原生视频旁白检查

沿用 README 中的项目安装与依赖配置。加入项目源码，并显式选择 Edge 后端：

```bash
PYTHONPATH=src \
TENNISLIVE_TTS_BACKEND=edge \
python tools/build_match_reel.py render \
  --spec specs/reels/<slug>.json \
  --outdir /tmp/tennislive-narration \
  --check-narration
```

正式 spec 应通过以下字段记录后端选择及理由，再使用同一环境运行原有制作命令：

```json
{
  "tts_backend": "edge",
  "_tts_backend_why": "本片采用 Edge TTS，使用已验证的新合成端点"
}
```

这条路径仍由共享 [`src/tennislive/video/tts.py`](../src/tennislive/video/tts.py) 生成音频与词边界，并使用原有内容缓存、重试和词边界校验。`--check-narration` 检查段落时长与切词，不替代待发布语音的读音检查。Edge 路径支持这里示例中的声线、语速和音高；spec 中的 Azure 情绪风格或 `lead_pause` 不能直接照搬到 Edge。

GitHub Actions 中使用原生视频入口同样自动获得共享模块的端点适配。已有 `alcaraz-voice-review.yml` 使用专用审音包装器，仅服务冻结的阿卡视频。

## 代理与失败排查

原生共享 TTS 将环境中的 `HTTPS_PROXY`（其次 `https_proxy`）显式传给每次合成请求；没有这些变量时保持直接连接，不修改第三方库的全局构造器。CLI 的专用适配文件则把 `HTTPS_PROXY` 设置为构造器默认值。

**Edge CLI 会主动传入 `proxy=None`，覆盖这个默认值。** 如果当前环境需要已配置的 `HTTPS_PROXY`，在上面的 CLI 命令中额外指定 `--proxy "$HTTPS_PROXY"`。本地实测过的完整调用如下：

```bash
PYTHONPATH=tools/alcaraz_voice_review/runtime \
python -m edge_tts \
  --proxy "$HTTPS_PROXY" \
  --voice zh-CN-YunjianNeural \
  --rate=+6% --pitch=+0Hz \
  --text "阿卡的反扑，停在抢七最后关头。" \
  --write-media test.mp3
```

无需代理的环境使用前面的基础命令。代理地址由运行环境配置，不写入仓库。需要代理 CA 的环境沿用 [`tennislive.localca`](../src/tennislive/localca.py) 的配置，在导入 Edge TTS 前加载可信 CA。

- `ModuleNotFoundError: edge_tts`：确认当前 Python 环境已经安装上面的包。
- 仍报 403：原生入口确认使用了当前仓库版本；第三方 CLI 确认包含适配目录的 `PYTHONPATH`，代理环境还须显式传 `--proxy`。适配后仍失败时记录实际错误，不能把过去的成功当成本次成功。
- 证书错误：检查当前环境的代理与 CA 配置。CA 校验通过和合成端点可用是两项不同检查。

本次实测没有修改系统安装的包文件，也没有关闭 TLS 验证。合成结果继续按原有视频生产和读音复核要求使用。
