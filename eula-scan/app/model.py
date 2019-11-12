import sqlite3
import json
from sqlalchemy import create_engine
from sqlalchemy.pool import SingletonThreadPool
import time

eng = create_engine("sqlite:////home/ubuntu/ml-law/eula-scan/TOS.sqlite", poolclass=SingletonThreadPool)


def _ex(statement, params=None):
    c=eng.connect()
    if not params:
        to_ret = c.execute(statement)
    else:
        to_ret = c.execute(statement, params)
    c.close()
    return to_ret


def list_companies():
    return list(map(dict, _ex("SELECT * FROM company")))


def lookup_TOS(company_id, start_time=None):
    if not start_time:
        start_time = time.time()
    tos = _ex("""
        SELECT * FROM tos_text WHERE start_date < ? AND company_id = ?
            ORDER BY start_date desc limit 1
        """,
        (start_time, company_id, )
        ).fetchone()
    if not tos:
        return None
    return {
        "text": tos.text,
        "formatted_text": tos.formatted_text,
    }


def lookup_URL(company_id, ):
    return _ex("SELECT url FROM company WHERE id=?", (company_id,)).fetchone()[0]


def lookup_company(company_id):
    company = dict(_ex("SELECT * FROM company WHERE id=?", (company_id, )).fetchone())
    terms = list(map(dict,
        _ex(
            "SELECT * FROM tos_text WHERE company_id=? ORDER BY start_date desc",
            (company_id, )
        ).fetchall()
    ))
    company['settings'] = (
        json.loads(company['settings'])
        if company['settings'] else None
    )
    return {
        "company": company,
        "terms": terms,
    }

def create_company(name, url, settings, ):
    _ex(
        'INSERT INTO company(name, url, settings) VALUES (?,?,?)',
        (name, url, json.dumps(settings, )))
    id = _ex(
        "select id from company WHERE name=? and url=?",
        (name, url)).fetchone()[0]
    return id


def update_company(company_id, name, url, settings):
    _ex("""
        UPDATE company
        SET name=?, url=?, settings=?, last_error=null
        WHERE id=?
        """,
        (name, url, json.dumps(settings), company_id))
    return _ex("SELECT * FROM company WHERE id=?", (company_id, )).fetchone().id

def flag_company_error(company_id, error_message):
    _ex("UPDATE company SET last_error=?, status=? WHERE id=?",
        (int(time.time()), error_message, company_id))
    return _ex("SELECT * FROM company WHERE id=?", (company_id, )).fetchone().id

def update_last_scan(company_id, last_scan=None, ):
    if not last_scan:
        last_scan = time.time()
    _ex('UPDATE company SET last_scan=? WHERE id=?', (last_scan, company_id))
    return _ex("SELECT * FROM company WHERE id=?", (company_id, )).fetchone().id

def add_TOS(company_id, text, formatted_text, current_time, ):
    last_tos = _ex(
        """SELECT * FROM tos_text WHERE company_id=? ORDER BY start_date DESC""",
        (company_id, )
    ).fetchone()
    _ex("""INSERT INTO tos_text(
                company_id, start_date, text, formatted_text)
            VALUES (?,?,?,?)
        """, (company_id, current_time, text, formatted_text,))


##################
## SETUP HELPER ##
##################

def __setup():
    _ex("""drop table if exists company""")
    _ex("""drop table if exists tos_text""")
    _ex("""
    CREATE TABLE IF NOT EXISTS company(
        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        url TEXT,
        name TEXT,
        last_scan INT,
        last_error INT,
        settings TEXT,
        status TEXT
    )
    """)

    _ex("""
    CREATE TABLE IF NOT EXISTS tos_text(
        id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
        company_id INT,
        start_date INT,
        text BLOB,
        formatted_text BLOB,
    )
    """)
    _ex("""
    CREATE INDEX IF NOT EXISTS tos_text_company_idx ON tos_text(company_id)
    """)
    id_ = create_company("STEIN TEST LOCAL", "http://0.0.0.0:8999/www", {})
    scan_company_tos(id_)
