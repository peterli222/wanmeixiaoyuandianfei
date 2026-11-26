# -*- coding: utf-8 -*-
"""把推送内容落到本地 outbox，交给 DSH/QQ 侧转发（替代 PushPlus）。

设计：electricity_monitor.py 的 push() 在没有 pushplus_token 时调用 send()，
把「标题 + 纯文本正文」写进 outbox/*.json，并打印。DSH 的定时任务读出来发 QQ，
成功后 take/ack 清掉，避免重复推送。

CLI:
  python qq_push.py pending        # 打印待发消息(JSON 行)，不删除
  python qq_push.py take           # 打印并移入 sent/（相当于已认领）
  python qq_push.py peek           # 只看条数
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
OUTBOX = os.path.join(HERE, "outbox")
SENT = os.path.join(OUTBOX, "sent")


def html2text(s: str) -> str:
    s = re.sub(r"(?is)<style.*?</style>", "", s)
    s = re.sub(r"(?i)</t[dh]>", " | ", s)
    s = re.sub(r"(?i)</tr>", "\n", s)
    s = re.sub(r"(?i)<br\s*/?>", "\n", s)
    s = re.sub(r"(?i)</p>", "\n", s)
    s = re.sub(r"(?i)</div>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = s.replace("\u00a0", " ")
    s = re.sub(r"[ \t]+", " ", s)
    out = []
    for line in s.splitlines():
        line = line.strip()
        line = re.sub(r"^(\| )+", "", line)
        line = re.sub(r"( \| )+$", "", line)
        line = re.sub(r"(\s*\|\s*)+", " | ", line)
        if line:
            out.append(line)
    return "\n".join(out).strip()


def send(title, content, dry=False):
    text = html2text(content)
    if dry:
        print("[推送] %s (dry-run)" % title)
        print(text)
        return {"code": 0, "msg": "dry-run"}
    os.makedirs(OUTBOX, exist_ok=True)
    ts = int(time.time())
    msg = {"ts": ts, "title": title, "text": text}
    path = os.path.join(OUTBOX, "%d-%s.json" % (ts, re.sub(r"[^\w\u4e00-\u9fff]+", "_", title))[:40])
    with open(path, "w", encoding="utf-8") as f:
        json.dump(msg, f, ensure_ascii=False, indent=2)
    print("[推送] %s -> outbox/%s" % (title, os.path.basename(path)))
    print(text)
    return {"code": 0, "msg": "queued", "file": path}


def _items():
    if not os.path.isdir(OUTBOX):
        return []
    return sorted(
        os.path.join(OUTBOX, n) for n in os.listdir(OUTBOX)
        if n.endswith(".json") and os.path.isfile(os.path.join(OUTBOX, n))
    )


def cmd_pending():
    for p in _items():
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        print(json.dumps({"file": p, "ts": d.get("ts"), "title": d.get("title"),
                          "text": d.get("text")}, ensure_ascii=False))


def cmd_take():
    os.makedirs(SENT, exist_ok=True)
    for p in _items():
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        print(json.dumps({"file": p, "ts": d.get("ts"), "title": d.get("title"),
                          "text": d.get("text")}, ensure_ascii=False))
        os.replace(p, os.path.join(SENT, os.path.basename(p)))
    if not _items():
        print("EMPTY")


def cmd_peek():
    print(len(_items()))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "pending"
    {"pending": cmd_pending, "take": cmd_take, "peek": cmd_peek}.get(cmd, cmd_pending)()
