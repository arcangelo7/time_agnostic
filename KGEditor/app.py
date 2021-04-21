from flask import Flask, render_template, request, redirect, url_for, jsonify
from oc_ocdm.graph import GraphSet
from oc_ocdm.graph.graph_entity import GraphEntity
from oc_ocdm import Storer
from SPARQLWrapper import SPARQLWrapper, POST, DIGEST, JSON, RDFXML
from SPARQLWrapper.SPARQLExceptions import QueryBadFormed
from rdflib import Graph, URIRef
import json, urllib, oc_ocdm.graph.entities as entities

app = Flask(__name__)

endpoint = "http://localhost:9999/blazegraph/sparql"
base_iri = "https://github.com/arcangelo7/time_agnostic/"
info_dir = "./data/info_dir/graph/"
resp_agent = "https://orcid.org/0000-0002-8420-0696"
graphset = GraphSet(base_iri=base_iri, info_dir=info_dir, wanted_label=False)

class Crud(object):
    def __init__(self, graphset:GraphSet, subj:str, obj:str, endpoint:str, base_iri:str, resp_agent:str):
        self.subj = subj
        self.obj = obj
        self.endpoint = endpoint
        self.base_iri = base_iri
        self.resp_agent = resp_agent
        self.add_methods = {
            "http://purl.org/spar/fabio/Expression": graphset.add_br,
            "http://purl.org/spar/fabio/Manifestation": graphset.add_re,
            "http://purl.org/spar/datacite/Identifier":graphset.add_id
        } 

    def _get_entity_type(self, base_iri:str, res:str) -> str:
        type_of_entity = res.replace(base_iri, "").split("/")[0]
        type_of_entity = str(GraphEntity.short_name_to_type_iri[type_of_entity])
        return type_of_entity

    def _get_entity_from_res(self, endpoint:str, res:URIRef, res_type:str, resp_agent:str):
        sparql = SPARQLWrapper(endpoint)
        query = f"""
            CONSTRUCT {{<{res}> ?p ?o}}
            WHERE {{<{res}> ?p ?o}}
        """
        sparql.setQuery(query)
        sparql.setReturnFormat(RDFXML)
        data = sparql.query().convert()
        graph = Graph().parse(data=data.serialize(format='xml'), format='xml')
        entity = self.add_methods[res_type](resp_agent=resp_agent, res=res, preexisting_graph=graph)
        return entity
    
    def add(self) -> None:
        pass
    
    def delete(self) -> None:
        s_entity_type = self._get_entity_type(self.base_iri, self.subj)
        o_entity_type = self._get_entity_type(self.base_iri, self.obj)
        s_entity = self._get_entity_from_res(self.endpoint, URIRef(self.subj), s_entity_type, self.resp_agent)
        o_entity = self._get_entity_from_res(self.endpoint, URIRef(self.obj), o_entity_type, self.resp_agent)
        removal_methods = {
            "http://purl.org/spar/fabio/Expression": {
                "http://purl.org/spar/datacite/Identifier": s_entity.remove_identifier,
                "http://purl.org/spar/fabio/Manifestation": s_entity.remove_format
            }
        }
        removal_methods[s_entity_type][o_entity_type](o_entity)   

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


@app.route("/delete")
def delete():
    s = request.args.get("triple[s]", None)
    p = request.args.get("triple[p]", None)
    o = request.args.get("triple[o]", None)
    crud = Crud(graphset, s, o, endpoint, base_iri, resp_agent)
    crud.delete()
    return jsonify({"result": "Successful delete"})

@app.route("/done")
def done():
    brs = graphset.get_br()
    storer = Storer(graphset)
    storer.upload_all(endpoint)
    res = request.form.get("res")
    return jsonify({"result": "Successful upload"})

if __name__ == "__main__":
    app.run(debug=True)
