"""仓库里不许留短时签名 URL 的凭据部分。

**来路（2026-08-14）：** `specs/reels/shang-darderi-montreal-2026.json` 的
`source_url` 和它那份 `probe.json` 的 `url`，存的是一条 Sky Sport 的**短时签名
HLS**：

    …/master.m3u8?hdnts=st=1786073073~exp=1786073373~acl=/…/*~hmac=<64 位十六进制>

TTL 300 秒，2026-08-07 就失效了——**所以清它不是为了止血，是为了别把一条鉴权
凭据的形状留在公开仓库里**，顺带让「这条 spec 渲不了第二遍」这件事**显式**
（原来它看着像一条正常的 `source_url`，真去渲会死在下载那一步）。

⚠️ **历史里那几个 blob 不清，这是认领过的取舍。** 清它要改写历史，而这个仓库
2026-08-13 刚改写过一次——代价是所有 commit SHA 变了，钉在 `@<sha>` 上的
jsDelivr 图片链接（已经发在微信消息里）跟着失效。**再付一次同样的代价，换的是
把一批七天前就过期的 300 秒令牌从历史里抹掉，收益是零。** 真正防复发的是这条
判据加上「换取签名 URL 拉受控流」那道源禁令，不是改写历史。

⚠️ **判据宁可窄，不可宽。** 上面那段说明文字里就写着 `hdnts=st=…~exp=…~hmac=…`
——这个仓库的注释正是教训的存放处，**连形状描述一起扫，「把坑记下来」就会被判成
「又踩了这个坑」**（同一个错这里犯过五次）。所以只认**真的带上了秘密材料**的那种：
`hmac=` / `Signature=` 后面跟着一长串十六进制或 base64。省略号、`<已清除>`
这类占位一律放行，反向锚点钉住了这一条。
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: 真凭据的形状：参数名 + **至少 24 个**连续的十六进制/base64 字符。
#:
#: 24 是量出来的下界：那条 Sky 签名的 `hmac` 是 64 位十六进制，AWS 的
#: `X-Amz-Signature` 也是 64 位，CloudFront 的 `Signature` 是 base64 的
#: 一百多字符。而写说明时用的占位（`…`、`<签名串已清除>`、`abc123`）都远够不着。
_SECRET_PARAMS = (
    "hmac", "signature", "x-amz-signature", "sig", "token",
    "key-pair-id", "policy", "awsaccesskeyid",
)
_SIGNED = re.compile(
    r"(?<![\w-])(" + "|".join(re.escape(p) for p in _SECRET_PARAMS) + r")"
    r"\s*=\s*([A-Za-z0-9+/_-]{24,}={0,2})",
    re.I,
)

#: 只扫会进仓库的文本产物。二进制和 `.git` 不看。
_SCAN_GLOBS = ("specs/**/*.json", "specs/**/*.txt",
               "output/**/*.json", "output/**/*.md", "output/**/*.txt",
               "src/**/*.py", "tools/**/*.py", ".github/workflows/*.yml")


def _tracked(patterns: tuple[str, ...]) -> list[str]:
    """被 git 跟踪的文本文件，仓库相对路径。

    ⚠️ 用 `git ls-files` 不用 `Path.glob`：CI 的稀疏检出把 `output/` 挡在外面，
    索引里的条目只是被标了 skip-worktree，`glob` 在那儿恒空——**而空列表和
    「一份产物都没有」长得一模一样**。git 跑不起来要当场出声。

    ⚠️ **必须 `-z`。** 不加的话 git 会按 `core.quotePath` 把非 ASCII 路径转义成
    `"output/…/\345\217\221\345\270\203文案.txt"` 这种带引号的八进制串，拿去
    `git show :<路径>` 当场 `unknown revision or path`——这个仓库里正好有一份
    中文名的产物（`发布文案.txt`），第一版就是这么红的。顺带 `-z` 也让路径里
    含空格的情况不用再考虑分词。
    """
    out = subprocess.run(["git", "ls-files", "-z", *patterns],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, f"git ls-files 跑不起来（{out.returncode}）：{out.stderr}"
    return [line for line in out.stdout.split("\0") if line]


def _read(path: str) -> str:
    """工作树上有就读工作树，没有就读索引里那份 blob。

    ⚠️ **枚举用索引、读取用工作树，是两个口径**——只用后者会在 CI 的稀疏检出下
    `FileNotFoundError`（本仓库 2026-08-14 刚为这条红过一次）。
    """
    disk = ROOT / path
    if disk.is_file():
        return disk.read_text(encoding="utf-8", errors="replace")
    out = subprocess.run(["git", "show", f":{path}"],
                         capture_output=True, text=True, cwd=ROOT)
    assert out.returncode == 0, (
        f"{path} 既不在工作树上、索引里也读不出来（{out.returncode}）：{out.stderr}")
    return out.stdout


def test_仓库里不许留签名URL的凭据部分():
    """扫全部被跟踪的文本产物，`hmac=` / `Signature=` 后面不许跟着真的秘密材料。

    ⚠️ 它拦的是**复发**，不是历史（历史那几个 blob 是认领过的取舍，见模块 docstring）。
    出路写在报错里：把参数值换成 `<签名串已清除>` 之类的占位，并留一句说明这条
    资产为什么取不到了——**别整个删掉那个字段**，删了下一个人会以为它本来就没有源片。
    """
    files = _tracked(_SCAN_GLOBS)
    # 判据自己的判据：主语没了（glob 写错、目录改名）的样子就是空列表，
    # 而那时这条测试会安安静静地全绿。
    assert len(files) >= 200, f"只扫到 {len(files)} 份文本产物，判据失效了"

    hits: list[str] = []
    for path in files:
        for line_no, line in enumerate(_read(path).splitlines(), 1):
            m = _SIGNED.search(line)
            if m:
                hits.append(f"{path}:{line_no}  {m.group(1)}={m.group(2)[:16]}…"
                            f"（{len(m.group(2))} 字符）")

    assert not hits, (
        "这几处留着短时签名 URL 的凭据部分：\n  " + "\n  ".join(hits)
        + "\n\n短时令牌过期之后没有可用性，却把一条鉴权凭据的形状留在公开仓库里。\n"
          "补法：把参数值换成 `<签名串已清除>` 之类的占位，**保留资产路径**，"
          "并加一句 `_source_url_note` 说明这条资产为什么取不到了——"
          "整个删掉那个字段的话，下一个人会以为它本来就没有源片。")


def test_CI要批量检出签名扫描需要的文本产物():
    """别让 sparse checkout 把 1900 多个小文件退化成逐个 ``git show``。

    2026-08-21 的真实 PR run 里，签名 URL 扫描单项用了 369.93 秒；同一份
    索引在 sparse checkout 直接包含 JSON/MD/TXT 后，完整扫描实测 0.41 秒。
    根因不是正则，而是缺失文件逐个触发 Git blob 读取。这里锁住批量检出的
    三种后缀；二进制成片仍然排除。
    """
    workflow = (ROOT / ".github/workflows/ci.yml").read_text("utf-8")
    for pattern in (
        "/output/**/*.json",
        "/output/**/*.md",
        "/output/**/*.txt",
    ):
        assert pattern in workflow, (
            f"ci sparse-checkout 缺 {pattern}；签名 URL 扫描会退回逐文件 git show")


def test_这条判据不许误伤对凭据形状的描述():
    """反向锚点：**这个仓库的注释就是教训的存放处**，里面必然写着当年那些串。

    连形状描述一起扫，「把坑记下来」会被判成「又踩了这个坑」——同一个错这个
    仓库犯过五次，所以这条不是装饰，它是上面那条判据能不能长期活着的前提。
    """
    放行 = [
        "hdnts=st=…~exp=…~hmac=…`，TTL 300 秒",          # 本 PR 自己写的说明
        "master.m3u8?<签名串已清除>",                      # 清理之后留下的占位
        "签名形如 hmac=<64 位十六进制>",                    # 文档里描述形状
        "?hmac=abc123",                                   # 短的示例值
        "Signature=<省略>",
        "token=xxx",
    ]
    for line in 放行:
        assert not _SIGNED.search(line), f"误伤了对形状的描述：{line!r}"

    拦住 = [
        "?hdnts=st=1&exp=2&hmac=8e28dd738ae0fb792a37a330146374b57e1b9fb2f2b136a3a983e4688307d9e9",
        "&X-Amz-Signature=4a7f2c9b1e8d0a3f5c6b2e9d4a1f8c7b0e3d6a9f2c5b8e1d4a7f0c3b6e9d2a5f",
        "?Signature=Q1BqZXhhbXBsZXNpZ25hdHVyZXZhbHVldGhhdGlzbG9uZ2Vub3VnaA__",
    ]
    for line in 拦住:
        assert _SIGNED.search(line), f"该拦的没拦住：{line[:60]}…"
