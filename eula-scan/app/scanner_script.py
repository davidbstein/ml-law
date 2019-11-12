from model import (
  list_companies,
)
from helpers import (
  scan_company_tos,
)


def scan_company(id):
  scan_company_tos(id)

def scan_all_companies():
  companies = list_companies()
  for i, company in enumerate(companies):
    print("scanning {} of {}: {}".format(i, len(companies), company.get('name')))
    scan_company(company['id'])

if __name__ == "__main__":
  scan_all_companies()
