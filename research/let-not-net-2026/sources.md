# let-not-net-2026 源片检索记录

2026-10-15。沙箱连不上 YouTube，检索放在临时工作流（已删）里用 `yt-dlp ytsearch` 跑，查询词见 `queries.txt`。
入选的全部是官方频道，经 `download-video.yml` 存进 Release `source-<id>`，两档英文转写在 `data/source_asr/<id>/`。

| 键 | 视频 | 频道 | 用途 |
|---|---|---|---|
| er | ErRIKW61Rsc「Unlikely 4 Lets In A Row」 | Tennis TV | 冷开场、结尾回合（竖版，规整为 er_c，见 normalize.sh） |
| hat | hAwOXW99Kbk 穆雷帽子掉落 let，鹿特丹 2022 | Tennis TV | 不碰网的 let |
| fr | 4zNsWcQ8jcY 弗里茨口袋掉球，上海 2026 | Tennis TV | 巡回赛规则 |
| fe | uScYlhMSeD4 兹维列夫与羽毛，澳网 2025 | Australian Open | 外物进场 |
| bj | IhbxwdeYHLo 兹维列夫/德约 VAR，中网 2026 | Tennis TV | 场边设备、德约原话 |
| wb | GeMppP-gRKc 大坂直美 vs 穆霍娃加长集锦，温网 2026 | Wimbledon | 讲解底片（无解说窗口） |
| ng | PZVUqAkrS1E Next Gen ATP Finals Rules Explained | Tennis TV | 取消发球 let（方版，规整为 ng_c） |
| zq | SB4QxpFvcmo 郑钦文快四表演赛忘了 let 规则，澳网 2025 | Australian Open | 快四不重发；封面帧 14.0s |
| sq | 17IqrJNNvFY Squash 101: Stroke / Yes Let / No Let | PSA SQUASHTV | 壁球 let |

检索过但没用：Pegula 2024 美网 let 后双误（S5IgXi2HASE，情节要靠解说才讲得清）；Pouille 场上鸟（ZUvnK6UVdlk，不是球打中鸟）；BWF Development「Lets (Service)」（UCBV_MmVR-A，只有 720p）。

## 封面（2026-10-15 返工）

账号所有者：「不要用郑钦文做封面」「副标题改成擦网喊的是 Let 不是 Net」「不要后面半句了」「封面要清晰表达 Let 的场景，而且必须用高清大图」。

检索 Let 场景的高清实拍（临时工作流已删，脚本最后一版留在 cover_search.py）：
- Wikimedia Commons 搜索 ＋ Tennis nets／Tennis umpires 分类：没有擦网实拍（最接近的是温网主裁量网高、美网主裁掷硬币）
- AP 原图：WTOP、KXAN、WFLA、PIX11、KTLA、KRON4、WATE、WKRG 等站的 WordPress 媒体库按说明全文搜，350 条网球图里只有球员撞网、触网丢分
- Flickr CC 搜索页：无相关结果；Unsplash／Openverse：要授权（401）；Getty：只拿得到带水印的预览图
- 并排给了 A 球撞网特写／B 主裁赛前量网高／C 福格尼尼趴网三版；账号所有者先选 A、钩子只留一行，随后改选 B，并让第二句钩子再斟酌，定为「主裁喊的是阻碍」

## 成片版本

| 版本 | 封面 | 成片 film_sha256 | render run |
|---|---|---|---|
| v1（已推送） | 郑钦文表演赛抽帧 | 28886c75da18… | 38682385186 |
| v2（已推送） | 球撞网特写（A） | cd575ab8968e… | 38690517063 |
| v3 | 主裁量网（B），钩子「擦网为啥喊Let／主裁喊的是阻碍」 | cccb421c9623… | 38693115964 |
