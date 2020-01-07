from model import (
  list_companies,
    lookup_next_TOS,
    lookup_TOS,
    backdate_TOS,
    add_TOS,
    lookup_company_metadata,
    _ex,
)
from helpers import (
  scan_company_tos,
  _pull_TOS,
  _diff_test,
)
import requests
import time
import datetime
from multiprocessing import (
  RLock,
  Pool,
)

from multiprocessing.pool import ThreadPool
import threading


def _enumerate_company_archive(company_row):
    query_string = {
        "url": company_row['url'],
        "limit": 1000,
        "showResumeKey": "true",
        "output": "json",
        "resumeKey": None,
    }
    all_rows = []
    while True:
        r = requests.get("http://web.archive.org/cdx/search/cdx", params=query_string)
        output = r.json()
        keys = output[0]
        end_idx = None
        if output[-2] == []:
            query_string['resumeKey'] = output[-1][0]
            end_idx = -2
        all_rows.extend(dict(zip(keys, oo)) for oo in output[1:end_idx])
        if output[-2] != []:
            break
    return all_rows

def _add_archived_TOS(company_row, archive_object):
    timestamp = int(datetime.datetime.strptime(archive_object['timestamp'], "%Y%m%d%H%M%S").timestamp())
    print(archive_object['timestamp'])
    next_pull = lookup_next_TOS(company_row['id'], timestamp)
    prev_pull = lookup_TOS(company_row['id'], timestamp)
    if next_pull['timestamp'] == timestamp:
        print("duplicate timestamp")
    current_pull = _pull_TOS("http://web.archive.org/web/{timestamp}/{original}".format(**archive_object))
    unchanged_next = next_pull and _diff_test(current_pull['text'], next_pull['text'], json.loads(company_row['settings']))
    unchanged_prev = prev_pull and _diff_test(current_pull['text'], prev_pull['text'], json.loads(company_row['settings']))
    if unchanged_next:
        print("earlier version of already loaded")
        backdate_TOS(next_pull['tos_id'], timestamp)
    elif unchanged_prev:
        print("no change since last pull")
    else:
        print("changed")
        add_TOS(company_row["id"], current_pull['text'], timestamp)


def pull_company_archive(company_id, start_point=None):
    company_row = lookup_company_metadata(company_id)
    archive_rows = _enumerate_company_archive(company_row)
    for archive_row in archive_rows:
        if start_point and archive_row['timestamp'] < start_point:
            continue
        try:
            _add_archived_TOS(company_row, archive_row)
        except:
            time.sleep(10)
            print("EXCEPTION")
            _add_archived_TOS(company_row, archive_row)
            print("TRUE FAILURE")


def parallel_scan_all_companies():
  companies = _ex("select * from company where last_scan > 0").fetchall()
  lock = threading.RLock()
  def scan_company_monad(args):
    i, company = args
    print("scanning {} of {}: {}".format(i, len(companies), company.name))
    return pull_company_archive(company.id)
  with ThreadPool(5) as p:
    p.map(scan_company_monad, enumerate(c for c in companies if 'PP' in c.name))

if __name__ == "__main__":
  parallel_scan_all_companies()
