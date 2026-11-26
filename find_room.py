# -*- coding: utf-8 -*-
"""房间树浏览助手（免登录，走云支付网关）。

用法:
  python find_room.py zones                       # 列校区
  python find_room.py builds <校区关键字>          # 列该校区楼栋
  python find_room.py units <校区> <楼栋>          # 列单元/楼层
  python find_room.py rooms <校区> <楼栋> <楼层>   # 列房间
  python find_room.py find <楼栋关键字> <房间号>   # 全区扫描定位房间
"""
import sys

import cloud_gateway as gw
import electricity_monitor as em

CFG = em.CFG
CLOUD = CFG["cloud"]


def level(optype, areaid="0", buildid="0", unitid="0", levelid="0"):
    return gw.rooms(CLOUD["api_url"], CFG["schoolcode"], CLOUD["payproid"],
                    CLOUD.get("businesstype") or "2", optype,
                    areaid=areaid, buildid=buildid, unitid=unitid, levelid=levelid)


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "zones"

    if cmd == "zones":
        for c in level(1):
            print("areaid=%s  %s" % (c.get("id"), c.get("name")))

    elif cmd == "builds":
        kw = sys.argv[2] if len(sys.argv) > 2 else ""
        for c in level(1):
            if kw and kw not in str(c.get("name")):
                continue
            for b in level(2, areaid=c["id"]):
                print("campus=%s  buildid=%s  %s" % (c.get("name"), b.get("id"), b.get("name")))

    elif cmd == "units":
        ck, bk = sys.argv[2], sys.argv[3]
        for c in level(1):
            if ck not in str(c.get("name")):
                continue
            for b in level(2, areaid=c["id"]):
                if bk not in str(b.get("name")):
                    continue
                for u in level(3, areaid=c["id"], buildid=b["id"]):
                    print("levelid=%s  %s" % (u.get("id"), u.get("name")))

    elif cmd == "rooms":
        ck, bk, uk = sys.argv[2], sys.argv[3], sys.argv[4]
        for c in level(1):
            if ck not in str(c.get("name")):
                continue
            for b in level(2, areaid=c["id"]):
                if bk not in str(b.get("name")):
                    continue
                for u in level(3, areaid=c["id"], buildid=b["id"]):
                    if uk not in str(u.get("name")):
                        continue
                    for r in level(4, areaid=c["id"], buildid=b["id"], levelid=u["id"]):
                        print("roomverify=%s  %s" % (r.get("id"), r.get("name")))

    elif cmd == "find":
        bk = sys.argv[2] if len(sys.argv) > 2 else ""
        rk = sys.argv[3] if len(sys.argv) > 3 else ""
        for c in level(1):
            for b in level(2, areaid=c["id"]):
                if bk and bk not in str(b.get("name")):
                    continue
                for u in level(3, areaid=c["id"], buildid=b["id"]):
                    for r in level(4, areaid=c["id"], buildid=b["id"], levelid=u["id"]):
                        if rk and rk not in str(r.get("name")):
                            continue
                        print("%s | %s | %s | %s | %s"
                              % (c.get("name"), b.get("name"), u.get("name"),
                                 r.get("name"), r.get("id")))
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
