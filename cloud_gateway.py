# -*- coding: utf-8 -*-
"""云支付网关客户端 —— **不需要登录 token**。

思路来自 cyqmq/astrbot_plugin_wanmei_dorm_power：
宿舍电量挂在「云支付缴费页」的 `/paygateway/smallpaygateway/trade` 接口上，
它只认 学校代码 + 缴费项目ID + 房间ID，不校验用户身份，
所以不用账号密码、不用短信、不用 token，也就不会过期。

三个参数都能在 config.json 里手填，也能用 `python cloud_gateway.py detect <缴费链接>` 自动解析。
"""
import json
import ssl
import sys
import time
import urllib.parse
import urllib.request

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE

UA = ("Mozilla/5.0 (Linux; Android 12; 24031PN0DC Build/V417IR; wv) "
      "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/110.0.5481.154 "
      "Safari/537.36 Wanxiao/5.8.9 Wmxy/5.8.27")
GATEWAY_PATH = "/paygateway/smallpaygateway/trade"


class GatewayError(RuntimeError):
    pass


def call(api_url, method, biz, timeout=20):
    """向云支付网关 POST 一次，返回解析后的 JSON。"""
    base = api_url.rsplit("/paygateway", 1)[0]
    payload = {
        "method": method,
        "bizcontent": json.dumps(biz, ensure_ascii=False),
        "timestamp": time.strftime("%y-%m-%d %H:%M:%S"),
        "sourceId": 2,
    }
    req = urllib.request.Request(
        api_url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Origin": base,
                 "Referer": base + "/pay/index.html",
                 "User-Agent": UA})
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=CTX) as r:
            raw = r.read().decode("utf-8", "replace")
    except Exception as e:
        raise GatewayError("网关请求失败: %r" % (e,))
    try:
        return json.loads(raw)
    except Exception:
        raise GatewayError("网关返回非 JSON: %s" % raw[:160])


def _unwrap(d):
    if str(d.get("returncode")) != "SUCCESS":
        raise GatewayError(d.get("returnmsg") or d.get("subMsg") or "接口返回失败")
    return d.get("businessData")


def room_state(api_url, schoolcode, payproid, businesstype, roomverify):
    """返回 {"quantity": float, "quantityunit": str, "description": str}。"""
    d = _unwrap(call(api_url, "samllProgramGetRoomState", {
        "payproid": str(payproid),
        "schoolcode": str(schoolcode),
        "roomverify": roomverify,
        "businesstype": str(businesstype),
    }))
    if not isinstance(d, dict):
        raise GatewayError("getRoomState 无 businessData: %r" % (d,))
    return d


def rooms(api_url, schoolcode, payproid, businesstype, optype,
          areaid="0", buildid="0", unitid="0", levelid="0"):
    """房间树一层：optype 1 校区 / 2 楼栋 / 3 楼层 / 4 房间。"""
    d = _unwrap(call(api_url, "samllProgramGetRoom", {
        "schoolno": str(schoolcode), "optype": optype, "payproid": str(payproid),
        "areaid": str(areaid), "buildid": str(buildid), "unitid": str(unitid),
        "levelid": str(levelid), "businesstype": str(businesstype), "idserial": "",
    }))
    return d or []


def parse_pay_url(url):
    """从完美校园「缴费页链接」解析出 schoolcode / payproid / businesstype / api_url。"""
    base, _, frag = url.partition("#")
    parsed = urllib.parse.urlparse(base)
    q = urllib.parse.parse_qs(parsed.query)
    schoolcode = ""
    for key in ("customerId", "customercode", "schoolcode", "schoolCode"):
        if q.get(key):
            schoolcode = q[key][0]
            break
    payproid = businesstype = payproname = ""
    if "billDetail" in frag and "?" in frag:
        fq = urllib.parse.parse_qs(frag.split("?", 1)[1])
        item_str = fq.get("item", [""])[0]
        for raw in (urllib.parse.unquote(item_str), item_str):
            try:
                item = json.loads(raw)
            except Exception:
                continue
            if isinstance(item, dict):
                payproid = str(item.get("id") or "")
                businesstype = str(item.get("flag") or "")
                payproname = item.get("payproname") or ""
                break
    return {"schoolcode": schoolcode, "payproid": payproid,
            "businesstype": businesstype, "payproname": payproname,
            "api_url": "https://%s%s" % (parsed.netloc, GATEWAY_PATH)}


def _main():
    if len(sys.argv) < 3:
        print("用法:")
        print("  python cloud_gateway.py detect <缴费页链接>")
        print("  python cloud_gateway.py state <api_url> <schoolcode> <payproid> <businesstype> <roomverify>")
        print("  python cloud_gateway.py tree  <api_url> <schoolcode> <payproid> <businesstype> [optype]")
        return
    cmd = sys.argv[1]
    if cmd == "detect":
        info = parse_pay_url(sys.argv[2])
        print(json.dumps(info, ensure_ascii=False, indent=2))
        if info["schoolcode"] and info["payproid"]:
            areas = rooms(info["api_url"], info["schoolcode"], info["payproid"],
                          info["businesstype"] or "2", 1)
            print("校区:", "、".join(a.get("name", "") for a in areas))
    elif cmd == "state":
        _, api, school, paypro, btype, room = sys.argv
        print(json.dumps(room_state(api, school, paypro, btype, room),
                         ensure_ascii=False, indent=2))
    elif cmd == "tree":
        api, school, paypro, btype = sys.argv[2:6]
        optype = int(sys.argv[6]) if len(sys.argv) > 6 else 1
        for r in rooms(api, school, paypro, btype, optype):
            print(r.get("id"), r.get("name"))


if __name__ == "__main__":
    _main()
