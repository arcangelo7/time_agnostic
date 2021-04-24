from flask import Flask, render_template, request, redirect, url_for, jsonify
from oc_ocdm.graph import GraphSet
from oc_ocdm.graph.graph_entity import GraphEntity
from oc_ocdm import Storer
from oc_ocdm.graph.entities.bibliographic.bibliographic_resource import BibliographicResource
from SPARQLWrapper import SPARQLWrapper, POST, DIGEST, JSON, RDFXML
from SPARQLWrapper.SPARQLExceptions import QueryBadFormed
from rdflib import Graph, URIRef
import json, urllib, oc_ocdm.graph.entities as entities
from inspect import signature

app = Flask(__name__)

endpoint = "http://localhost:9999/blazegraph/sparql"
base_iri = "https://github.com/arcangelo7/time_agnostic/"
info_dir = "./data/info_dir/graph/"
resp_agent = "https://orcid.org/0000-0002-8420-0696"
graphset = GraphSet(base_iri=base_iri, info_dir=info_dir, wanted_label=False)
with open('KGEditor\static\config\config.json', 'r') as f:
    config = json.load(f)
update_query = dict()

def get_entity_type(base_iri:str, res:str) -> str:
    type_of_entity = res.replace(base_iri, "").split("/")[0]
    type_of_entity = str(GraphEntity.short_name_to_type_iri[type_of_entity])
    return type_of_entity

def get_entity_from_res(
        endpoint:str, res:URIRef, res_type:str, 
        resp_agent:str, graphset:GraphSet, config:dict) -> GraphEntity:
    sparql = SPARQLWrapper(endpoint)
    query = f"""
        CONSTRUCT {{<{res}> ?p ?o}}
        WHERE {{<{res}> ?p ?o}}
    """
    sparql.setQuery(query)
    sparql.setReturnFormat(RDFXML)
    data = sparql.query().convert()
    graph = Graph().parse(data=data.serialize(format='xml'), format='xml')
    entity = getattr(graphset, config[res_type]["add"])(resp_agent=resp_agent, res=res, preexisting_graph=graph)
    return entity

def save_create_query(subj:str, predicate:str, obj:str, base_iri:str=base_iri, 
        endpoint:str=endpoint, resp_agent:str=resp_agent, graphset:GraphSet=graphset, config:dict=config
    ) -> None:
    s_entity_type = get_entity_type(base_iri=base_iri, res=subj)
    s_entity = get_entity_from_res(
        endpoint=endpoint, res=URIRef(subj), res_type=s_entity_type, 
        resp_agent=resp_agent, graphset=graphset, config=config)
    method_name = config[s_entity_type][predicate]["create"]
    sig = signature(getattr(s_entity, method_name))
    params_number = len(sig.parameters)
    if params_number > 0:
        o_entity_type = get_entity_type(base_iri, obj)
        o_entity = get_entity_from_res(
            endpoint=endpoint, res=URIRef(obj), res_type=o_entity_type, 
            resp_agent=resp_agent, graphset=graphset, config=config)
        update_query[subj+predicate+obj] = {
            "s_entity": s_entity,
            "method_name": method_name,
            "o_entity": o_entity
        }
    else:
        update_query[subj+predicate+obj] = {
            "s_entity": s_entity,
            "method_name": method_name,
            "o_entity": ""
        }

def save_update_query(
        subj:str, predicate:str, obj:str, base_iri:str=base_iri, 
        endpoint:str=endpoint, resp_agent:str=resp_agent, graphset:GraphSet=graphset, config:dict=config
    ) -> None:
    save_delete_query(subj, predicate, obj)
    save_create_query(subj, predicate, obj)

def save_delete_query(
        subj:str, predicate:str, obj:str, base_iri:str=base_iri, 
        endpoint:str=endpoint, resp_agent:str=resp_agent, graphset:GraphSet=graphset, config:dict=config
    ) -> None:
    s_entity_type = get_entity_type(base_iri=base_iri, res=subj)
    s_entity = get_entity_from_res(
        endpoint=endpoint, res=URIRef(subj), res_type=s_entity_type, 
        resp_agent=resp_agent, graphset=graphset, config=config)
    method_name = config[s_entity_type][predicate]["delete"]
    sig = signature(getattr(s_entity, method_name))
    params_number = len(sig.parameters)
    if params_number > 0:
        o_entity_type = get_entity_type(base_iri, obj)
        o_entity = get_entity_from_res(
            endpoint=endpoint, res=URIRef(obj), res_type=o_entity_type, 
            resp_agent=resp_agent, graphset=graphset, config=config)
        update_query[subj+predicate+obj] = {
            "s_entity": s_entity,
            "method_name": method_name,
            "o_entity": o_entity
        }
    else:
        update_query[subj+predicate+obj] = {
            "s_entity": s_entity,
            "method_name": method_name,
            "o_entity": ""
        }

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
    return render_template("entity.jinja2", res=res, response_outgoing=response_outgoing, response_incoming=response_incoming, baseUri=base_iri)

@app.route("/create")
def create():
    return jsonify({"result": "Successful creation"})

@app.route("/update")
def update():
    s = request.args.get("triple[s]", None)
    p = request.args.get("triple[p]", None)
    o = request.args.get("triple[o]", None)
    save_delete_query(subj=s, predicate=p, obj=o)
    save_create_query(subj=s, predicate=p, obj=o)
    return jsonify({"result": update_query})

@app.route("/delete")
def delete():
    s = request.args.get("triple[s]", None)
    p = request.args.get("triple[p]", None)
    o = request.args.get("triple[o]", None)
    save_delete_query(subj=s, predicate=p, obj=o)
    return jsonify({"result": "Successful delete"})

@app.route("/undo")
def undo():
    s = request.args.get("triple[s]", None)
    p = request.args.get("triple[p]", None)
    o = request.args.get("triple[o]", None)
    update_query.pop(s+p+o, None)
    return jsonify({"result": "Successful undo"})

@app.route("/done")
def done():
    for k, v in update_query.items():
        if v["o_entity"] != "":
            getattr(v["s_entity"], v["method_name"])(v["o_entity"])
        else:
            getattr(v["s_entity"], v["method_name"])()
    storer = Storer(graphset)
    storer.upload_all(endpoint)
    return jsonify({"result": "Successful upload"})

if __name__ == "__main__":
    app.run(debug=True)
