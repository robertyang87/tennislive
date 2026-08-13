#!/usr/bin/env python3
"""拿流水号问 PushPlus：这条消息到底送到微信没有。

## 来路

`publish/pushplus.py` 发完会打一行

    [PushPlus] 收下了：流水号 <id>　图片通道 …　msg=执行成功

那一行**只保证接口收下了**，不保证微信真的推到了手机上——这句警告和查询
接口的地址一直印在日志里，可**没有人能真的去查**：查询要 token，而 token
只在 runner 的 secret 里，沙箱和本地都拿不到。于是「接口成功但人没收到」
这种情况，我们手上只有一句「大概发了吧」。

这个文件把那条路补上，和 `pages-selftest.yml` 是同一个形状：**把一次验证
从发布路径里拆出来**，单独跑、不发任何消息。

## 用法

    PUSHPLUS_TOKEN=… python3 tools/check_pushplus_delivery.py <流水号>

或者走工作流 `pushplus-query.yml`（token 从 secret 取，本地不用配）。

⚠️ **这条路一条消息都不许发。** 它只 GET 查询接口；判据
`test_查投递状态那条路不许发消息` 钉住这一点——查一次状态的代价必须是零，
否则下次「查一下」就会变成「又发了一条」。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import requests

QUERY_URL = "https://www.pushplus.plus/api/send/queryMessage"
TIMEOUT = 20


def query(token: str, trace_id: str) -> dict:
    """问一次。返回解析好的响应体。"""
    resp = requests.get(QUERY_URL, params={"token": token, "id": trace_id},
                        timeout=TIMEOUT)
    resp.raise_for_status()
    return resp.json()


def describe(payload: dict) -> tuple[str, int]:
    """把响应体翻成人话，并给出退出码。

    PushPlus 的查询接口把消息记录放在 `data.list`（分页结构）或 `data`
    本身。**不同版本的返回体形状不一样，所以这儿不硬解**：认得出状态就
    翻译，认不出就把原始 JSON 打出来让人自己看——「解析不出来」和
    「没送到」是两回事，不许混成一句。
    """
    code = payload.get("code")
    if code != 200:
        print(f"[查询] PushPlus 拒绝了这次查询：code={code} "
              f"msg={payload.get('msg')!r}")
        print("       常见原因：token 不对、流水号不属于这个 token、"
              "或者记录已过期")
        return "rejected", 1

    data = payload.get("data")
    rows = []
    if isinstance(data, dict):
        rows = data.get("list") or data.get("records") or []
    elif isinstance(data, list):
        rows = data
    if not rows and isinstance(data, dict) and data.get("status") is not None:
        rows = [data]

    if not rows:
        print("[查询] 接口回了 200，但**没有这条消息的记录**——"
              "流水号可能不属于这个 token，或者记录已经过期")
        print(json.dumps(payload, ensure_ascii=False, indent=2)[:1200])
        return "empty", 1

    # 各版本字段名不统一，认得几个算几个；认不出的原样打出来
    for i, row in enumerate(rows, 1):
        status = (row.get("status") if isinstance(row, dict) else None)
        title = (row.get("title") if isinstance(row, dict) else None)
        channel = (row.get("channel") if isinstance(row, dict) else None)
        when = (row.get("createTime") or row.get("sendTime")
                if isinstance(row, dict) else None)
        print(f"[记录 {i}] 状态={status!r} 渠道={channel!r} "
              f"标题={title!r} 时间={when!r}")
    print("\n原始返回体（字段名各版本不一，以它为准）：")
    print(json.dumps(payload, ensure_ascii=False, indent=2)[:2000])
    return "ok", 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("trace_id", help="发送时日志里那行流水号")
    args = ap.parse_args()

    token = os.environ.get("PUSHPLUS_TOKEN", "").strip()
    if not token:
        print("[查询] 环境里没有 PUSHPLUS_TOKEN——查询接口要它。"
              "走 pushplus-query.yml 工作流，token 从 secret 取。")
        return 1

    print(f"[查询] 流水号 {args.trace_id}")
    try:
        payload = query(token, args.trace_id)
    except requests.RequestException as exc:
        # ⚠️ 「查不到」和「没送到」是两件事，日志里不许混成一句
        print(f"[查询] 请求本身失败了（{exc}）——**这不代表消息没送到**，"
              "只代表这次查询没成功")
        return 1
    _kind, rc = describe(payload)
    return rc


if __name__ == "__main__":
    sys.exit(main())
