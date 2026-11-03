# vibetennis 特效与工具清单（视觉 · 声学）

账号所有者 2026-11-03：「把我们所用到的特效或者工具也梳理和调研清楚，给我们后续带来视觉效果以及声学效果上更好呈现的，都能物尽其用」。

这份分三块：**已有的家底**（EP01–EP05 实际用过、代码在哪、什么时候用）→ **约束**（量出来的）→ **升级路线**（调研过的工具，每条标了核实程度和授权）。
写新一集的镜头提纲时，先在第一块里挑，挑不到再看第三块。

核实标记：✅ 本会话实测或读过官方页面；⚠️ 只有二手来源，用之前去官方页面核。

---

## 一、已有的家底

### 1. 3D 场景（Three.js r170，`episodes/<slug>/r3d/scene.js`）

| 手法 | 用过的集 | 适合讲什么 | 代码参考 |
|---|---|---|---|
| 全息蓝网格地面（雾 FogExp2 只在 EP01 EP02） | 全部 | 所有开场、转场的「实验室」底 | EP02 `scene.js` |
| Bloom 辉光（UnrealBloomPass） | 全部 | 发光线条、粒子、读数；强度 0.4（EP04/05）比 0.85（EP01/02）更克制、更清楚 | EP05 第 702 行 |
| 自写的后期着色器 `finalPass`（9 个参数） | EP05 最全 | 见下表，镜头事件靠它们推 | EP05 第 703–718 行 |
| 粒子拼字（THREE.Points，中英各一份） | EP03–EP05 | 钩子问题、章节标题、片尾金句——这是全片最「抓眼」的一下 | EP05 `MSH` |
| 球的轨迹管（TubeGeometry＋CatmullRomCurve3） | EP05 | 弹跳角度、出射角对比 | EP05 lanes |
| 线框边（EdgesGeometry＋LineSegments，全部）、粗线（Line2，EP01 EP02 EP04） | 全部 | 全息感的场馆、示意图 | EP02 |
| InstancedMesh（大量重复体） | EP04 EP05 | 看台座位、马尔可夫树节点 | EP05 场馆 |
| CanvasTexture／Sprite 贴字、贴图标 | 全部 | 3D 空间里的数字标签 | EP04 |
| 自建场馆（超椭圆／八边形看台、可开合顶棚） | EP05 | 四大满贯场馆 | EP05 `VENUES` |
| 地球＋飞行弧线（非线性时间重映射、高度随距离变） | EP05 | 讲「四个地方」「全世界」 | EP05 `globeCam` |
| GLB 模型加载（GLTFLoader） | EP05（已关，`USE_GLB=false`） | 所有者自建模型改好后可开 | EP05 |

**`finalPass` 九个旋钮**（一个着色器里全有，按镜头事件拧）：

| 参数 | 效果 | 用在什么时候 |
|---|---|---|
| `uFlash` | 白闪 | 揭晓答案、数字落定 |
| `uCA` | 色差（RGB 错位） | 默认 0.0015 给「镜头感」；冲击时拉大 |
| `uZoom` | 径向变焦模糊 | 冲进去／转场 |
| `uShake` | 机位抖动 | 击球、落地冲击 |
| `uGlitch` | 横向撕裂＋红条 | 「误差」「出错」「伪造」的瞬间 |
| `uFreeze` | 冷色降饱和＋扫描线 | 时间冻结、慢放分析 |
| `uTilt` | 移轴微缩（中间清、上下虚） | 俯瞰场馆、地球、全景 |
| 胶片颗粒（常开 0.025） | 去掉 CG 的塑料感 | 常开 |
| `uT` | 时间（驱动抖动和撕裂） | — |

### 2. 叠加层（skia-python，`episodes/<slug>/overlay.py`）

| 元素 | 函数 | 用途 |
|---|---|---|
| 锚定字幕（带引线，跟 3D 锚点走） | `caption` | 栏目标配：字幕放在被讲的东西旁边 |
| HUD 标签／括号框 | `hudlabel` `bracketbox` | 给 3D 物体点名 |
| 全息瞄准环 | `reticle` | 锁定接触点、关键帧 |
| 卫星高度读数 | `altimeter` | 地球、航拍镜头 |
| 城市标签（背面自动隐藏） | `citylabels` | 地球 |
| 马克笔线＋画板卡片 | `mline` `card` `tele` | 解说员式的「圈画」（telestrator） |
| 章节标签（右上） | `chapter` | 结构提示 |
| 品牌标（左上） | `brand` | 栏目合同 |
| 富文本发光、逐字揭示 | `rich` | 关键数字 |

### 3. 声音（`episodes/<slug>/sfx.py`，numpy＋scipy 程序化合成）

