from model import (
  list_companies,
)
from helpers import (
  scan_company_tos,
)

from multiprocessing import (
  RLock,
  Pool,
)

from multiprocessing.pool import ThreadPool
import threading

def scan_company(id, prefix=None, lock=None):
  scan_company_tos(id, prefix, lock)

def scan_all_companies():
  companies = list_companies()
  for i, company in enumerate(companies):
    print("scanning {} of {}: {}".format(i, len(companies), company.get('name')))
    scan_company(company['id'])

def parallel_scan_all_companies():
  companies = list_companies()
  lock = threading.RLock()
  def scan_company_monad(args):
    i, company = args
    print("scanning {} of {}: {}".format(i, len(companies), company.get('name')))
    return scan_company(company['id'], i, lock)
  with ThreadPool(50) as p:
    p.map(scan_company_monad, enumerate(companies))

if __name__ == "__main__":
  parallel_scan_all_companies()
