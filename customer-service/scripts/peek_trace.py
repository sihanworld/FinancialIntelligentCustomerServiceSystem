import os, json
import pymysql
from pathlib import Path

env = {}
for line in Path(".env").read_text(encoding="utf-8").splitlines():
    if line.strip() and not line.startswith("#") and "=" in line:
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()

import re
m = re.match(r"mysql(?:\+aiomysql)?://([^:]+):([^@]+)@([^:/]+):(\d+)/([^?]+)", env["CS_DATABASE_URL"])
conn = pymysql.connect(host=m.group(3), port=int(m.group(4)), user=m.group(1), password=m.group(2), database=m.group(5), charset="utf8mb4")
with conn.cursor(pymysql.cursors.DictCursor) as cur:
    cur.execute("SELECT sender_id, tracks, plan_json, clarify_reason, flow_id, step_id, status, error_message FROM cs_turn_trace ORDER BY id DESC LIMIT 3")
    for r in cur.fetchall():
        print(json.dumps(r, ensure_ascii=False, default=str))
    cur.execute("SELECT COUNT(*) AS n FROM cs_action_audit")
    print("audit rows:", cur.fetchone())
    cur.execute("SELECT action_name, method, url, biz_code, http_status FROM cs_action_audit ORDER BY id DESC LIMIT 5")
    for r in cur.fetchall():
        print(r)
conn.close()
