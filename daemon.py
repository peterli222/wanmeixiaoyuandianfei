# -*- coding: utf-8 -*-
"""单实例守护：保证只有一个采样进程，避免重复采样/重复推送。

  python daemon.py start     # 后台起一个（已有存活实例则拒绝）
  python daemon.py stop      # 停掉
  python daemon.py status    # 看是否活着 + 心跳
"""
from __future__ import annotations

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PID = os.path.join(HERE, ".daemon.pid")
HB = os.path.join(HERE, ".heartbeat")
LOG = os.path.join(HERE, "monitor.log")


def _alive(pid):
    try:
        out = subprocess.run(["tasklist", "/FI", "PID eq %d" % pid],
                             capture_output=True, text=True).stdout
        return str(pid) in out
    except Exception:
        return False


def _pid():
    try:
        with open(PID) as f:
            return int(f.read().strip())
    except Exception:
        return None


def start():
    p = _pid()
    if p and _alive(p):
        print("已在运行 pid=%d，不重复启动" % p)
        return 1
    exe = sys.executable
    log = open(LOG, "a", encoding="utf-8")
    proc = subprocess.Popen([exe, "-u", "electricity_monitor.py", "run",
                             "--interval", "3600"],
                            cwd=HERE, stdout=log, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL,
                            creationflags=(getattr(subprocess, "DETACHED_PROCESS", 0x8)
                                           | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
                                           | getattr(subprocess, "CREATE_NO_WINDOW", 0x8000000)))
    with open(PID, "w") as f:
        f.write(str(proc.pid))
    print("已启动 pid=%d" % proc.pid)
    return 0


def stop():
    p = _pid()
    if not p:
        print("没有 pid 文件")
        return 0
    if not _alive(p):
        print("pid=%d 已不在" % p)
        os.remove(PID)
        return 0
    subprocess.run(["taskkill", "/PID", str(p), "/F"], capture_output=True)
    os.remove(PID)
    print("已停止 pid=%d" % p)
    return 0


def status():
    p = _pid()
    alive = bool(p and _alive(p))
    print("pid      : %s (%s)" % (p, "运行中" if alive else "已退出"))
    try:
        hb = int(open(HB).read().strip())
        print("心跳     : %s（%.0f 秒前）"
              % (time.strftime("%m-%d %H:%M:%S", time.localtime(hb)),
                 time.time() - hb))
    except Exception:
        print("心跳     : 无")
    return 0


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    sys.exit({"start": start, "stop": stop, "status": status}.get(cmd, status)())