**所有音效都是自己合成的，没有采样素材**——好处是零授权风险、能精确对齐；代价是质感偏「合成器」。
EP05 现有音色库（函数名即音色）：`pock`（击球，可慢放降调）、`bounce`、`squash`（慢放压扁）、`slide`（滑行摩擦）、`crackle`（红土颗粒）、
`swish` `riser` `hit` `boom` `slam`（转场与揭晓）、`blip` `tick` `click` `ding` `chime` `sparkle` `number_pop` `counter_roll`（界面与数字）、
`panel` `power_on/off` `zap` `shutter` `glitch` `hum` `freeze_in` `wind`（科技与氛围）、`crowd` `applause` `tvize`（现场与电视声）。
混响是自己生成的噪声脉冲响应（`ir` / `verb`）。

| 其他 | 现状 |
|---|---|
| BGM | EP04、EP05 是同一首：`robertyang87/vibeknowledge` 库的 `we-never-remix-hi-noise-qiucheng.m4a`；**授权来源没有书面记录**（库内 README 只写「发布时优先用平台曲库同曲」）；EP05 用小节重复把它续长 |
| 旁白 | edge-tts 云健 +18%（中文版，EP03 起）；英文版不配音 |
| 混音 | 两遍 loudnorm 到 -14 LUFS、限幅；QC 查真峰值 ≤ -1 dBTP、背景声铺满 |

---

## 二、约束（实测）

- **渲染是纯 CPU 软件 GL**（Chromium swiftshader，4 核）：EP05 全片 79 块的中位数 **2.6 秒/帧**、p90 5.0 秒/帧，整片约 70 分钟。
  任何「每帧多渲 N 次」的效果（累积运动模糊、景深、超采样）成本 ×N，**只能用在几秒钟的英雄镜头上**
- **会话网络有白名单**：polyhaven、freesound、sonniss、ambientcg、pixabay 在本会话里都连不上（✅ 2026-11-03 实测被代理拒绝）；
  npm、PyPI 通。素材要么所有者在环境里放行这些域名，要么照 TTS 的老办法在 GitHub Actions runner 上下载再推回仓库
- **skia-python 144 没有 Skottie（Lottie）模块**（✅ 实测 `dir(skia)` 无此项）——Lottie 动画不能直接在叠加层里用

---

## 三、升级路线（按「效果提升 ÷ 成本」排）

### A. 立刻能用、零授权风险

| # | 做什么 | 为什么值 | 核实 |
|---|---|---|---|
| A1 | **英雄镜头的累积运动模糊**：同一帧在 `t-Δ…t+Δ` 渲 8 个子帧取平均 | 我们是离线逐帧渲、`renderAt(t)` 是确定性的，所以能做实时引擎做不到的**真运动模糊**；球速、挥拍、慢放转快放一下子从「CG」变「摄影」。只开在击球／落地那 1–2 秒，成本可控 | ✅ 原理基于现有 `renderAt(t)`；未实做 |
| A2 | **音效跟画面左右声像**：`place(pan=)` 早就有，但都是手填；改成按 overlay 的 3D 锚点横坐标自动算 | 球从左飞到右，声音也跟着走——耳机党（大多数手机观众）立刻感觉到「空间」 | ✅ `place()` 已支持 pan；锚点已在 `.anchors.json` |
| A3 | **渲染分发到 Actions 矩阵**：240 帧一块本来就是独立的，丢给 10–20 个 runner 并行 | 整片 70 分钟 → 十分钟级；改完重渲不再是心理负担，审片轮次可以多 | ⚠️ runner 也是 CPU，需实测单块速度 |
| A4 | **把 `finalPass` 搬进共用引擎**并给每个旋钮写「什么情绪用它」（上表） | 每集都在复制粘贴、参数漂移（bloom 0.85 vs 0.4） | ✅ |

### B. 视觉升级（开源库，npm 可装）

| # | 工具 | 带来什么 | 授权 / 兼容 | 核实 |
|---|---|---|---|---|
| B1 | **pmndrs `postprocessing` 6.39.6** | 选择性辉光（只让该亮的亮）、SMAA 抗锯齿、景深、God rays 光束、LUT 调色、更好的色调映射——一套电影级后期 | MIT；peerDependencies `three >=0.168 <0.188`，r170 在范围内 | ✅ `npm view` 实测版本与依赖；⚠️ 不能和 three 自带 EffectComposer 混用（二手），要把 finalPass 改写成它的 Effect |
| B2 | **troika-three-text 0.53.1** | 3D 空间里的 SDF 文字：任意字号都锐利、能弯曲、能逐字动画——数字从球场上「长出来」 | MIT | ✅ `npm view` |
| B3 | **Poly Haven HDRI 与 PBR 材质** | 环境反射让球、金属顶棚、奖杯有真实高光；红土、草、硬地换成真实扫描材质 | CC0，可商用、不用署名，只是不能声称原作者 | ✅ 官方 FAQ；下载需放行域名或走 runner |
| B4 | ambientCG 材质 | 同 B3，备选 | ⚠️ 二手说是 CC0，官网本会话打不开 | ⚠️ |
| B5 | Blender（Cycles）出封面和片头英雄帧 | 光追质感，用于静帧完全够快 | GPL（工具本身；渲出的图归我们） | ⚠️ 未在容器里试装 |

