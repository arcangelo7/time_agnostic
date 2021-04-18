from flask import Flask, render_template, request, redirect, url_for, jsonify
from SPARQLWrapper import SPARQLWrapper, POST, DIGEST, JSON, RDFXML
from SPARQLWrapper.SPARQLExceptions import QueryBadFormed
from rdflib import Graph, URIRef
import json, urllib

app = Flask(__name__)

endpoint = "http://localhost:9999/bigdata/sparql"
baseUri = "https://github.com/arcangelo7/time_agnostic/"
update_string = ""

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
            return jsonify({'results': 'error'})
    else:
        return jsonify({'results': 'error'})

@app.route("/entity/<path:res>")
def entity(res):
    query_outgoing = f"""
        CONSTRUCT {{<{res}> ?p ?o}}
        WHERE {{
            <{res}> ?p ?o
        }}
    """
    query_incoming = f"""
        CONSTRUCT {{?s ?p <{res}>}}
        WHERE {{
            ?s ?p <{res}>
        }}        
    """
    sparql = SPARQLWrapper(endpoint)
    try:
        sparql.setQuery(query_outgoing)
        sparql.setReturnFormat(JSON)
        response_outgoing = sparql.query().convert()
        sparql.setQuery(query_incoming)
        sparql.setReturnFormat(JSON)
        response_incoming = sparql.query().convert()
    except Exception as e:
        app.logger.error('Something went wrong')
    return render_template("entity.jinja2", res=res, response_outgoing=response_outgoing, response_incoming=response_incoming, baseUri=baseUri)


@app.route("/delete")
def delete():
    global update_string
    s = request.args.get("triple[s]", None)
    p = request.args.get("triple[p]", None)
    o = request.args.get("triple[o]", None)
    update_string += f"""
            DELETE 
            {{ 
                <{s}> <{p}> <{o}>.
            }}
            WHERE {{
                <{s}> <{p}> <{o}>.
            }}
        """
    return jsonify({'results': 'error'})

@app.route("/done", methods=["POST"])
def done():
    global update_string
    res = request.form.get("res")
    sparql = SPARQLWrapper(endpoint)
    sparql.setQuery(update_string)
    sparql.setMethod(POST)
    results = sparql.query()
    update_string = ""
    return redirect(url_for("entity", res=res))

if __name__ == "__main__":
    app.run(debug=True)
