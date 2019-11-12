import bs4
import difflib
import requests
import time

from model import (
    add_TOS,
    create_company,
    flag_company_error,
    list_companies,
    lookup_company,
    lookup_TOS,
    lookup_URL,
    update_company,
    update_last_scan
)

def demo_scan(url):
    return _pull_TOS(url)

def scan_company_tos(company_id):
    url = lookup_URL(company_id)
    try:
        tos = _pull_TOS(url)
    except Exception as e:
        print("HANDING ERROR...")
        flag_company_error(company_id, "In attempting to download the link, got the following error \n{}: {}".format(type(e), e))
        return False
    if ("TERMS OF SERVICE" not in tos.get("text").UPPER()) and ("PRIVACY POLICY" not in tos.get("text").UPPER()):
        flag_company_error(company_id, "contents do not appear to be a TOS, EULA, or Privacy Policy. Please check URL")
    lookup_TOS(company_id)
    update_result = _do_update_check(company_id)
    update_last_scan(company_id)
    if not update_result['new']:
        return False
    else:
        add_TOS(
            company_id,
            update_result["text"],
            update_result["formatted_text"],
            int(time.time())
        )
        return True

def cleanup_terms_instance(terms_instance, settings):
    terms_instance['text'] = _apply_settings(terms_instance['text'], settings)
    return terms_instance

def _apply_settings(s, settings):
    if not settings:
        return s
    return (s
        .partition(settings.get("filter_start", ""))[2]
        .rpartition(settings.get("filter_end", ""))[0]
        )

def _diff_test(a, b, settings):
    a = _apply_settings(a, settings)
    b = _apply_settings(b, settings)
    return a == b

def _pull_TOS(url):
    r = requests.get(url, timeout=10)
    assert r.status_code == 200, 'error, code: ' + r.status_code
    soup = bs4.BeautifulSoup(r.text, features="html.parser")
    return {
        "text": soup.body.text,
        "formatted_text": str(soup.body),
    }

def _do_update_check(company_id):
    old_tos = lookup_TOS(company_id)
    company = lookup_company(company_id)
    new_tos = _pull_TOS(company['company']['url'])
    if old_tos:
        if _diff_test(
            old_tos['text'],
            new_tos['text'],
            company['company']['settings']):
            return {
                "text": new_tos["text"],
                "formatted_text": new_tos["formatted_text"],
                "new": False,
            }
        else:
            return {
                "text": new_tos["text"],
                "formatted_text": new_tos["formatted_text"],
                "new": True,
            }
    else:
        return {
            "text": new_tos["text"],
            "formatted_text": new_tos["formatted_text"],
            "new": True
        }