### C. 声学升级

| # | 工具 / 素材 | 带来什么 | 授权 | 核实 |
|---|---|---|---|---|
| C1 | **Spotify pedalboard 0.9.26** | 专业压缩、限幅、卷积混响、EQ 一行一个；替掉手写的 scipy 滤波和噪声混响；**旁白侧链闪避**（说话时 BGM 自动让路）做得更自然 | GPLv3（我们只在内部制作时用、不分发它，没问题） | ✅ pip 可下载；许可证读的是官方仓库说明 |
| C2 | **真实卷积混响 IR**（OpenAIR 约克大学库） | 「体育场」「室内馆」「空旷实验室」的真实空间感，替掉合成的噪声 IR | 逐个文件看，上传者在 CC 各版本里选，部分保留所有权利 | ⚠️ 用哪个就核哪个文件的页面 |
| C3 | **Sonniss GDC 音效包**（每年一包，历年合计 100GB+） | 真实击球、观众、体育场环境声；和合成音效混用，「pock」立刻有真实的皮和线 | 二手一致说：免版税、可商用、**不用署名**，禁止拿去训练 AI | ⚠️ 官方许可页 sonniss.com/gdc-bundle-license 本会话打不开，用前核 |
| C4 | Freesound 的 CC0 筛选 | 补特定声音（网球拍线、红土滑步） | 只挑 CC0；CC-BY 要署名，CC-NC 不能用 | ⚠️ 域名本会话不通 |
| C5 | **BGM 换成授权清楚的来源** | 现在这首没有授权记录，而且连用两集 | Pixabay 音乐：二手说可商用免署名，但**部分曲目登记了 Content ID，合法使用也可能被认领**；最稳是平台曲库（视频号／抖音发布时选）或付费曲库 | ⚠️ 需要所有者定 |
| C6 | 中文配音换开源模型（CosyVoice 2 等） | 更自然的停顿和情绪，摆脱 edge-tts 的机器味 | 二手说 Apache 2.0；要读官方仓库与模型卡确认「权重」的许可 | ⚠️ 且要 GPU 才快，容器里慢 |

### D. 不建议

- **BBC 音效库**：⚠️ 印象中许可是非商业（RemArc），本次没核；号是商业号，除非核到可商用，否则不用
- **把 Lottie 动画塞进叠加层**：skia-python 没 Skottie；要用得另起渲染器，不值
- **整片开累积运动模糊／景深**：成本 ×8，70 分钟变 9 小时

---

## 四、建议的落地顺序

1. **A2 自动声像 ＋ C1 pedalboard 混音**：只改 `sfx.py` 一侧，下一集就能听出差别，零授权风险
2. **A1 英雄镜头运动模糊 ＋ B2 SDF 文字**：视觉上最显眼的两处
3. **B1 换 pmndrs 后期**（顺便把 finalPass 搬进共用引擎，A4）
4. **素材类（B3、C2、C3）**：要么放行域名，要么写一条 runner 下载工作流；每个文件把来源和许可写进 `episodes/<slug>/ASSETS.md`
5. **C5 BGM**：所有者定来源

## 出处

- pmndrs postprocessing 手册：<https://pmndrs.github.io/postprocessing/manual>；仓库 <https://github.com/pmndrs/postprocessing>
- troika-three-text：<https://protectwise.github.io/troika/troika-three-text>
- Poly Haven 授权 FAQ：<https://polyhaven.com/faq>
- Spotify pedalboard：<https://github.com/spotify/pedalboard>、<https://spotify.github.io/pedalboard>
- OpenAIR 脉冲响应库：<https://www.openair.hosted.york.ac.uk/?page_id=2>
- Sonniss GDC 包（二手报道）：<https://rekkerd.org/sonniss-releases-gdc-2026-game-audio-bundle/>、<https://gamefromscratch.com/sonniss-27-5gb-sound-effect-giveaway-at-gdc-2024/>
- Pixabay 音乐与 Content ID（二手）：<https://hellothematic.com/thematic-vs-pixabay/>、<https://musicgpt.com/blog/truly-safe-copyright-free-music/>
- CosyVoice 2（二手）：<https://tts.ai/voices/cosyvoice2-chinese-male>
