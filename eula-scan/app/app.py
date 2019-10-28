from flask import (
  Flask,
  render_template,
  jsonify,
  request,
  redirect,
)
import difflib
import json
from cacheout import Cache
from helpers import (
  cleanup_terms_instance,
  demo_scan,
  scan_company_tos,
)
from model import (
  add_TOS,
  create_company,
  list_companies,
  lookup_company,
  lookup_TOS,
  lookup_URL,
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
      terms=[
        cleanup_terms_instance(t, company_info['company']['settings'])
        for t in company_info['terms']
        ],
      )

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
  data = json.loads(request.data)
  return json.dumps(demo_scan(data['url']).get("text"))

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


@app.template_filter()
def timestamp_formatter(ts):
  if not ts:
    return ts
  return datetime.datetime.fromtimestamp(ts).strftime(
    "%B %d, %Y, (%Y-%m-%d %H:%M:%S)"
    )


@app.context_processor
def add_context_vars():
  def make_diff(a, b):
    return difflib.HtmlDiff(
        #wrapcolumn=80
      ).make_table(
        a.split('\n'), b.split('\n'),
        "new", "old", True, 2
      )
  return dict(
    make_diff=cache.memoize()(make_diff)
  )

if __name__ == '__main__':
    app.run(debug=True)
