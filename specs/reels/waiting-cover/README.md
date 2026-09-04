# 等封面的 spec 放这儿，别放在 `specs/reels/` 里

CLAUDE.md「如果没封面，都先做好视频等封面」——片子可以先做完，但 **spec 不能带着一个
不存在的 `cover.portrait.image` 躺在 `specs/reels/` 里**：`validate_spec` 的
`cover_photo_problem` 会当场报「封面大图找不到」，于是

- `test_封面大图一律用官方高清图不许抽帧`
- `test_每条spec的旁白都还估得下`（它对每条 spec 走一遍 `validate_spec`）

两条会常年红，而**一条常年红的检查和没有检查是同一个毛病**。

所以约定：**图还没发布的 spec 先落在这个子目录里**，图落地之后
`mv` 回 `specs/reels/`、补上 `cover.portrait._photo_why` 和（美网这一档必然要的）
`_low_res_why`，再跑 `--dry-run` ＋ 全量、提交。

⚠️ **这个目录不被任何扫描碰到**：测试和工具扫的都是 `specs/reels/*.json`（非递归），
`promote_reel_draft` 只读 `specs/reels/pending/`——所以放这儿既不会打红全量，
也不会被自动链当成待转正的草稿捡走。

⚠️ **代价：跨会话去重看不见它。** CLAUDE.md 那条
`git ls-tree --name-only origin/main specs/reels/` 不带 `-r`，只列顶层，
所以别的会话按姓名 grep 不到这里的文件。要连这一层一起查就加 `-r`：

    git ls-tree -r --name-only origin/main specs/reels/ | grep -iE "<姓>|<姓>"
