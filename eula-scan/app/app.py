from flask import Flask
import json
app = Flask(__name__)#, static_folder="", templates_folder="")

#####################################
## Browsing and exploring the data ##
#####################################

@app.route("/")
def overview():
    """ list all companies """
    return "overview <pre>" + json.dumps(locals(), indent="  ") + "</pre>"

# date range: start_date < target, end_date > target OR NOT end_date

@app.route("/changes")
def change_browser():
    """ list all companies and the isolated deltas for a selected range """
    return "change <pre>" + json.dumps(locals(), indent="  ") + "</pre>"

@app.route("/changes/all/<fromdate>/<todate>")
def delta_list(fromdate, todate):
    """ return the deltas of all companies in a date range """
    return "delta <pre>" + json.dumps(locals(), indent="  ") + "</pre>"

@app.route("/changes/<id>/<fromdate>/<todate>")
def company_delta(id, fromdate, todate):
    """ return the delta of a company for a selected in a date range """
    return "delta <pre>" + json.dumps(locals(), indent="  ") + "</pre>"

@app.route("/company/<id>")
def company_view(id):
    """ show company, all available updates, and a delta viewer."""
    return "company <pre>" + json.dumps(locals(), indent="  ") + "</pre>"

##############################################################
## Consider merging these and checkign the method in the fn ##
##############################################################

@app.route("/company/<id>/edit", methods=["POST"])
def update_company(id):
    """ update a company's settings """
    return "update <pre>" + json.dumps(locals(), indent="  ") + "</pre>"

@app.route("/company/<id>/edit")
def update_company_view(id):
    """ the form that goes withthe update_company"""
    return "update <pre>" + json.dumps(locals(), indent="  ") + "</pre>"

@app.route("/company/new", methods=["POST"])
def create_company(id):
    """ create a new company """
    return "create <pre>" + json.dumps(locals(), indent="  ") + "</pre>"

@app.route("/company/new")
def create_company_view(id):
    """ the form that goes with the new company"""
    return "create <pre>" + json.dumps(locals(), indent="  ") + "</pre>"



if __name__ == '__main__':
    app.run(debug=True)
