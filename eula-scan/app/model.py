import sqlite3
import json
from sqlalchemy import create_engine
c = sqlite3.connect('TOS.sqlite')

eng = create_engine("sqlite:///Users/stein/repos/ml-law/eula-scan/TOS.sqlite")
c = eng.connect()


def list_companies():
    company_list = c.execute("select * from company")
    to_ret = []
    for c in company_list:
        to_ret.append({
            "id": c[0],
            "url": c[1],
            "name": c[2],
            "last_scan": c[3],
            "last_error": c[4],
            "scan_instructions": c[5],
            "status": c[6],
        })
    return to_ret


def lookup_diff(company_id, start_time, end_time=None):
    first_diff = c.execute("""
        select * from tos_text
        where start_date < ?
        and company_id = ?
        order by start_date desc limit 1
        """,
        (start_time, company_id, )
        ).fetchone()
    if end_time == None:
        return first_diff.delta
    second_diff = c.execute("""
        select * from tos_text
        where start_date < ?
        and company_id = ?
        order by start_date desc limit 1
        """,
        (start_time, company_id, )
        )
    if first_diff == second_diff:
        return first_diff.delta


def lookup_URL(company_id):
    return c.execute("select url from company where id=?", (company_id,)).fetchone()[0]


def lookup_TOS(company_id):
    last_tos = c.execute("""
        select text, formatted_text from tos_text where company_id=?
        order by start_date desc
        """, (company_id,)
    ).fetchone()
    if not last_tos:
        return None
    else:
        return {
            "text": last_tos[0],
            "formatted_text": last_tos[1],
        }


def create_company(name, url, settings):
    c.execute('INSERT INTO company(name, url) VALUES (?,?)', (name, url))
    id = c.execute("select id from company where name=? and url=?", (name, url)).fetchone()[0]
    return id


def update_company(company_id, url=None, name=None, scan_instructions=None):
    if url:
        c.execute("update company where id=? set url=?", (company_id, url))
    if name:
        c.execute("update company where id=? set name=?", (company_id, name))
    if scan_instructions:
        c.execute(
            "update company where id=? set scan_instructions=?",
            (company_id, json.dumps(scan_instructions))
        )
    return c.execute("select * from company where id=?", (company_id, )).fetchone()


def _update_last_scan(id, last_scan=None):
    c.execute('UPDATE company SET last_scan=? WHERE id=?', (last_scan, id))


def _update_last_error(company_id, error_time, dt):
    c.execute('UPDATE company SET last_error=? WHERE id=?', (error_time, id))


def add_TOS(company_id, text, formatted_text, delta, formatted_delta, current_time):
    last_tos = c.execute(
        """SELECT * FROM tos_text WHERE company_id=? ORDER BY start_date DESC""",
        (company_id, )
    ).fetchone()
    if last_tos:
        c.execute(
            """UPDATE tos_text SET end_date=? WHERE id=?""",
            (current_time, last_tos.id,)
        )
        c.commit()
    c.execute(
        """
        INSERT INTO tos_text(
            company_id, start_date, text, formatted_text, delta, formatted_delta
            )
        VALUES (?,?,?,?,?,?)
        """,
        (
            company_id,
            current_time,
            text,
            formatted_text,
            json.dumps(delta),
            json.dumps(formatted_delta)
        )
    )
    c.commit()



##################
## SETUP HELPER ##
##################

def __setup():
    c.execute("""drop table if exists company""")
    c.execute("""drop table if exists tos_text""")
    c.execute("""
    CREATE TABLE IF NOT EXISTS company(
        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        url TEXT,
        name TEXT,
        last_scan INT,
        last_error INT,
        scan_instructions TEXT,
        status TEXT
    )
    """)

    c.execute("""
    CREATE TABLE IF NOT EXISTS tos_text(
        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        company_id INT,
        start_date INT,
        end_date INT,
        text BLOB,
        formatted_text BLOB,
        delta BLOB,
        formatted_delta BLOB
    )
    """)
    c.execute("""
    CREATE INDEX IF NOT EXISTS tos_text_company_idx ON tos_text(company_id)
    """)
    c.commit()
    id_ = create_company("STEIN TEST LOCAL", "http://0.0.0.0:8999/www", {})
    scan_company_tos(id_)
