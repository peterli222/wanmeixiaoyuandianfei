# -*- coding: utf-8 -*-
"""补回漏采的整点样本。

用法:
    python backfill.py "2026-11-24 22:00"

读取实时电量并以指定时刻写入 samples，用于定时任务漏跑时补数据。
电量读取仍走免登录云支付网关。
"""
import datetime
import os
import sqlite3
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import electricity_monitor as em

DB = os.path.join(HERE, "electricity.db")


def main():
    if len(sys.argv) < 2:
        print('用法: python backfill.py "YYYY-MM-DD HH:MM"')
        return 2
    dt = datetime.datetime.strptime(sys.argv[1].strip(), "%Y-%m-%d %H:%M")
    ts = int(dt.timestamp())
    kwh, unit, desc = em.get_kwh()
    c = sqlite3.connect(DB)
    exists = c.execute("SELECT kwh FROM samples WHERE ts=?", (ts,)).fetchone()
    c.execute("INSERT OR REPLACE INTO samples(ts,kwh,unit) VALUES(?,?,?)",
              (ts, kwh, unit))
    c.commit()
    latest = c.execute("SELECT ts,kwh FROM samples ORDER BY ts DESC LIMIT 1").fetchone()
    c.close()
    print("%s %s -> %.1f%s（实时读数：%s）" % (
        "覆盖" if exists else "补回",
        dt.strftime("%m-%d %H:%M"), kwh, unit, desc))
    print("最新样本: %s %.1f度" % (
        datetime.datetime.fromtimestamp(latest[0]).strftime("%m-%d %H:%M"),
        latest[1]))
    if exists and abs(exists[0] - kwh) > 0.01:
        print("注意: 该时刻原值 %.1f，与实时读数不一致" % exists[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
