#!/bin/sh
# 装电量监控的定时采样任务。幂等：重复跑只会替换自己的条目，
# 服务器上原有的其它 crontab 条目原样保留。
#
#   sh install_cron.sh              # 每天 04:00 采一次（默认）
#   APP=/opt/electricity-monitor sh install_cron.sh
#
# 想改成每小时：把下面的 "0 4 * * *" 换成 "0 * * * *"。
set -e
APP="${APP:-/opt/electricity-monitor}"
PY="${PY:-/usr/bin/python3}"
command -v flock >/dev/null 2>&1 || { echo "缺少 flock（apt install util-linux）"; exit 1; }
[ -f "$APP/electricity_monitor.py" ] || { echo "没找到 $APP/electricity_monitor.py"; exit 1; }

TMP=$(mktemp)
crontab -l 2>/dev/null | grep -v "$APP" | grep -v "^PYTHONIOENCODING" > "$TMP" || true
cat >> "$TMP" <<EOF
PYTHONIOENCODING=utf-8
0 4 * * * flock -n $APP/.lock $PY $APP/electricity_monitor.py sample >> $APP/monitor.log 2>&1
EOF
crontab "$TMP"
rm -f "$TMP"
echo "=== 当前 crontab ==="
crontab -l
