# 当前冻结包中文读音审查

结论：complete_with_declared_supported_low_name。当前 8 个真实请求，20 处正文常规多音位置和49处姓名音节全部有实际音频支持，未确认0处；确认错读0处。当前 coordinate 塔维持有效组合方法的低置信正确支持，不升级为中/高。固定片尾按完整文本、profile、MP3、WordBoundary exact 复用旧审批，旧限制保留。

实际输入：`/workspace/scratch/ostapenko-tts-repaired.zip`

SHA256：`097242a138184043d122391d3958776505670af16ed50eaee5142697c26ae473`

声线：zh-CN-YunjianNeural，rate +6%，pitch +0Hz。只有 coordinate / tiebreak_payoff 两请求变化，另6请求完整文本/profile/MP3/marks字节一致，逐条见 old-repaired-exact-reuse.json。全部当前精确绑定见 bindings.json / frozen-manifest.json / final-review.json。

本轮只追加4个待核音节各正2反2，共16个当前完整语境单目标参照，不再合成。佩真实5.58–5.62秒核心降2.91半音，正确侧沛/配降、错误侧赔/陪升，双侧LOO全部有效，score0.731。拉最终a核保留真实时间：actual斜率+12.749 st/s，垃/邋+17.666/+16.587，辣/瘌−15.766/−25.493，双侧LOO全有效，score0.763；actual静态MFCC到正确侧距离2.649，小于正确侧彼此3.064，CV支持成立。拉默认窗口和等长归一化形状失败均保留在证据。coordinate斯真实3.70–3.75秒核心与丝/嘶完全一致，嗣/四下降，补核双侧LOO全部有效，score1.0，默认单侧override历史仍保留。TB奥当前参照双侧LOO有效且音核近同音，high score1.0；科真实F0核双侧LOO有效，medium0.789。

coordinate塔原组合方法双侧参照LOO有效、当前CV有效，score0.287为correct low；补纯F0时错误参照LOO失败，不据此抬置信度，也不将其伪装实际错读。

旧稿种/解/分3处未确认原样冻结在 old-final-review.json、OLD_FINAL_REVIEW.md 和 old-6df4a0c7f60b/。分末窗的misread反证和另一内窗correct结果都保留；当前稿删除这3位置，未把旧未知重写成正确或确诊错读。落/迫在未变请求中已有真实CV及降调组件支持，按exact字节继承。

没有调用DeepSeek/MiniMax，没有宣称人工听审，没有用词典或ASR汉字直接判声调，没有更改主仓库、spec或屏幕文字。原始失败、旧语境差异、当前真实音核范围和独立参照hash均留存。
