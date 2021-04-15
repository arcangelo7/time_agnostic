from flask import Flask, render_template, request, redirect, url_for
from SPARQLWrapper import SPARQLWrapper, JSON, RDFXML
from SPARQLWrapper.SPARQLExceptions import QueryBadFormed
from rdflib import Graph
import json

app = Flask(__name__)

sparql = SPARQLWrapper("http://localhost:9999/bigdata/sparql")
results = {
    "results": list()
}

@app.route("/", methods=["GET", "POST"])
def home():
    if request.method == "POST":
        try:
            query = request.form.get("sparqlQuery")
            sparql.setQuery(query)
            sparql.setReturnFormat(JSON)
            results["results"] = sparql.query().convert()["results"]["bindings"]
            return redirect(url_for("home"))
        except QueryBadFormed:
            return redirect(url_for("home"))
    return render_template("home.jinja2", results=results["results"])

if __name__ == "__main__":
    app.run(debug=True)
