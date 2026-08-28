"""初始化客服库：从 .env 的 CS_DATABASE_URL 解析连接参数，建库并执行 sql/customer_service.sql"""
import logging
import re
from pathlib import Path

import pymysql

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[1]


def load_env() -> dict[str, str]:
    env_file = ROOT / ".env"
    result: dict[str, str] = {}
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            result[key.strip()] = value.strip()
    return result


def parse_db_url(url: str) -> dict:
    m = re.match(r"mysql(?:\+aiomysql)?://(?P<user>[^:]+):(?P<password>[^@]+)@(?P<host>[^:/]+):(?P<port>\d+)/(?P<db>[^?]+)", url)
    if not m:
        raise RuntimeError(f"无法解析 CS_DATABASE_URL: {url}")
    return {
        "host": m.group("host"),
        "port": int(m.group("port")),
        "user": m.group("user"),
        "password": m.group("password"),
        "db": m.group("db"),
    }


def main():
    env = load_env()
    conf = parse_db_url(env["CS_DATABASE_URL"])
    db_name = conf.pop("db")

    conn = pymysql.connect(**conf, autocommit=True)
    try:
        with conn.cursor() as cur:
            cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        logger.info(f"数据库 {db_name} 就绪")
    finally:
        conn.close()

    conn = pymysql.connect(**conf, database=db_name, autocommit=True)
    try:
        sql_text = (ROOT / "sql" / "customer_service.sql").read_text(encoding="utf-8")
        # 先移除注释行，再按分号拆分，避免“注释开头的块”被整体过滤
        cleaned = "\n".join(line for line in sql_text.splitlines() if not line.strip().startswith("--"))
        statements = [s.strip() for s in cleaned.split(";") if s.strip()]
        with conn.cursor() as cur:
            for stmt in statements:
                cur.execute(stmt)
        logger.info(f"已执行 {len(statements)} 条建表语句")
    finally:
        conn.close()
    logger.info("客服库初始化完成")


if __name__ == "__main__":
    main()
