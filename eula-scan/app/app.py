from flask import (
  Flask,
  render_template,
  jsonify,
  request,
  redirect,
  make_response,
)
import io
import csv
import difflib
import json
from cacheout import Cache
from helpers import (
  demo_scan,
  scan_company_tos,
)
from model import (
    add_TOS,
    create_company,
    get_companies,
    list_companies,
    lookup_company,
    lookup_TOS,
    lookup_next_TOS,
    lookup_URL,
    number_of_companies,
    update_company,
)
import datetime

app = Flask(__name__)#, static_folder="", templates_folder="")
cache = Cache(ttl=60)

#####################################
## Browsing and exploring the data ##
#####################################

@app.route("/")
def overview():
    """ list all companies """
    return render_template("index.tmpl.html")

@app.route("/company_list")
def company_list_json():
    """ list all companies """
    return jsonify(list_companies())

# date range: start_date < target, end_date > target OR NOT end_date

@app.route("/ajaxTableEndpoint")
def ajax_table_endpoint():
    params = json.loads(request.args.get('params'))
    size = params.get('size', 25)
    page = params.get('page', 1)
    sorters = params.get('sorters', [])
    filters = params.get('filters', [])
    data = get_companies(size, page, sorters, filters)
    return jsonify({
        "last_page": 1 + number_of_companies() // size,
        "data": data,
        "srt": sorters,
        "f": filters,
        "p": page,
        "s": size,
    })

@app.route("/changes")
def change_browser():
    """ list all companies and the isolated deltas for a selected range """
    raise NotImplemented("TODO")

@app.route("/changes/all/<fromdate>/<todate>")
def delta_list(fromdate, todate):
    """ return the deltas of all companies in a date range """
    raise NotImplemented("TODO")

@app.route("/changes/<id>/<fromdate>/<todate>")
def company_delta(id, fromdate, todate):
    """ return the delta of a company for a selected in a date range """
    raise NotImplemented("TODO")


@app.route("/company/<id>")
def company_view(id):
    """ show company, all available updates, and a delta viewer."""
    company_info = lookup_company(id)
    return render_template(
      "company_view.tmpl.html",
      company_info=company_info['company'],
      terms=company_info['terms'],
      )

@app.route("/company/<id>/delta/<timestamp>")
def get_company_delta(id, timestamp):
    company_info = lookup_company
    current_terms = lookup_next_TOS(id, timestamp)
    a = current_terms['text']
    previous_terms = lookup_TOS(id, current_terms['timestamp'])
    b = previous_terms and previous_terms['text']
    if a and b:
        table = difflib.HtmlDiff().make_table(
            a.split('\n'), b.split('\n'),
            "new", "old", True, 2
          )
        count = len(difflib.HtmlDiff(
          ).make_table(
            a.split('\n'), b.split('\n'),
            "new", "old", True, 0
          ).split("/tr")) - 2
    else:
        table = a or b
        count = 0
    return jsonify(dict(
        current_terms=current_terms,
        previous_terms=previous_terms,
        count=count,
        table=table,
        ts=timestamp,
        company_id=id
    ))

@app.route("/company/<id>/edit")
def update_company_view(id):
    """ the form that goes withthe update_company"""
    company_info = lookup_company(id)['company']
    print(company_info)
    return render_template(
      "new_company.tmpl.html",
      companyinfo=company_info)

@app.route("/company/<id>/update", methods=["POST"])
def update_company_submit(id):
    id=update_company(id,
      request.form['name'], request.form['tos_url'], {
      "filter_start": request.form['filter_start'],
      "filter_end": request.form['filter_end'],
    })
    return redirect("/company/{}".format(id), code=302)

@app.route("/company/<id>/force_scan")
def company_force_scan(id):
    change_detected = scan_company_tos(id)
    return redirect("/company/{}".format(id), code=302)

@app.route("/preview", methods=["POST"])
def preview():
  try:
      data = json.loads(request.data)
      return json.dumps(demo_scan(data['url']).get("text"))
  except Exception as e:
      return json.dumps(str(e))


@app.route("/company/new")
def create_company_view():
    """ the form that goes with the new company"""
    return render_template("new_company.tmpl.html")

@app.route("/company/new/submit", methods=["POST"])
def create_company_submit():
    """ the form that goes with the new company"""
    id=create_company(request.form['name'], request.form['tos_url'], {
      "filter_start": request.form['filter_start'],
      "filter_end": request.form['filter_end'],
    })
    return redirect("/company/{}".format(id), code=302)

@app.route('/download_company_list')
def download_company_list():
    companies = list_companies()
    si = io.StringIO()
    cw = csv.DictWriter(si, fieldnames=companies[0].keys())
    cw.writerows(companies)
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=company_list_{}.csv".format(
        datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%Sutc")
    )
    output.headers["Content-type"] = "text/csv"
    return output


@app.template_filter()
def timestamp_formatter(ts):
  if not ts:
    return ts
  return datetime.datetime.fromtimestamp(ts).strftime(
    "%B %d, %Y, (%Y-%m-%d %H:%M:%S)"
    )


@app.context_processor
def add_context_vars():
  @cache.memoize()
  def make_diff(a, b):
    return difflib.HtmlDiff(
        #wrapcolumn=80
      ).make_table(
        a.split('\n'), b.split('\n'),
        "new", "old", True, 2
      )
  def size_diff(a, b):
    diff = difflib.HtmlDiff(
      ).make_table(
        a.split('\n'), b.split('\n'),
        "new", "old", True, 0
      )
    return len(diff.split("/tr")) - 2
  return dict(
    make_diff=make_diff,
    size_diff=size_diff,
  )

if __name__ == '__main__':
    app.run(debug=False)
