import model
import helpers

import requests
import datetime
import json
import time
import threading
import queue

import logging

logger = logging.getLogger()
ch = logging.StreamHandler()
ch.setFormatter(logging.Formatter(
    '\u001b[36m[%(threadName)s]\u001b[0m %(asctime)s - %(levelname)s - %(message)s'
))
logger.addHandler(ch)
logger.setLevel(logging.WARNING)
#logger.setLevel(logging.CRITICAL)
local_logger = logging.getLogger('script')

from pymemcache.client.base import Client
mc = Client(('localhost', 11211))


def get_week(timestamp):
    week = datetime.datetime.strptime(timestamp[:8], "%Y%m%d").isocalendar()
    #return "{}-{}-{}".format(week[0], week[1], week[2]//4)
    return "{}-{}".format(week[0], week[1])

def get_company_archive(company_row, earliest_ts=0, sleepmin=30, sleepmax=120):
    try:
        archive_rows = helpers._enumerate_company_archive(company_row)
    except:
        print("sleeping")
        import random
        time.sleep(random.randint(sleepmin, sleepmax))
        archive_rows = helpers._enumerate_company_archive(company_row)
    formatted_earliest = datetime.datetime.fromtimestamp(earliest_ts).strftime("%Y%m%d%H%M%S")
    filtered_ar = [ar for ar in archive_rows if ar['timestamp'] > formatted_earliest]
    if not filtered_ar:
        return []
    to_ret = [filtered_ar[0]]
    cur = filtered_ar[0]['timestamp']
    for entry in filtered_ar[1:]:
        if get_week(cur) == get_week(entry['timestamp']):
            continue
        cur = entry['timestamp']
        to_ret.append(entry)
    return to_ret
       
    
def clear_all_tos(company_id):
    model._ex("delete from tos_text where company_id={}".format(company_id))

def pull_history(company_id, earliest_ts=0):
    start_time = int(time.time())
    company_row = model.lookup_company_metadata(company_id)
    archive_rows = get_company_archive(company_row, earliest_ts=earliest_ts)
    n=len(archive_rows)
    count = 0
    for i, ar in enumerate(reversed(archive_rows)):
        if not i%10:
            logger.warning("{} - {}/{}".format(company_id, i,n))
        else:
            logger.info ("{} - {}/{}".format(company_id, i,n))
        logger.info(ar['timestamp'])
        count += helpers._process_archived_TOS(company_row, ar)

def fix_repeats(company_id):
    while True:
        rows = model._ex(
            "select * from tos_text where company_id={} order by start_date desc".format(
                company_id)
        ).fetchall()
        changes = 0
        for a,b,c in zip(rows, rows[1:], rows[2:]):
            if helpers._diff_test(a.text, b.text, {}):
                model._ex("delete from tos_text where id={}".format(a.id))
                changes += 1
            if helpers._diff_test(a.text, c.text, {}):
                model._ex("delete from tos_text where id={}".format(a.id))
                model._ex("delete from tos_text where id={}".format(b.id))
                changes += 1
        if changes:
            print("{} rows removed".format(changes))
            continue
        break


killer = queue.Queue()
def counter(q):
    base_threads = threading.active_count()
    start = time.time()
    print("active threads: {}\t elapsed time: {}\tqueue size: {}".format(
        threading.active_count() - base_threads,
        str(datetime.timedelta(seconds=int(time.time()-start))),
        q.qsize()
    ))
    while killer.empty():
        time.sleep(5)
        active_threads = threading.active_count() - base_threads
        print("active threads: {}\t elapsed time: {}\tqueue size: {}".format(
            active_threads,
            str(datetime.timedelta(seconds=int(time.time()-start))),
            q.qsize()
        ))
#         if active_threads < 5:
#             logger.setLevel(logging.INFO)
        if active_threads == 0:
            break
    print("dead!")

def scan_company(c_id):
    clear_all_tos(c_id)
    pull_history(c_id)
    fix_repeats(c_id)

def scanner(q):
    while not q.empty():
        try:
            company_id = q.get_nowait()
            scan_company(company_id)
            model.update_last_scan(company_id)
        except:
            import traceback
            logging.warn(traceback.format_exc())
            model.flag_company_error(company_id, "integrety check not performed")
    logger.warn("THREAD TERMINATED")
    
        
def get_oldest_companies(limit=100):
    query = (
        model._COMPANY.select()
        .where((model._COMPANY.c.last_scan < time.time() - (60 * 60 * 24)) & 
               (model._COMPANY.c.last_error < time.time() - (60 * 60 * 24)) &
               (model._COMPANY.c.last_scan != None))
        .order_by(model._COMPANY.c.last_scan)
        .limit(limit)
    )
    for r in model._ex(query):
        yield r

                
