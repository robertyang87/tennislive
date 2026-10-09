# 郑钦文—斯维托丽娜：最终实际配音复核

实际 Edge 云见 zh-CN-YunjianNeural，+6%，+0Hz。8 段（7 旁白+固定片尾），313 个送声字符；所有最终 renderer MP3 与对应生产 ZIP 原声逐字节一致，真实 WordBoundary 与最终 speakable 文本一致。没有调用 DeepSeek 或 MiniMax；没有声称人工听审。

逐字清单：40 个多音字出现位置，40 个得到声学支持，0 个未确认。默认结果和全部坏参照自测保留。见 final-review.json 与 bindings.json。

初稿唯一未确认的轻声“了”已由编辑删除；仅删除“兑现了”里的“了”。这一段已用全新 renderer voice_02.mp3 完整重新测量，其他七段确切文本、声线、语速与实际音频绑定均保持有效。

补核说明：姓名“娜”区分na/nuo的元音对照high；第一盘“发球”的“发”按f之后持续元音核区分fā/fà，wrong-side LOO通过但只有一个正确侧参考，限low；下一轮“中”的双侧F0参考自测通过high。片尾cha/chai使用持续元音核，cha1/cha4使用F0，保留第一处正确侧同音覆盖和错误侧自测失败的限制。“的”与“得”使用近韵元音代理，限low。

当前状态：acoustic_review_complete。这是声学支持报告，置信度为启发式；低置信与参考限制均明确保留。实际成片混音/编码是否完整仍由最终QC核验。

## 原始音频、测量与脚本归档

引用音频与测量路径为 ZIP 内路径；在当前 pronunciation 目录解压下面两个 ZIP 后，可按原 hash 复现。原始默认不可靠记录和所有采用的参照、自测及复现脚本完整保留；原始测量 JSON 字节没有改写。原始绝对路径经 artifact-map.json 映射到 ZIP 内相对路径，逐成员 SHA256 见 archive-manifest.json。

- `pronunciation-process-evidence.zip`：5145139 字节，SHA256 `e30cc5b39670f89ec23c0ddd7a705777220e37734ddd2781a4285852e6f370a4`；坐标、首盘、第二盘压力与回破，以及完整复现脚本。
- `pronunciation-finish-evidence.zip`：5054434 字节，SHA256 `e88621a6b035f28e23aa0ae676682f70004af7e87b81a8cac807a5995f4407dd`；抢七、统计、下一轮与片尾。

例如在本目录执行：

```bash
python -m zipfile -e pronunciation-process-evidence.zip .
python -m zipfile -e pronunciation-finish-evidence.zip .
```

归档尺寸已经实测且分别小于 8,000,000 字节，逐成员解压后的字节 SHA256 已与打包前文件一致性校验通过。

解压后执行 `python measurement-scripts/verify_archive_payloads.py`：自动核验压缩包、所有原始文件、8段实际配音及报告引用的逐项 SHA256，不依赖 scratch 路径。
