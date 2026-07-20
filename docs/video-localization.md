# 授权海外视频中文化

这条管线只处理操作者已经放到本地、且有明确改编与发布权限的视频。它没有下载器，
不会从 YouTube、Instagram、TikTok、转播商或媒体网站抓取视频。翻译或加字幕本身不会
自动取得转载权。

## 输入

1. 本地视频，例如 `incoming/interview.mp4`
2. 与视频对应的本地 SRT，例如 `incoming/interview.en.srt`
3. 授权清单，参考 `data/video_rights.example.json`

`rights_basis` 可选 `owned`、`licensed`、`written_permission`、
`creative_commons`、`public_domain`。授权清单必须允许翻译；生成硬字幕视频时还必须允许
再次发布。带 `ND`（禁止演绎）的 Creative Commons 许可会被拒绝。推荐填写视频 SHA-256，
避免把一份授权清单误用于另一个文件。

## 运行

```bash
export GITHUB_MODELS_TOKEN=github_pat_xxx

tennislive video \
  --video incoming/interview.mp4 \
  --subtitles incoming/interview.en.srt \
  --rights incoming/interview.rights.json \
  --outdir output/video/interview
```

默认生成简体中文字幕、带硬字幕的 MP4 与 `rights-audit.json`。系统需要 `ffmpeg` 可执行
文件；加 `--no-burn` 只生成 SRT 和授权审计，加 `--bilingual` 生成原文/中文双语字幕。
重复生成时需显式加 `--overwrite`。

输出目录：

- `interview.zh-CN.srt`：审核与发布用中文字幕
- `interview.zh-CN.mp4`：可选的硬字幕成片
- `attribution.txt`：发帖时一并使用的来源署名
- `rights-audit.json`：授权声明、源文件哈希与输出记录

GitHub Action 可以用同一命令处理仓库内或 artifact 解包后的本地素材。应把 token 放在
Actions Secret 中；授权文件和视频不要放入公开仓库，除非其许可明确允许公开分发。
