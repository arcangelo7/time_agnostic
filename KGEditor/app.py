from flask import Flask, render_template
from SPARQLWrapper import SPARQLWrapper, JSON, RDFXML
from rdflib import Graph
import json

app = Flask(__name__)

sparql = SPARQLWrapper("http://localhost:9999/bigdata/sparql")
triples_query = """
    SELECT ?s ?p ?o
    WHERE {?s ?p ?o}
    LIMIT 10
"""
sparql.setQuery(triples_query)
sparql.setReturnFormat(JSON)
triples_result = sparql.query().convert()

@app.route("/")
def home():
    return render_template("home.jinja2", triples_result=triples_result)

if __name__ == "__main__":
    app.run(debug=True)
