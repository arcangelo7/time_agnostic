from flask import Flask, render_template, request, redirect, url_for, jsonify
from SPARQLWrapper import SPARQLWrapper, JSON, RDFXML
from SPARQLWrapper.SPARQLExceptions import QueryBadFormed
from rdflib import Graph, URIRef
import json, urllib

app = Flask(__name__)

endpoint = "http://localhost:9999/bigdata/sparql"

@app.route("/")
def home():
    return render_template("home.jinja2")

@app.route("/sparql")
def sparql():
    query = request.args.get('query', None)
    if query:
        sparql = SPARQLWrapper(endpoint)
        sparql.setQuery(query)
        sparql.setReturnFormat(JSON)
        try:
            response = sparql.query().convert()
            return jsonify(response)
        except Exception as e:
            app.logger.error('Something went wrong')
    else:
        return jsonify({'result': 'Error'})

@app.route("/entity/<path:res>")
def entity(res):
    query = f"""
        CONSTRUCT {{<{res}> ?p ?o}}
        WHERE {{
            <{res}> ?p ?o
        }}
    """
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(query)
    sparql.setReturnFormat(RDFXML)
    try:
        response = sparql.query().convert()
    except Exception as e:
        app.logger.error('Something went wrong')
    return render_template("entity.jinja2", res=res)

if __name__ == "__main__":
    app.run(debug=True)
