# 配音证据提交清单

本次仅审查和准备打包清单，没有stage、commit、切分支、重新合成或修改既有未知结论。

## 应提交的小证据

`packaging-review.json`逐文件列出路径、大小和SHA256。基础小JSON/MD共75个，合计1438426字节，包含：

- `data/evidence/.../voice/production/`顶层JSON和MD：实际输入`job.json`、有限结论`voice-review.json`、完整内容审查、两档完整ASR、ASR输入映射、待用户核听清单与实际120.504秒核听音频映射、审核说明、原生配音公开恢复映射和说明。
- `production/targets/*.json`全部51个有限对照记录，保留未知和参考不足，不能只提交correct结果。
- `production/native-speech/*.marks.json`全部9个小原生边界文件，可与公开冻结包逐字节核对。
- `requests/.../voice-review/`顶层既有JSON/MD：品牌owner复用评估、合成前静态清单、冻结包公开转移证明、准备说明。

建议连同6个本期局部复现/恢复Python脚本提交，合计27358字节；它们不是生产全局代码。另提交本打包说明、`packaging-review.json`和`commit-paths.txt`。`commit-paths.txt`是完整、精确的仓库相对路径白名单，排除了全部媒体、缓存和运行日志；使用前仍应查看实际Git差异。本任务没有执行任何Git暂存命令。

## 绝不能stage的本地材料

当前两目录中共501个排除文件，21603486字节。具体路径见`packaging-review.json`，规则为：

- 任何MP3、WAV、ZIP，包括`production/frozen-tts.zip`、`actual-utterances.wav`和全部`native-speech/*.mp3`。
- 整个`production/reference-cache/`，**包括其中JSON**；整套`production/reference-locks/`；整个`tts-seed-cache/`（当前已累积9个原生缓存ZIP，不只是最早那一项品牌）。
- `.log`、`.lock`及可能出现的`__pycache__/`等运行中间文件。

不要直接暂存整个`voice/`或`voice-review/`目录。媒体的哈希或本地引用出现在JSON中，不代表应把媒体本体提交到Git。

## 原生媒体恢复与参考音频边界

原生MP3及配对marks可从以下公开、内容哈希标记URL恢复：

https://github.com/robertyang87/tennislive/releases/download/reel-tts-chwalinska-kartal-wuhan-2026-f-2414de29cc3083bf/tts_bundle.zip

严格SHA256：`2414de29cc3083bf79d08dc11e33ef22100671bd96605d8dd0fddc4ab34bf9d9`。已实际通过公开下载恢复并核对9项MP3+9项raw marks。每项完整映射和可执行恢复方法见`data/evidence/.../voice/production/native-speech-restore.json`与`NATIVE-SPEECH-RESTORE.md`。

参考控制音频不在生产冻结包内。其本地缓存不提交；target数值、F0轨迹和参考哈希仍保留，但不能把“生产原音频可恢复”夸大成“所有参考控制音频都可恢复”。若需要精确复现声学数值，应另行保全原参考缓存的带哈希归档；重新请求TTS不能冒充原参考字节。

## URL、凭据与审核状态

已扫描这两个目录现有JSON/MD/Python/日志，包括缓存JSON。没有发现需要清理的签名URL、URL用户凭据、令牌或API密钥值。保存的链接是无query参数的公开GitHub Release/Actions链接；下载服务的临时签名跳转仅在内存跟随，没有写入证据。

用户仅批准720p；本期120.504秒全旁白核听仍pending。机器unknown不变；品牌只复用上一片同完整句、同request、同MP3/marks的真实owner确认。本打包审查没有新增全片配音pass或用户听审确认。
