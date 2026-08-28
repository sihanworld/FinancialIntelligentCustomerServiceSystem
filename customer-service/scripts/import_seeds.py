"""导入 FAQ / 知识库种子数据（seeds/*.csv -> cs_faq / cs_knowledge_doc）"""
import csv
import logging
from pathlib import Path

import pymysql

from init_cs_db import load_env, parse_db_url, ROOT

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    env = load_env()
    conf = parse_db_url(env["CS_DATABASE_URL"])
    db_name = conf.pop("db")
    conn = pymysql.connect(**conf, database=db_name, autocommit=True)
    try:
        with conn.cursor() as cur:
            # FAQ
            cur.execute("DELETE FROM cs_faq")
            with open(ROOT / "seeds" / "cs_faq.csv", encoding="utf-8-sig") as f:
                rows = list(csv.DictReader(f))
            for row in rows:
                cur.execute(
                    "INSERT INTO cs_faq (category, question, answer, keywords, sort_no, status) VALUES (%s,%s,%s,%s,%s,'active')",
                    (row["category"], row["question"], row["answer"], row["keywords"], int(row.get("sort_no") or 1)),
                )
            logger.info(f"导入 FAQ {len(rows)} 条")

            # 知识库文档
            cur.execute("DELETE FROM cs_knowledge_doc")
            with open(ROOT / "seeds" / "cs_knowledge_doc.csv", encoding="utf-8-sig") as f:
                docs = list(csv.DictReader(f))
            for doc in docs:
                cur.execute(
                    "INSERT INTO cs_knowledge_doc (category, title, content, keywords, status) VALUES (%s,%s,%s,%s,'active')",
                    (doc["category"], doc["title"], doc["content"], doc["keywords"]),
                )
            logger.info(f"导入知识库文档 {len(docs)} 条")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
