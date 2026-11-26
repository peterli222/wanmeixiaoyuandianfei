# -*- coding: utf-8 -*-
"""时段闸门与 30 度阈值自测。"""
import os
import sys
import time
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
# 干净 clone 上没有 config.json，测试统一读示例配置
if not os.path.exists(os.path.join(ROOT, "config.json")):
    os.environ["DIANFEI_CONFIG"] = os.path.join(ROOT, "config.example.json")
import electricity_monitor as em

ok = True


def check(name, got, want):
    global ok
    good = got == want
    if not good:
        ok = False
    print("%-42s %s  %r" % (name, "OK  " if good else "FAIL", got))


def at(h):
    d = datetime.now().replace(hour=h, minute=0, second=0, microsecond=0)
    return d.timestamp()


for h in range(24):
    want = 8 <= h < 23
    check("in_alert_window(%02d:00)" % h, em.in_alert_window(at(h)), want)

print()
check("07:59 不提醒", em.in_alert_window(at(7) + 3540), False)
check("08:00 开始提醒", em.in_alert_window(at(8)), True)
check("22:59 仍在时段", em.in_alert_window(at(22) + 3540), True)
check("23:00 停止", em.in_alert_window(at(23)), False)

print()
print("全部通过" if ok else "有失败项")
sys.exit(0 if ok else 1)
