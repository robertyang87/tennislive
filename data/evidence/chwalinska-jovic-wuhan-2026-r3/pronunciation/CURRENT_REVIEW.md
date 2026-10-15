# 当前V3真实冻结配音复核完成

实际冻结包 `e35d913c416209be96566582110d4c9d21ce6c170cdebcf8380d7f651b4ad82e`。7条云见 `zh-CN-YunjianNeural / +6% / +0Hz` 口播，43处多音/专名/品牌目标均有有限低支持，当前待核0、当前确认错读0；数字33段有完整实际无提示ASR词序与取值证据。没有封面口播。

**七条MP3及WordBoundary逐项SHA全部与实际成片 native_input_archive.json 一致**，对应电影 `d45f651435e44a0b6d8c3039f6b438f46a16ecc4133128395dbe31c2560f11dd`。方法是 `bound_input_review_not_human_listening`，没有声称听过最终混音。

全部结论保守记低支持。两项cross-negative机械LOO原始失败完整保留；最后5项依精确实际音节定位后参考曲线、真实音核及音系差异逐项审查，未把原失败改成机械通过。“会”hui/kuai的频谱对照仅有限边界支持，Burg组件不支持如实保留。缺正侧留一的单正控保留限制，实际同音核身份或声调解释另列。不是全机械组件pass。

V1/V2旧失败永久留存。旧V2“接发”的“发”确认为fà，2240个目标语音样本与“接髮”负控逐样本相同，保留在history/v2-940605eabb1e/v2-confirmed-fa4.json。V3删除“接发”二字后只重新审核新first请求，其余六请求全文、完整参数、MP3和marks字节均同才继承相应实际证据。

完整方法/原失败/有限当前支持见current-review.json、真实最终输入逐项绑定见final-film-input-binding.json；独立最后11项见independent-qc/v3-current-supplement.json、最后5的精确元音曲线与频谱见independent-qc/five-located-nuclei-results.json与five-phoneme-charts/。没有人工听审、响度处理或扫描声明。
