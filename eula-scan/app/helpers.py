import bs4
import difflib
import requests
import time

from .model import (
    add_TOS,
    create_company,
    list_companies,
    lookup_diff,
    lookup_TOS,
    lookup_URL,
    update_company,
)


def demo_scan(url):
    return _pull_TOS(url)


def scan_company_tos(company_id):
    url = lookup_URL(company_id)
    tos = _pull_TOS(url)
    lookup_TOS(company_id)
    update_result = _do_update_check(company_id)
    if not update_result:
        print("no change")
        pass # nullop
    else:
        add_TOS(
            company_id,
            update_result["text"],
            update_result["formatted_text"],
            update_result.get("delta"),
            update_result.get("formatted_delta"),
            int(time.time())
       )
    # TODO: log error and update status to show most recent error


def _iterative_diff_function(a, b):
    difflib._check_types(a, b, '','','','','\n')
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(lambda x: x==' ',a,b).get_opcodes():
        if tag == "equal":
            yield (tag, a[i1:i2])
        if tag == "delete":
            yield (tag, a[i1:i2])
        if tag == "insert":
            yield (tag, b[j1:j2])
        if tag == "replace":
            yield (tag, a[i1:i2], b[j1:j2])


def _diff_function(a, b):
    return list(iterative_diff_function(a, b))


def _pull_TOS(url):
    r = requests.get(url, timeout=10)
    assert r.status_code == 200, 'error, code: ' + r.status_code
    soup = bs4.BeautifulSoup(r.text)
    return {
        "text": soup.body.text,  #"\n\n".join(p.text for p in ps),
        "formatted_text": str(soup.body),     #"\n\n".join(str(p) for p in ps),
    }


def _do_update_check(company_id):
    old_tos = lookup_TOS(company_id)
    url = lookup_URL(company_id)
    new_tos = pull_TOS(url)
    if old_tos:
        text_diff = _diff_function(
            old_tos['text'],
            new_tos['text'],
        )
        format_diff = _diff_function(
            old_tos['formatted_text'],
            new_tos['formatted_text'],
        )
        if len(text_diff) == len(format_diff) == 1:
            if (text_diff[0][0] == format_diff[0][0] == "equal"):
                return None
        return {
            "text": new_tos["text"],
            "formatted_text": new_tos["formatted_text"],
            "delta": text_diff,
            "formatted_delta": format_diff,
            "new": False,
        }
    else:
        return {
            "text": new_tos["text"],
            "formatted_text": new_tos["formatted_text"],
            "new": True
        }
