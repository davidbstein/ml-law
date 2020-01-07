import bs4
import datetime
import difflib
import logging
import json
import re
import requests
import string
import time
logger = logging.getLogger()

from model import (
    add_TOS,
    backdate_TOS,
    create_company,
    flag_company_error,
    list_companies,
    lookup_company,
    lookup_TOS,
    lookup_URL,
    lookup_next_TOS,
    update_company,
    update_last_scan
)

import threading
_lock = threading.RLock()

def demo_scan(url):
    return _pull_TOS(url)

def scan_company_tos(company_id, prefix="", lock=_lock):
    url = lookup_URL(company_id)
    try:
        tos = _pull_TOS(url)
    except Exception as e:
        logger.debug("{} - HANDING ERROR...".format(prefix))
        with lock:
            flag_company_error(company_id, "In attempting to download the link, got the following error \n{}: {}".format(type(e), e))
        logger.debug("{} - ...DONE".format(prefix))
        return False
    logger.debug("{} - saving...".format(prefix))
    with lock:
        if ("TERMS OF SERVICE" not in tos.get("text").upper()) and ("PRIVACY POLICY" not in tos.get("text").upper()):
            flag_company_error(company_id, "contents do not appear to be a TOS, EULA, or Privacy Policy. Please check URL")
        lookup_TOS(company_id)
        update_result = _do_update_check(company_id, new_tos=tos)
        update_last_scan(company_id)
    if not update_result['new']:
        return False
    else:
        with lock:
            add_TOS(
                company_id,
                update_result["text"],
                int(time.time())
            )
        return True

def _apply_settings(s, settings):
    if not settings:
        return s
    if settings.get("filter_start"):
        s = s.partition(settings.get("filter_start"))[2]
    if settings.get("filter_end"):
        s = s.rpartition(settings.get("filter_end"))[0]
    return s


def _diff_test(a, b, settings):
    a = _apply_settings(a, settings)
    b = _apply_settings(b, settings)
    changes = list(difflib.context_diff(
        a.split('\n'),b.split('\n'), n=0
    ))
    logger.debug('\n'.join(changes)[:1000])
    return len(changes) == 0


def _is_text(txt):
    code_phrases = (
        "if(",
        "()", 
        "};", 
        "!)",
        "<%",
        "%>",
        "<!--",
        "-->",
        "Log InSign Up",
        'Log in',
        'Sign in',
        'add to cart',
    )
    opening_phrases = (
        "window.",
        "document.",
        "margin-",
        "text-",
        "color: #",
        "Sorry, there was a problem loading this page",
        "Please enable JavaScript",
        'add to cart',
        'Log in',
        'Sign in',
    )
    if not txt:
        return False
    if sum(ch in txt for ch in "{};=") > 2:
        return False
    if any(s in txt for s in code_phrases):
        return False
    if any(txt.upper().startswith(s.upper()) for s in opening_phrases):
        return False
    return True


def _clean_text(txt):
    paragraphs = txt.split("~~~")
    to_ret = []
    for p in paragraphs:
        p = p.strip()
        p = ' '.join(p.split())
        if not _is_text(p):
            continue
        to_ret.append("")
        if len(p.split()) > 10:
            to_ret.extend("{}.".format(s) for s in p.split('. '))
            if not p.endswith('.'):
                to_ret[0] = to_ret[0][:-1]
        else:
            to_ret.append(p)
    return "\n".join(to_ret)

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.14; rv:70.0) Gecko/20100101 Firefox/70.0",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Pragma": "no-cache",
    "Cache-Control": "no-cache"
}
def _pull_TOS(url):
    for count in range(3):
        try:
            r = requests.get(url, timeout=10, headers=_HEADERS)
        except Exception as e:
            logger.debug("retrying")
            time.sleep(10)
            if count >= 2:
                raise e
            continue
        break
    if r.status_code != 200:
        return {
            #"error": r.text,
            "code": r.status_code,
            "url": url,
        }
    page_text = (r.text.replace("<p>", "~~~")
        .replace("<P>", "~~~")
        .replace("<br>", "~~~")
        .replace("<BR>", "~~~") 
        .replace("<br/>", "~~~")
        .replace("<BR/>", "~~~")
        .replace("<!-- END WAYBACK TOOLBAR INSERT -->", "~WAYBACK~"))
    page_text = re.sub(r'http://web.archive.org/web/\d+/', "", page_text)
    soup = bs4.BeautifulSoup(page_text, features="html5lib")
    text = _clean_text(soup.body.text.split("~WAYBACK~")[-1])
    return {
        "text": text,
    }

def _do_update_check(company_id, new_tos=None):
    old_tos = lookup_TOS(company_id)
    company = lookup_company(company_id)
    if not new_tos:
        new_tos = _pull_TOS(company['company']['url'])
    if old_tos:
        if _diff_test(
            old_tos['text'],
            new_tos['text'],
            company['company']['settings']):
            return {
                "text": new_tos["text"],
                "new": False,
            }
        else:
            return {
                "text": new_tos["text"],
                "new": True,
            }
    else:
        return {
            "text": new_tos["text"],
            "new": True
        }

def _is_english(txt, threshold=.7):
    if "This translation is provided for convenience only and the English language version will control in the event of any discrepancies." in txt:
        return False
    if "This banner text can have markup." in txt:
        return False
    words = set(open("/usr/share/dict/words").read().upper().split())
    word_list = (txt.upper()
        .translate(str.maketrans('', '', string.punctuation))
        .translate(str.maketrans('', '', string.digits))
        .split()
    )
    if not len(word_list):
        return False
    return sum(w in words for w in word_list) / len(word_list) > threshold    


def _process_archived_TOS(company_row, archive_object):
    current_pull = _pull_TOS("http://web.archive.org/web/{timestamp}/{original}".format(**archive_object))
    if not 'text' in current_pull:
        logger.error("======\nerror: {}\n{}".format(json.dumps(current_pull, indent='  '), json.dumps(archive_object, indent='  ')))
        return 0
    if not _is_english(current_pull['text']):
        logger.debug("not english")
        logger.debug(current_pull['text'][:40])
        return 0
    timestamp = int(datetime.datetime.strptime(archive_object['timestamp'], "%Y%m%d%H%M%S").timestamp())
    next_pull = lookup_next_TOS(company_row['id'], timestamp)
    unchanged = next_pull and _diff_test(current_pull['text'], next_pull['text'], json.loads(company_row['settings']))
    if not unchanged:
        logger.debug("changed") # add new row
        add_TOS(company_row["id"], current_pull['text'], timestamp)
        return 1
    if unchanged:
        logger.debug("unchanged") # back up timestamp
        backdate_TOS(next_pull['tos_id'], timestamp)
        return 0


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
        try:
            output = r.json()
        except Exception as e:
            logger.error('http://web.archive.org/cdx/search/cdx -- ' + company_row['url'])
            raise e
        keys = output[0]
        end_idx = None
        if output[-2] == []:
            query_string['resumeKey'] = output[-1][0]
            end_idx = -2
        all_rows.extend(dict(zip(keys, oo)) for oo in output[1:end_idx])
        if output[-2] != []:
            break
    return all_rows


def pull_company_from_wayback_machine(company_id, latest=None):
    company_row = model.lookup_company_metadata(143)
    archive_rows = helpers._enumerate_company_archive(company_row)
    for ar in reversed(archive_rows):
        logger.debug('scanning {}'.format(ar['timestamp']))
        _process_archived_TOS(company_row, ar)
