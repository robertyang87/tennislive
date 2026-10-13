# 按视频产线选择回归测试

账号所有者在 2026-10-13 明确授权：「不同类型的视频产线的要求不一样，不用所有测试都走一遍」。CI 现在检查实际 base/head 的文件差异，自动选择所属产线和公共合同。`ci / test` 仍是合并所需的同一个检查状态；它的成功表示计划中所选范围通过，不能称为全仓通过。

## 产线和选择规则

| 输入变更 | 回归范围 |
|---|---|
| `specs/reels/`、所属请求、比赛发布账本、`output/<date>/reel/` | 比赛剪辑产线（赛场之上）＋公共检查 |
| `specs/interviews/`、所属请求与发布账本、采访产物 | 采访产线（赛后开麦）＋公共检查 |
| `specs/explainers/`、`src/tennislive/video/episodes/*.json`、所属请求与产物 | 讲解／故事产线＋公共检查 |
| 新闻视频配置与产物 | 新闻产线＋公共检查 |
| 同一提交涉及多条线 | 范围取并集，不允许手动标签压掉其他线 |
| 已审查的产线 workflow | 对应产线＋全仓 workflow 公共合同 |
| Python 源码 | 沿实际导入、局部动态导入、合同中的源文件引用扩展到消费者；影响非视频产品或全局 fixture、没有明确消费者时 full |
| 新增、被实际 spec 引用的封面照片；能按 spec 引用／slug 认领的证据 | 所有已识别的拥有产线＋公共检查 |
| 已有图片／字体／品牌资源、公共设计与通用卡片渲染、依赖、包初始化、测试／选择器／CI 本身 | full |
| 未知路径、被删除的代码、无法取得 base/diff、空 diff、未登记或缺失测试、工作树与指定 head 不一致 | full |
| 普通 README／CLAUDE／`docs/*.md` | 少量公共文档、权限、凭据与 workflow 合同 |

这里按实际渲染管线划分，不只按栏目文字：走 match-reel 的「网球有故事」比赛素材剪辑仍属于比赛剪辑管线；讲解配置走 explainer。原生校验器继续根据栏目执行各自要求，不会把比赛的比分板要求强加给采访或纯讲解。

每条生产线保留全部已登记的自身回归，加上字幕／原声／画布／官方来源／人名／证据绑定／发布幂等／链接与微信等公共合同。跨线文件不按名字排除：例如 `explainer.py` 还提供比赛与采访共享的字幕或配音函数，公共裁切、字体和发布规则会覆盖实际消费者。初版消费者分析偏保守；大型共享渲染器仍可能 full，不声称所有源码修改都能缩窄。

全仓 workflow 的字体、依赖、Pages、提交身份和缓存要求有些藏在 `test_match_reel.py`、`test_interview_clip.py`、`test_explainer.py` 中。清单选择这些**原有函数节点**，不复制判据、不执行无关历史大包。其他产线中实际读取本线 spec 的测试，也按原节点补入；若由 module 常量／fixture／helper 读取则保留整个文件。整文件已选时去掉重复节点，避免同一断言执行两次。

明确清单在 [production_test_scopes.json](../tools/production_test_scopes.json)。新增测试必须登记完整归属；未登记时回退 full，不能让新测试静静消失。`.xhs.txt`、实际审核证据、发布账本和 `_why` 不按普通文档豁免。

## 本地与 CI 使用

本地先准备与 CI 一致的已提交输入，再生成范围：

```bash
python tools/production_test_scopes.py --base origin/main --head HEAD --outdir /tmp/production-test-scope
cat /tmp/production-test-scope/plan.json
mapfile -t targets < /tmp/production-test-scope/pytest-args.txt
PYTHONPATH=src pytest "${targets[@]}" -rs -n auto --dist loadfile --durations=25 -o faulthandler_timeout=180
```

需要主动完整检查：

```bash
python tools/production_test_scopes.py --full --outdir /tmp/production-test-scope
```

PR 用事件的 base SHA 和实际检出的合并树比较；主干 push 用事件的 before 和当前树比较。先窄范围取回 base，无法取到就 full。NUL 分隔的真实 diff 不折叠重命名，跨线移动同时包含旧线和新线。未提交源码／配置和另一个 head 的工作树不用于缩窄判断。

选择在重量依赖准备前完成，但初版保留原字体、FFmpeg、浏览器及模型安装，避免通过缺依赖把实际检查变成 skip。每次报告实际 base/head、变化路径、选择原因、清单 SHA 和 pytest 参数；报告在日志、Actions 摘要与独立 artifact 中保存。空参数直接失败，pytest 非零照常失败。历史诊断仍单独排在 pytest 之前，不能作为新电影的通过凭证。

pytest 显式设定 `PYTHONPATH=src`，绑定当前检出的包源码。首次本地独立产线运行发现环境中的 editable 安装仍指向旧工作区，混入旧代码和资产路径；这些失败不算当前产线结果。纠正导入路径后重跑，并保留此环境差异记录。

每日 UTC 03:23 和手动触发 CI 都执行 full，测试清单和选择框架改动也执行 full。rebase 后重新计算并通过新 head 的范围，不能拿旧提交的绿代替。

## 制作和发布仍按当期产物验收

测试分层不代替当期 spec dry-run、实际配音装载与听审、源 SHA、原帧上的字幕位置、全片原生 QC、电影／ASS／spec 绑定、Release 完整 GET 哈希、复制页和微信唯一 provider 回执。分层只改变回归范围，不降低画质、不调整现场原声，也不发送任何消息。

这次首次部署另外验证了三条实际故障：采访英文字体不一致、采访竖屏裁切闸失效、比赛字幕位置窗口被忽略。各自原生测试先正常通过，随后在独立进程注入故障后失败；这些节点都包含在对应计划中，失败退出码不会被工作流吞掉。真实跨线依赖审计见 [cross-line-cases.json](../data/evidence/production-test-scopes/cross-line-cases.json)。

本地代表性改动的实际收集数为比赛 3535、采访 3207、讲解 1718、新闻 1342。代表性路径只用于测试分层，没有改写或发布任何电影。首次部署分别执行主要产线检查，并对最终选择框架改动做一次完整 CI；执行结果以 PR 当前 head 的检查和 [实测记录](../data/evidence/production-test-scopes/validation.json) 为准。用例减少不等于总耗时同比例减少，尚不能据此承诺 20 分钟视频交付。
