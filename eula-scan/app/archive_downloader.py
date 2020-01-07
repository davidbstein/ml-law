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
logger.setLevel(logging.WARN)
#logger.setLevel(logging.CRITICAL)
local_logger = logging.getLogger('script')

from pymemcache.client.base import Client
mc = Client(('localhost', 11211))


def get_company_archive(company_row, earliest_ts=0):
    archive_rows = helpers._enumerate_company_archive(company_row)
    formatted_earliest = datetime.datetime.fromtimestamp(earliest_ts).strftime("%Y%m%d%H%M%S")
    return [ar for ar in archive_rows if ar['timestamp'] > formatted_earliest]

def clear_all_tos(company_id):
    model._ex("delete from tos_text where company_id={}".format(company_id))

def pull_history(company_id, earliest_ts=0):
    start_time = int(time.time())
    company_row = model.lookup_company_metadata(company_id)
    archive_rows = get_company_archive(company_row, earliest_ts=earliest_ts)
    n=len(archive_rows)
    count = 0
    for i, ar in enumerate(reversed(archive_rows)):
        logger.warning("{}/{}".format(i,n))
        logger.info(ar['timestamp'])
        count += helpers._process_archived_TOS(company_row, ar)

def fix_repeats(company_id):
    while True:
        rows = model._ex(
            "select * from tos_text where company_id={} order by start_date desc".format(
                company_id)
        ).fetchall()
        changes = 0
        print(len(rows))
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
        print("break")
        break

        
def get_oldest_companies(limit=100):
    for r in model._ex(C_TABLE.select().order_by(C_TABLE.c.last_scan).limit(limit)):
        yield r
        
def run_company_update(company):
    pull_history(company.id, earliest_ts=company.last_scan)
    fix_repeats(company.id)
    helpers.scan_company_tos(company.id)
    model.update_last_scan(company.id)

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
        print("active threads: {}\t elapsed time: {}\tqueue size: {}".format(
            threading.active_count() - base_threads,
            str(datetime.timedelta(seconds=int(time.time()-start))),
            q.qsize()
        ))
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
    print("THREAD TERMINATED")
    

def old_main():
    print(model._ex("select max(id) from company").fetchone())
    q = queue.Queue()
    count_thread = threading.Thread(target=counter, args=(q,))
    count_thread.start()

    LIMIT = 500
    THREAD_COUNT = 35  
    
    id_list = []
    dataset_table = model._meta.tables['polisis_dataset'];
    for r in model._ex(dataset_table.select().where(dataset_table.c.status==3).limit(LIMIT)):
        i = model.create_company(
            name="Polisis Dataset - {}".format(r.company_url), url=r.policy_url, settings={}
        )
        model._ex("update polisis_dataset set status=4 where id={}".format(r.id))
        q.put(i)
        id_list.append(i)

    threads = []
    for _ in range(THREAD_COUNT):
        threads.append(threading.Thread(target=scanner, kwargs={"q":q}))
        threads[-1].start()
    
    for thread in threads:
        thread.join()
    killer.put(1)
    print("DONE")
    count_thread.join()