def get_unscanned_companies(limit=100):
    query = (
        model._COMPANY.select()
        .where((model._COMPANY.c.last_scan == None) &
               (model._COMPANY.c.last_error < time.time() - (60 * 60 * 24)) &
               (model._COMPANY.c.last_error == None))
        .order_by(model._COMPANY.c.alexa_rank)
        .limit(limit)
    )
    for r in model._ex(query):
        yield r
                
def get_top_companies(limit=100):
    query = (
        model._COMPANY.select()
        .where((
        (
            (model._COMPANY.c.last_scan < time.time() - (60 * 60 * 24 * 7)) &
            (model._COMPANY.c.last_error < time.time() - (60 * 60 * 24 * 7)) 
        ) |
        ((model._COMPANY.c.last_scan == None) & (model._COMPANY.c.last_error == None))
        ) & (model._COMPANY.c.alexa_rank < 50000))
        .order_by(model._COMPANY.c.alexa_rank)
        .limit(limit)
    )
    for r in model._ex(query):
        yield r


def recompute_company_update_count(company):
    rows = model._ex(
        model._TOS.select().where(model._TOS.c.company_id==company.id).order_by(model._TOS.c.start_date)
    ).fetchall()
    rowcount = len(rows)
    model._ex(
        model._COMPANY.update().where(model._COMPANY.c.id==company.id).values(
            changes_recorded=rowcount, 
            first_scan=min(company.first_scan, 
                           rows[0].start_date or time.time(), 
                           rows[-1].start_date or time.time())
        )
    )
    return rowcount


def run_company_update(company):
    pull_history(company.id, earliest_ts=(company.last_scan or 0))
    fix_repeats(company.id)
    helpers.scan_company_tos(company.id)
    model.update_last_scan(company.id)
    recompute_company_update_count(company)
    logger.warning("complete: {} - {}".format(company.id, company.name))

def updater(q):
    while not q.empty():
        try:
            company = q.get_nowait()
            logger.warn("{} - {} -- http://eula-scan.davidbstein.com/company/{}".format(company.alexa_rank, company.name, company.id))
            run_company_update(company)
        except:
            import traceback
            logging.error(traceback.format_exc())
            model.flag_company_error(company.id, "integrety check not performed")
    logger.warn("THREAD TERMINATED")
    
def updater_main(limit, thread_count):
    q = queue.Queue()
    count_thread = threading.Thread(target=counter, args=(q,))
    count_thread.start()
    
    skip_ids = set()
    for c in get_top_companies(limit=limit):
        if c.id not in skip_ids:
            q.put(c)
            skip_ids.add(c.id)
    for c in get_oldest_companies(limit=limit//5):
        if c.id not in skip_ids:
            q.put(c)
            skip_ids.add(c.id)
    for c in get_unscanned_companies(limit=limit//10):
        if c.id not in skip_ids:
            q.put(c)
            skip_ids.add(c.id)
    print(skip_ids)
    threads = []
    for _ in range(thread_count):
        threads.append(threading.Thread(target=updater, kwargs={"q":q}))
        threads[-1].start()
        time.sleep(5)

    for thread in threads:
        thread.join()
    killer.put(1)
    print("DONE")
    count_thread.join()

"""
def scanner_main():
    print(model._ex("select max(id) from company").fetchone())
    q = queue.Queue()
    count_thread = threading.Thread(target=counter, args=(q,))
    count_thread.start()
    
    dataset_table = model._meta.tables['polisis_dataset'];
    for r in model._ex(dataset_table.select().where(dataset_table.c.status==3).limit(LIMIT)):
        i = model.create_company(
            name="Polisis Dataset - {}".format(r.company_url), url=r.policy_url, settings={}
        )
        model._ex("update polisis_dataset set status=4 where id={}".format(r.id))
        q.put(i)

    threads = []
    for _ in range(THREAD_COUNT):
        threads.append(threading.Thread(target=scanner, kwargs={"q":q}))
        threads[-1].start()
    
    for thread in threads:
        thread.join()
    killer.put(1)
    print("DONE")
    count_thread.join()
"""
# count number of changes per entry
def updates_per_company():
    rows = model._ex("select count(*) as c, company_id from tos_text group by company_id")
    counts = {r.company_id: r.c for r in rows}
    for company_id, count in counts.items():
        model._ex(model._COMPANY.update().where(model._COMPANY.c.id==company_id).values(changes_recorded=count))

if __name__ == '__main__':
    LIMIT = 500
    THREAD_COUNT = 40

    updater_main(LIMIT, THREAD_COUNT)
    updates_per_company()
