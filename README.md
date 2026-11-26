# 宿舍电费监控

查宿舍还剩多少电 —— 本地网页看板 + 低电量微信提醒。

**不需要登录完美校园账号**，不用模拟器，不用一直抓包，也不装任何第三方库。

> 本仓库基于 [jialiangh/campus-electricity-monitor](https://github.com/jialiangh/campus-electricity-monitor) 改造：
> 原版那套「手机号 + 密码登录」已被整个移除，改成直接调云支付网关，只要知道房间标识就能读数。

---

## 先说清楚适用范围

能用：

- 学校用「完美校园」App 交电费
- 宿舍电表挂在这套系统上（绝大多数是）
- 有一台能常开的电脑（自己的电脑、树莓派、小服务器都行）

不能用：学校走的是老一代 `SWAEServlet` 接口的。那种其实更简单，但本项目没实现。

另外，**有三个参数必须你自己去拿**（学校编号、缴费项目 id、房间标识），
这一步免不了，见下面「准备工作」。

---

## 它长什么样

跑起来是一个本地网页（`http://127.0.0.1:8848`）：

- 顶上一个数字：现在还剩多少度
- 一条曲线：最近电量怎么掉的
- 一排柱子：每天用了多少度
- 右上角「⟳ 立即查询」：点一下马上实时查一次
- 顺带算好「按现在的用法还能撑几天」

不想开服务的话可以导出一个自带数据的 HTML，双击就能看。

---

## 为什么不用登录

完美校园的「电费缴纳」是一个 H5 页面，它背后调这个网关：

```
POST https://cloudpaygateway.17wanxiao.com/paygateway/smallpaygateway/trade
```

这个网关**不校验登录态**，只认请求体里的三个参数：

| 参数 | 含义 |
| --- | --- |
| `schoolcode` | 学校编号 |
| `payproid` | 缴费项目 id（电费是其中一个） |
| `roomverify` | 房间标识，形如 `1-1--1-101` |

给对了就返回这个房间的剩余电量。所以整个项目不需要账号、密码、短信验证、token ——
也就不会过期、不会触发「新设备验证」。

**代价**：`roomverify` 等于这个房间电表的查询钥匙。知道它的人能查这个宿舍还剩多少电
（注意：**只能查，不能扣费也不能充值**）。所以别往群里贴。

---

## 准备工作：拿到三个参数

### 抓包

用浏览器 F12（打开完美校园的 H5 缴费页，看 Network 里对 `cloudpaygateway` 的请求），
或者手机上用 mitmproxy / HttpCanary 之类抓。把那个请求原样看一遍就能找到：

- 请求里的 `customerId` → 填 `schoolcode`
- 电费页请求里的 `payproid` → 填 `cloud.payproid`
- 电费项目的 `businesstype` → 电是 `2`，水是 `1`

### 房间标识

有了前两个，剩下的可以用脚本一级级往下钻：

```bash
python find_room.py zones                        # 列校区
python find_room.py builds 东校区                 # 列该校区楼栋
python find_room.py units 东校区 3号楼             # 列楼层
python find_room.py rooms 东校区 3号楼 虚拟楼层     # 列房间 → roomverify
```

最后一步打印出来的、形如 `1-1--1-101` 的那串，就是 `roomverify`。

> **别一次扫全校。** 房间树有几百个节点，挨个请求会撞限流（站点前面有 WAF）。
> 一定要按 校区 → 楼栋 → 楼层 → 房间 逐级下钻。

---

## 快速开始

```bash
git clone <本仓库地址>
cd campus-electricity-monitor
cp config.example.json config.json
```

不用 `pip install`，Python 3.8+ 自带的库就够（标准库 + sqlite3）。

然后把上面拿到的参数填进 `config.json`：

```json
{
  "schoolcode": "0000",
  "room": { "roomverify": "1-1--1-101", "label": "X号楼 101" },
  "payPro": { "electric": { "name": "用电支出", "businesstype": 2 } },
  "cloud": {
    "api_url": "https://cloudpaygateway.17wanxiao.com/paygateway/smallpaygateway/trade",
    "payproid": "0000",
    "businesstype": "2"
  },
  "threshold_low": 30,
  "alert_window": [8, 23]
}
```

（上面的 `schoolcode` / `payproid` / `roomverify` 全是占位符，必须换成你自己抓到的。）

验证一下能不能读到：

```bash
python electricity_monitor.py now
```

打印出 `xx.x 度 (剩余电量)` 就成功了。

---

## 用起来

### 看板

```bash
python web_server.py
```

浏览器开 `http://127.0.0.1:8848`。页面每 30 分钟自动刷一次；
「⟳ 立即查询」按钮可以手动实时查（有 60 秒冷却，防连点）。

想导出离线快照（数据打包进单文件，发给别人也能看）：

```bash
python web_server.py export
```

### 定时采样

看板不会自己长数据，得定时采一次。

Windows（每天凌晨 4 点）：

```bat
schtasks /Create /TN DianfeiDaily /SC DAILY /ST 04:00 /TR "\"C:\Python312\python.exe\" \"<项目目录>\electricity_monitor.py\" sample" /F
```

Linux / macOS：

```bash
sh install_cron.sh          # 默认装成每天 04:00，路径用 APP 环境变量指定
```

或者干脆让它自己常驻，不依赖系统定时器：

```bash
python electricity_monitor.py run --interval 86400
```

**一天一次够吗？** 够看「每天用几度、还能撑几天」。但想知道一天里哪个时段最费电，
就得采得更密（`--interval 3600` 或 cron 每小时）。

### 低电量提醒（可选）

1. 微信扫码登录 [PushPlus](https://www.pushplus.plus)，复制自己的 token
2. 填进 `config.json` 的 `pushplus_token`

两个参数可调：

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `threshold_low` | `30` | 低于多少度开始提醒 |
| `alert_window` | `[8, 23]` | 允许提醒的时段，`[0,24]` 表示全天 |

> **这里有个坑，踩过**：采样时刻必须落在 `alert_window` 里面。
> 程序在时段外发现低电量时不会推送、也不记账，而是等**下一次采样**落在时段内才补发。
> 如果你每天只在 4 点采一次，却把窗口设成 `[8, 23]`，那提醒**永远发不出去**。
> 一天只采一次的话，直接写 `[0, 24]`。

不填 token 也能跑，只是提醒会写进本地 `outbox/` 目录，没人转发。

---

## 常见问题

**读到的是一堆空数据 / 说找不到缴费项目**
`schoolcode` 或 `payproid` 填错了，重新抓包确认。

**返回 `returncode` 不是 SUCCESS**
看返回里的 `returnmsg`。多半是 `roomverify` 不对（房间可能被合并、改名、删了），
用 `find_room.py` 重新查一遍。

**能不能也查水费？**
能。水是另一个 `payproid`，`businesstype` 填 `1`，单位是吨，链路完全一样。

**请求 404 / 连接被拒？**
网关走标准 `443` 端口，别手工加 `:18443` 之类的端口号。

**看板打不开？**
`python web_server.py` 那个窗口要一直开着；服务不会开机自启，需要时手动跑一次。

---

## 文件说明

| 文件 | 作用 |
| --- | --- |
| `cloud_gateway.py` | 网关取数的底层封装 |
| `electricity_monitor.py` | 采样、统计、提醒的主程序 |
| `web_server.py` + `web/index.html` | 本地看板 |
| `find_room.py` | 查房间树，找 `roomverify` |
| `qq_push.py` | 没配 PushPlus 时把提醒落到本地 outbox |
| `daemon.py` | Windows 下单实例守护，防止重复采样 |
| `backfill.py` | 补某个时间点的历史样本 |
| `tests/` | 自检脚本，不联网不真推送 |
| `docs/接口说明.md` | 逆向笔记（含已废弃的登录链路，仅供对照） |

---

## 统计口径

- **用电量 = 相邻两次读数的差值**。读数变小 = 用了电，变大 = 充了钱。
- **充值不算用电**：读数上升会单独记，并重新武装低电量提醒。
- **跨时段按时间比例摊**：两次读数隔了 6 小时又跨过零点，这 6 小时的用电按比例分到两天，
  不然每天第一笔会被错记到前一天。

---

## 隐私与免责

- `roomverify` 当密码对待。`.gitignore` 已排除 `config.json`、数据库、日志和导出快照，
  提交前还是自己扫一眼 `git status`。
- 仓库里的示例参数（`schoolcode` / `payproid` / `roomverify` / 房号）**全是占位符**，
  别把自己的真值填进 `config.example.json`，只填 `config.json`。
- 这是**非官方**实现，靠逆向得到。学校或厂商随时可能改协议，改了就得重新适配。
- 只查你自己的宿舍，别拿它扫整栋楼。
- 仅供学习和方便自己生活，请遵守学校相关规定。

---

## 致谢

- 原始项目：[jialiangh/campus-electricity-monitor](https://github.com/jialiangh/campus-electricity-monitor)（MIT）
- 免登录思路参考：[cyqmq/astrbot_plugin_wanmei_dorm_power](https://github.com/cyqmq/astrbot_plugin_wanmei_dorm_power)

## License

MIT，见 [LICENSE](LICENSE)。

> AI生成
