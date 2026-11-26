# -*- coding: utf-8 -*-
"""检查采样间隔，找出漏采的时间段。"""
import os
import sqlite3
import sys
import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PATH = os.environ.get("DIANFEI_DB") or os.path.join(ROOT, "electricity.db")
if len(sys.argv) > 1:
    PATH = sys.argv[1]
if not os.path.isfile(PATH):
    raise SystemExit("找不到数据库：%s\n用法: python tests/gaps.py [electricity.db 路径]" % PATH)
c = sqlite3.connect(PATH)
rows = c.execute("SELECT ts, kwh FROM samples ORDER BY ts").fetchall()
print("样本数:", len(rows))


def fmt(t):
    return datetime.datetime.fromtimestamp(t).strftime("%m-%d %H:%M:%S")


gaps = []
prev = None
for ts, kwh in rows:
    mark = ""
    if prev is not None:
        d = (ts - prev) / 60.0
        gaps.append(d)
        if d > 61:
            mark = "  <-- 漏了 %d 分钟" % round(d - 60)
    print(fmt(ts), "%.1f度" % kwh, mark)
    prev = ts

if gaps:
    print()
    print("间隔: 最小 %.1f 分 / 最大 %.1f 分 / 平均 %.1f 分"
          % (min(gaps), max(gaps), sum(gaps) / len(gaps)))
    print("超过 61 分钟的间隔:", sum(1 for g in gaps if g > 61), "次")
