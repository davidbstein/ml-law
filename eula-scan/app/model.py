import sqlite3
import json
from sqlalchemy import (
    create_engine,
    MetaData,
    select,
    func,
    )
import time

_db_uri = json.load(open("/home/ubuntu/passwords.json"))['DB_URI']
_eng = create_engine(_db_uri)
_meta = MetaData()
_meta.reflect(bind=_eng)
_COMPANY = _meta.tables['company']
_TOS = _meta.tables['tos_text']

def _ex(statement, params=None):
    _c = _eng.connect()
    if not params:
        to_ret = _c.execute(statement)
    else:
        to_ret = _c.execute(statement, *params)
    return to_ret


def list_companies():
    return list(map(dict, _ex(_COMPANY.select())))


def number_of_companies():
    return _ex(select([func.count(_COMPANY.c.id)])).fetchone().count_1


def _gen_clause(filter):
    if filter['type'] == 'like':
        return _COMPANY.c[filter['field']].contains(filter.get("value", ""))

def get_companies(size, page, sorters=None, filters=None):
    query = _COMPANY.select()
    if sorters:
        query = query.order_by(*[
            getattr(_COMPANY.c[sorters[i]['field']], sorters[i]['dir'])().nullslast()
            for i in range(len(sorters))
        ])
    if filters:
        whereclause = _gen_clause(filters[0])
        query = query.where(whereclause)
    resp = _ex(query.limit(size * page))
    holder = [None] * size
    idx = 0
    for r in resp:
        holder[idx] = r
        idx = (idx + 1) % size
    to_ret = []
    for jdx in range(size):
        to_ret.append(dict(holder[(idx+jdx)%size]))
    return to_ret

def lookup_next_TOS(company_id, start_time):
    whereclause = (
        (_TOS.c.company_id == company_id)
        &
        (_TOS.c.start_date >= start_time)
    )
    tos = _ex(
        _TOS.select()
        .where(whereclause)
        .order_by(_TOS.c.start_date.asc())
        .limit(1)
    ).fetchone()
    if not tos:
        return None
    return {
        "tos_id": tos.id,
        "timestamp": tos.start_date,
        "text": tos.text,
    }

def lookup_TOS(company_id, start_time=None):
    if not start_time:
        start_time = time.time()
    whereclause = _TOS.c.company_id == company_id
    if start_time:
        whereclause &= _TOS.c.start_date < start_time
    tos = _ex(
        _TOS.select()
        .where(whereclause)
        .order_by(_TOS.c.start_date.desc())
        .limit(1)
    ).fetchone()
    if not tos:
        return None
    return {
        "text": tos.text,
    }


def lookup_URL(company_id, ):
    return _ex(_COMPANY.select().where(_COMPANY.c.id==company_id)).fetchone().url


def lookup_company(company_id):
    company = dict(_ex(_COMPANY.select().where(_COMPANY.c.id==company_id)).fetchone())
    terms = list(map(dict,
        _ex(
            select([_TOS.c.start_date]).where(_TOS.c.company_id==company_id).order_by(_TOS.c.start_date.desc())
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

def lookup_company_metadata(company_id):
    return dict(_ex(_COMPANY.select().where(_COMPANY.c.id==company_id)).fetchone())

def create_company(name, url, settings, ):
    _ex(_COMPANY.insert().values(
        name=name, url=url, settings=json.dumps(settings,)
    ))
    id = _ex(_COMPANY.select().where(
        (_COMPANY.c.name==name) & (_COMPANY.c.url==url)
    )).fetchone().id
    return id


def update_company(company_id, name, url, settings):
    _ex(_COMPANY.update()
        .where(_COMPANY.c.id==company_id)
        .values(name=name, url=url, settings=json.dumps(settings)))
    return _ex(_COMPANY.select().where(_COMPANY.c.id==company_id)).fetchone().id

def flag_company_error(company_id, error_message):
    _ex(_COMPANY.update()
        .where(_COMPANY.c.id==company_id)
        .values(last_error=int(time.time()), status=error_message)
    )
    return _ex(_COMPANY.select().where(_COMPANY.c.id==company_id)).fetchone().id


def clear_company_error(company_id):
    _ex(_COMPANY.update()
        .where(_COMPANY.c.id==company_id)
        .values(last_error=None, status=None)
    )
    return _ex(_COMPANY.select().where(_COMPANY.c.id==company_id)).fetchone().id

def update_last_scan(company_id, last_scan=None, ):
    if not last_scan:
        last_scan = time.time()
    _ex(_COMPANY.update().where(_COMPANY.c.id==company_id).values(last_scan=last_scan))
    return _ex(_COMPANY.select().where(_COMPANY.c.id==company_id)).fetchone().id

def update_first_scan(company_id, first_scan):
    _ex(_COMPANY.update().where(_COMPANY.c.id==company_id).values(first_scan=first_scan))
    return _ex(_COMPANY.select().where(_COMPANY.c.id==company_id)).fetchone().id

def add_TOS(company_id, text, current_time, ):
    last_tos = _ex(_TOS.select().where(_TOS.c.company_id==company_id).order_by(_TOS.c.start_date.desc())).fetchone()
    _ex(
        _TOS.insert().values(company_id=company_id, start_date=current_time, text=text)
    )

def backdate_TOS(tos_id, timestamp):
    _ex(_TOS.update().where(_TOS.c.id == tos_id).values(start_date=timestamp))

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
    )
    """)
    _ex("""
    CREATE INDEX IF NOT EXISTS tos_text_company_idx ON tos_text(company_id)
    """)
    id_ = create_company("STEIN TEST LOCAL", "http://0.0.0.0:8999/www", {})
    scan_company_tos(id_)
