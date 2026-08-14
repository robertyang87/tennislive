"""解说片这条线的落地闸——**它写好了一次都没跑过**（2026-08-14 接上）。

`tools/check_explainer_landed.py` 174 行、`tools/check_explainer_voice.py` 80 行，
而 `grep -rn check_explainer_landed .github/` 除了脚本自己**零命中**。CLAUDE.md
把「`check_explainer_landed` 报不合格」列为仅有的两个该停下来的闸之一——
**规矩写了、工具写了、就是没接上。**

同一个形状仓库栽过一次：`check_reel_landed.py` 也曾零调用方，补跑一遍它自己就
报出两个真缺陷（音轨比画面短 ×7、38 秒数字静音 ×1）。工具自己的 docstring 写着
「只在成功时出声的检查，没法证明它真的看过」——**一个从来没被调用的检查比那还
弱一档**。

这份测试钉三件事，缺一件这道闸就没意义：

1. **真的被调用了一次**（不是躺在 tools/ 里）
2. **排在正确的位置**——只钉「被调用」拦不住有人把它挪到 `rm -f "$CLIP"` 后面，
   那时成片已经删了、render.json 和 push.html 已经重写了，没得验
3. **期望值不许抄成字面量**——`check_explainer_voice.py` 正是栽在这上面
   （`WANT_RATE` 停在 `+28%`，而代码 2026-08-03 定回 `+22%`）
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

WORKFLOW = Path(".github/workflows/explainer.yml")
LANDED = Path("tools/check_explainer_landed.py")
VOICE = Path("tools/check_explainer_voice.py")


def _yaml_only(text: str) -> str:
    """去掉整行注释。

    工作流的注释是这个仓库记教训的地方——这一步的注释里就明写着
    `check_explainer_landed`、`--says`、`+28%`。连注释一起扫，「把坑记下来」
    会被判成「又踩了这个坑」，而且这次更坏：注释里出现脚本名会让
    「有没有真的调用」变成一盏**假绿**。判据宁可窄，不可宽。
    """
    return "\n".join(ln for ln in text.splitlines()
                     if not ln.lstrip().startswith("#"))


def _steps(text: str) -> list[str]:
    """按 `      - name:` 切出步骤名，顺序即执行顺序。"""
    return [ln.split("- name:", 1)[1].strip()
            for ln in text.splitlines() if ln.startswith("      - name:")]


def _step_blocks(text: str) -> list[tuple[str, str]]:
    """(步骤名, 这一步自己那一段)，已去掉整行注释。

    ⚠️ 按**整行头** `\\n      - name:` 切。从裸的 `- name:` 切再按 `- name:`
    分割会在第 0 位截断拿到一个空串（`_step_block` 那条注释记的就是这个）。
    """
    body = _yaml_only(text)
    out = []
    for chunk in body.split("\n      - name:")[1:]:
        out.append((chunk.splitlines()[0].strip(), chunk))
    return out


def _strip_comments_and_docstrings(src: str) -> str:
    """扫 Python 源码之前先把注释和三引号串剥掉——同一个理由。"""
    src = re.sub(r'"""[\s\S]*?"""', "", src)
    return "\n".join(ln for ln in src.splitlines()
                     if not ln.lstrip().startswith("#"))


def test_解说片的两个检查脚本都要真的被调用一次():
    """零调用方的检查，和没有检查是同一个毛病——只是它看起来像有。"""
    jobs = _yaml_only(WORKFLOW.read_text(encoding="utf-8")).split("\njobs:", 1)[1]
    for tool in ("tools/check_explainer_landed.py", "tools/check_explainer_voice.py"):
        assert tool in jobs, f"没有任何一步调用 {tool}——它就是个没人跑的脚本"
    # 空调用（不给 --says）只查「目录非空」，那是一盏恒亮的绿灯，不是闸。
    assert "--says" in jobs, "调了 check_explainer_landed 却不给 --says，等于什么都没查"


def test_落地闸要排在删成片和提交之前():
    """位置三头都要卡住，钉「被调用」拦不住把它挪到后面去。

    - 排在 **`rm -f "$CLIP"` 之前**：那一步（成片发到 Release）末尾把成片删了，
      还会重写 `render.json` 和 `push.html`，排在它后面就没得验了；
    - 排在**提交之前**：进了 main，`publish pushplus` 就会把它发到微信，
      而微信那条消息发出去收不回来（match-reel 那条闸同样的理由）；
    - 排在**上传 artifact 之后**：闸红了片子还有处可取，和提交步骤那句
      「成片仍在 artifact 里」是同一个承诺。

    ⚠️ 删成片那一步**按它真的在删**去认，不按步骤名认——改个名字就绕过去的
    判据等于没有。
    """
    text = WORKFLOW.read_text(encoding="utf-8")
    names = _steps(text)
    blocks = _step_blocks(text)
    assert [n for n, _ in blocks] == names, "步骤切分和步骤名对不上"

    gate = next(i for i, n in enumerate(names) if "查这一版产物本身合不合格" in n)
    gen = next(i for i, n in enumerate(names) if "生成解说视频" in n)
    upload = next(i for i, n in enumerate(names) if "artifact" in n)
    commit = next(i for i, n in enumerate(names) if "提交成片到仓库" in n)
    kills = [i for i, (_, b) in enumerate(blocks) if 'rm -f "$CLIP"' in b]
    assert kills, "找不到那一步删成片的——这条判据的主语没了，得换判据"

    assert gen < upload < gate, (
        f"闸在第 {gate} 步，而生成在 {gen}、上传 artifact 在 {upload}——"
        "它必须排在渲完之后、而且排在上传之后（红了片子还得有处可取）")
    assert gate < min(kills), (
        f"闸在第 {gate} 步，而第 {min(kills)} 步就把成片 rm 掉了——排在它后面没得验")
    assert gate < commit, (
        f"闸在第 {gate} 步、提交在 {commit}——进了 main 就会被推到微信，消息收不回来")


def test_喂给闸的是每屏小标不是旁白原文():
    """⚠️ `.ass` 去过标点、`.words.json` 本来就不含标点，**旁白搜不到**。

    而搜不到报出来是「★ 一个文件都没有」——**和「这一版没落库」长得一模一样**，
    正是这个脚本存在的全部理由要防的东西。2026-08-14 拿存量 39 条 deck、243 屏
    量过（不是推的）：小标命中 241；旁白前 14 字含标点的 228 条只命中 7。
    """
    gate = dict(_step_blocks(WORKFLOW.read_text(encoding="utf-8")))["查这一版产物本身合不合格"]
    assert "seg.title" in gate, "喂进 --says 的不是每屏小标"
    assert ".narration" not in gate, (
        "把旁白原文喂进了 --says——标点会让它必然搜不到，而那个红看起来像「没落库」")


def test_配音的期望值只有一个出处不许抄一份字面量():
    """**这一条是清假红。** `WANT_RATE` 抄着 `+28%`，而代码 2026-08-03 定回 `+22%`。

    量过存量：29 份已落库的 `narration.json` 里 **19 份是 `+22%`**（当前代码
    默认）、10 份是 `+28%`。也就是说照原样把这个脚本接进工作流，**今天每一条
    新片子都会报「✗ 与期望不符」**——一条常年红的检查和没有检查是同一个毛病。

    「一个数写两处必分叉」，所以期望值直接读代码里那份。
    """
    from tennislive.video.explainer import DEFAULT_RATE, DEFAULT_VOICE

    body = _strip_comments_and_docstrings(VOICE.read_text(encoding="utf-8"))
    assert not re.search(r'["\']\s*[+-]\d+%\s*["\']', body), (
        "语速的期望值又被抄成了字面量——它会停在某一版，然后对每条新片子常年红")
    assert not re.search(r'["\']zh-[A-Za-z-]+Neural["\']', body), (
        "语音名又被抄了一份，同一个毛病")

    # ⚠️ 光「源码里没有字面量」不够：也可能是有人把这两个常量整个删了。
    # 真跑一遍，证明期望值确实等于代码默认。
    got = subprocess.run(
        [sys.executable, "-c",
         "import importlib.util,sys;"
         "s=importlib.util.spec_from_file_location('cev','tools/check_explainer_voice.py');"
         "m=importlib.util.module_from_spec(s);s.loader.exec_module(m);"
         "print(m.WANT_VOICE);print(m.WANT_RATE)"],
        capture_output=True, text=True, check=True).stdout.split()
    assert got == [DEFAULT_VOICE, DEFAULT_RATE], (
        f"期望值 {got} 和代码默认 {[DEFAULT_VOICE, DEFAULT_RATE]} 对不上")


def test_落地闸要能读工作区不然它在提交之前根本查不了(tmp_path):
    """闸排在提交之前，那一刻 outdir 一个字节都还没进 git。

    脚本默认从 `origin/main` 读，那条路在这个位置上报出来是「还不存在」——
    **那句话的意思是「还没提交」，不是「不合格」**，而这个脚本存在的全部理由
    就是把这两件事分开。所以 `--local` 不是锦上添花，是这道闸装得上的前提。
    """
    outdir = tmp_path / "explainer" / "demo"
    outdir.mkdir(parents=True)
    (outdir / "xiaohongshu.txt").write_text("位置不够 官方把她挪去了中心球场", encoding="utf-8")

    def run(*args):
        return subprocess.run([sys.executable, str(LANDED), "--local", str(outdir),
                               "demo", *args], capture_output=True, text=True)

    ok = run("--says", "挪去了中心球场")
    assert ok.returncode == 0, f"工作区里明明有这句话，却报了不合格：{ok.stdout}"
    assert "xiaohongshu.txt" in ok.stdout, "没报出它命中在哪个文件里"

    miss = run("--says", "这句话根本不在里面")
    assert miss.returncode == 2, "缺一句照样报绿"
    assert "一个文件都没有" in miss.stdout

    # 目录压根不存在时，两条路要各说各的话——「还没提交」不能读成「不合格」。
    gone = subprocess.run([sys.executable, str(LANDED), "--local",
                           str(tmp_path / "nope"), "demo", "--says", "x"],
                          capture_output=True, text=True)
    assert gone.returncode == 2 and "是空的" in gone.stdout, gone.stdout


def test_什么都不查的调用不许报已落地(tmp_path):
    """不给 `--says` 也不给 `--slide` 时只剩「目录非空」——那不是闸，是绿灯。

    接进工作流的当天就得防住：谁把 `--says` 那一串漏了，这一步照样 0 退出，
    而「查过了」这三个字会被记到这条片子头上。
    """
    outdir = tmp_path / "demo"
    outdir.mkdir()
    (outdir / "xiaohongshu.txt").write_text("随便什么", encoding="utf-8")
    r = subprocess.run([sys.executable, str(LANDED), "--local", str(outdir), "demo"],
                       capture_output=True, text=True)
    assert r.returncode == 2, "什么都没查却报了「已落地」"
    assert "什么都没查" in r.stdout


def test_幻灯取不到时要说清是没东西可验还是不合格(tmp_path):
    """2026-08-13 起幻灯和成片都不进 git 了（走 Release + archive-media 清过）。

    量过：`origin/main` 上 `slide_*.jpg` 和 `*.mp4` **各 0 个**。所以走 git ref
    那条路比画面，必然取不到——而那是「没东西可验」，不是「这一版不合格」。
    报错里要把出路说出来（用 `--local` 在渲完当场比），别只说一句取不到。
    """
    src = LANDED.read_text(encoding="utf-8")
    assert "2026-08-13 起不进 git" in src, "没写清楚幻灯为什么取不到，下一个人会当成片子不合格"
    outdir = tmp_path / "demo"
    outdir.mkdir()
    (outdir / "xiaohongshu.txt").write_text("随便什么", encoding="utf-8")
    r = subprocess.run([sys.executable, str(LANDED), "--local", str(outdir), "demo",
                        "--slide", "5", "--against", str(outdir / "nope.png")],
                       capture_output=True, text=True)
    assert r.returncode == 2 and "取不到" in r.stdout, r.stdout
    # --local 那条路不该再劝人「用 --local」——它已经在用了。
    assert "请用 --local" not in r.stdout, "已经是 --local 了还劝人用 --local"
