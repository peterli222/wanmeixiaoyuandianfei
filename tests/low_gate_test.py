# -*- coding: utf-8 -*-
"""check_low：30 度阈值 + 时段闸门 + 3 小时节流的组合自测（内存库，不推送）。"""
import os
import sqlite3
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
# 干净 clone 上没有 config.json，测试统一读示例配置
if not os.path.exists(os.path.join(ROOT, "config.json")):
    os.environ["DIANFEI_CONFIG"] = os.path.join(ROOT, "config.example.json")
import electricity_monitor as em

ok = True
sent = []
em.push = lambda t, c, dry=False: sent.append(t)      # 拦截真实推送


def check(name, got, want):
    global ok
    good = got == want
    if not good:
        ok = False
    print("%-44s %s  %r" % (name, "OK  " if good else "FAIL", got))


def fresh():
    c = sqlite3.connect(":memory:")
    c.execute("CREATE TABLE samples(ts INTEGER PRIMARY KEY, kwh REAL, unit TEXT)")
    c.execute("CREATE TABLE events(ts INTEGER PRIMARY KEY, kind TEXT, detail TEXT)")
    c.execute("CREATE TABLE meta(k TEXT PRIMARY KEY, v TEXT)")
    c.commit()
    return c


# ---- 阈值 30 ----
em.in_alert_window = lambda ts=None: True
sent.clear(); c = fresh(); em.check_low(c, 35.0); check("35 度不提醒", len(sent), 0)
sent.clear(); c = fresh(); em.check_low(c, 29.9); check("29.9 度提醒", len(sent), 1)
sent.clear(); c = fresh(); em.check_low(c, 30.0); check("正好 30 度不提醒", len(sent), 0)
sent.clear(); c = fresh(); em.check_low(c, 0.5);  check("0.5 度提醒", len(sent), 1)

# ---- 3 小时节流 ----
sent.clear(); c = fresh()
em.check_low(c, 20.0); em.check_low(c, 19.0)
check("3 小时内不重复", len(sent), 1)
c.execute("UPDATE meta SET v=? WHERE k='last_low_alert'", (int(time.time()) - 3 * 3600 - 60,))
c.commit(); em.check_low(c, 18.0)
check("超过 3 小时再提醒", len(sent), 2)

# ---- 时段闸门：静默期不发也不记账 ----
em.in_alert_window = lambda ts=None: False
sent.clear(); c = fresh()
em.check_low(c, 12.0)
check("静默时段不推送", len(sent), 0)
check("静默时段不写 last_low_alert",
      c.execute("SELECT v FROM meta WHERE k='last_low_alert'").fetchone(), None)

# ---- 静默期攒着，进时段后补发 ----
em.in_alert_window = lambda ts=None: True
em.check_low(c, 11.0)
check("进入时段后补发", len(sent), 1)

# ---- 耗尽后停发 ----
sent.clear(); c = fresh()
em.check_low(c, 0.0)
em.check_low(c, 0.0)
check("电量耗尽后停发", len(sent), 1)

print()
print("全部通过" if ok else "有失败项")
sys.exit(0 if ok else 1)
