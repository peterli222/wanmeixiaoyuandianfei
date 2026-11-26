# -*- coding: utf-8 -*-
"""电费看板：本地网页可视化。

启动： python web_server.py            （默认 http://127.0.0.1:8848）
      python web_server.py 9000       （换端口）

只读 electricity.db，不联网、不需要登录。
"""
import json
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("DIANFEI_DB") or os.path.join(HERE, "electricity.db")
CONFIG_PATH = os.environ.get("DIANFEI_CONFIG") or os.path.join(HERE, "config.json")
WEB_DIR = os.path.join(HERE, "web")


def load_cfg():
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def db():
    c = sqlite3.connect(DB_PATH)
    c.execute("CREATE TABLE IF NOT EXISTS samples("
              "ts INTEGER PRIMARY KEY, kwh REAL, unit TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS events("
              "ts INTEGER PRIMARY KEY, kind TEXT, detail TEXT)")
    c.execute("CREATE TABLE IF NOT EXISTS meta("
              "k TEXT PRIMARY KEY, v TEXT)")
    return c


def day_key(ts):
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")


def build_payload():
    cfg = load_cfg()
    c = db()
    rows = c.execute("SELECT ts, kwh FROM samples ORDER BY ts").fetchall()
    samples = [{"ts": int(t), "kwh": round(float(k), 2)} for t, k in rows]
    threshold = float(cfg.get("threshold_low", 30))
    label = (cfg.get("room") or {}).get("label", "宿舍")
    now = int(time.time())

    # ---- 按天聚合 ----
    days = {}
    for s in samples:
        d = day_key(s["ts"])
        it = days.setdefault(d, {"date": d, "first": s["kwh"], "last": s["kwh"],
                                 "min": s["kwh"], "max": s["kwh"], "n": 0})
        it["last"] = s["kwh"]
        it["min"] = min(it["min"], s["kwh"])
        it["max"] = max(it["max"], s["kwh"])
        it["n"] += 1

    # ---- 相邻样本求用量（充值会让电量跳升，按 0 处理） ----
    daily = {}
    for i in range(1, len(samples)):
        a, b = samples[i - 1], samples[i]
        drop = a["kwh"] - b["kwh"]
        if drop <= 0:
            continue
        if b["ts"] - a["ts"] > 6 * 3600:   # 间隔太久，不可信
            continue
        daily[day_key(b["ts"])] = daily.get(day_key(b["ts"]), 0.0) + drop

    daily_list = []
    for d in sorted(days):
        daily_list.append({
            "date": d,
            "used": round(daily.get(d, 0.0), 2),
            "kwh": round(days[d]["last"], 2),
            "min": round(days[d]["min"], 2),
            "max": round(days[d]["max"], 2),
            "samples": days[d]["n"],
        })

    # ---- 小时分布（按样本所在小时累计用量） ----
    hourly = [0.0] * 24
    for i in range(1, len(samples)):
        a, b = samples[i - 1], samples[i]
        drop = a["kwh"] - b["kwh"]
        if drop <= 0 or b["ts"] - a["ts"] > 6 * 3600:
            continue
        hourly[datetime.fromtimestamp(b["ts"]).hour] += drop

    # ---- 摘要 ----
    cur = samples[-1] if samples else None
    used_total = sum(daily.values())
    span_days = max(1, len(daily_list))
    per_day = used_total / span_days if used_total > 0 else None
    summary = {
        "label": label,
        "current": cur["kwh"] if cur else None,
        "current_ts": cur["ts"] if cur else None,
        "age_sec": (now - cur["ts"]) if cur else None,
        "threshold": threshold,
        "sample_count": len(samples),
        "first_ts": samples[0]["ts"] if samples else None,
        "used_total": round(used_total, 2),
        "per_day": round(per_day, 2) if per_day else None,
        "days_left": round(cur["kwh"] / per_day, 1) if (cur and per_day) else None,
        "low": bool(cur and cur["kwh"] <= threshold),
    }

    return {
        "generated_at": now,
        "summary": summary,
        "samples": samples,
        "daily": daily_list,
        "hourly": [round(x, 2) for x in hourly],
    }


# ---- 手动查询（网页上的「立即查询」按钮）----
_query_lock = threading.Lock()
_last_query_ts = 0


def run_query():
    """点按钮时实时读一次电量并入库，返回 (ok, payload_or_error)。

    走的是和定时任务同一个 do_sample，所以充值检测、低电提醒逻辑完全一致。
    用锁 + 冷却时间挡住连点，避免把公共网关打爆。
    """
    global _last_query_ts
    cfg = load_cfg()
    cooldown = int(cfg.get("query_cooldown_sec", 60))
    with _query_lock:
        now = int(time.time())
        if _last_query_ts and now - _last_query_ts < cooldown:
            wait = cooldown - (now - _last_query_ts)
            return False, {"error": "太频繁了，%d 秒后再试" % wait, "cooldown": wait}
        try:
            import electricity_monitor as em
            c = em.db()
            try:
                kwh = em.do_sample(c, dry=False, verbose=False)
            finally:
                c.close()
        except Exception as e:
            return False, {"error": "查询失败：%s" % e}
        _last_query_ts = int(time.time())
        return True, {"kwh": round(float(kwh), 2), "ts": _last_query_ts}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body, ctype):
        data = body.encode("utf-8") if isinstance(body, str) else body
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path == "/api/data":
            try:
                self._send(200, json.dumps(build_payload(), ensure_ascii=False),
                           "application/json; charset=utf-8")
            except Exception as e:
                self._send(500, json.dumps({"error": repr(e)}, ensure_ascii=False),
                           "application/json; charset=utf-8")
            return
        if path in ("/", "/index.html"):
            fp = os.path.join(WEB_DIR, "index.html")
            try:
                with open(fp, encoding="utf-8") as f:
                    self._send(200, f.read(), "text/html; charset=utf-8")
            except Exception as e:
                self._send(500, "缺少 web/index.html: %r" % (e,), "text/plain; charset=utf-8")
            return
        self._send(404, "not found", "text/plain; charset=utf-8")

    def do_POST(self):
        path = self.path.split("?")[0]
        if path != "/api/query":
            self._send(404, "not found", "text/plain; charset=utf-8")
            return
        ok, result = run_query()
        body = {"ok": ok}
        body.update(result)
        if ok:
            try:
                body["data"] = build_payload()
            except Exception as e:
                body["ok"] = False
                body["error"] = "数据读取失败：%r" % (e,)
            code = 200
        else:
            code = 429 if "cooldown" in result else 500
        self._send(code, json.dumps(body, ensure_ascii=False),
                   "application/json; charset=utf-8")


def export(out_path=None):
    """把当前数据内嵌进一份独立 HTML，双击即可看，不需要起服务。"""
    out_path = out_path or os.path.join(HERE, "电费看板.html")
    with open(os.path.join(WEB_DIR, "index.html"), encoding="utf-8") as f:
        html = f.read()
    payload = json.dumps(build_payload(), ensure_ascii=False)
    payload = payload.replace("</", "<\\/")   # 防止提前闭合 script
    html = html.replace('<script id="embedded" type="application/json">null</script>',
                        '<script id="embedded" type="application/json">%s</script>' % payload)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    return out_path


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "export":
        p = export(sys.argv[2] if len(sys.argv) > 2 else None)
        print("已导出: %s" % p)
        return
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8848
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print("电费看板: http://127.0.0.1:%d" % port)
    print("数据源  : %s" % DB_PATH)
    sys.stdout.flush()
    srv.serve_forever()


if __name__ == "__main__":
    main()
