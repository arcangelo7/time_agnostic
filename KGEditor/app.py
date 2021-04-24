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

class Crud(object):
    def __init__(self, graphset:GraphSet, subj:str, predicate:str, obj:str, endpoint:str, base_iri:str, resp_agent:str):
        self.subj = subj
        self.predicate = predicate
        self.obj = obj
        self.endpoint = endpoint
        self.base_iri = base_iri
        self.resp_agent = resp_agent
        self.add_methods = {
            "http://purl.org/spar/datacite/Identifier": graphset.add_id,
            "http://purl.org/spar/pro/RoleInTime": graphset.add_ar,
            "http://purl.org/spar/biro/BibliographicReference": graphset.add_be,
            "http://purl.org/spar/fabio/Expression": graphset.add_br,
            "http://purl.org/spar/cito/Citation": graphset.add_ci,
            "http://purl.org/spar/fabio/Manifestation": graphset.add_re,
            "http://xmlns.com/foaf/0.1/Agent": graphset.add_ra
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
        s_entity = self._get_entity_from_res(self.endpoint, URIRef(self.subj), s_entity_type, self.resp_agent)
        removal_methods = {
            "http://purl.org/spar/pro/RoleInTime": {
                "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": "remove_type",
                "https://w3id.org/oc/ontology/hasNext": "remove_next",
                "http://purl.org/spar/pro/isHeldBy": "remove_is_held_by",
                "http://purl.org/spar/pro/withRole": "remove_role_type"
            },
            "http://purl.org/spar/biro/BibliographicReference": {
                "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": "remove_type",
                "http://purl.org/spar/c4o/hasContent": "remove_content",
                "http://purl.org/spar/biro/references": "remove_referenced_br"
            },
            "http://purl.org/spar/fabio/Expression": {
                "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": "remove_type",
                "http://purl.org/spar/datacite/hasIdentifier": "remove_identifier",
                "http://purl.org/dc/terms/title": "remove_title",
                "http://purl.org/spar/fabio/hasSubtitle": "remove_subtitle",
                "http://purl.org/vocab/frbr/core#partOf": "remove_is_part_of",
                "http://purl.org/spar/cito/cites": "remove_citation",
                "http://prismstandard.org/namespaces/basic/2.0/publicationDate": "remove_pub_date",
                "http://purl.org/vocab/frbr/core#embodiment": "remove_format",
                "http://purl.org/spar/fabio/hasSequenceIdentifier": "remove_number",
                "http://purl.org/vocab/frbr/core#part": "remove_contained_in_reference_list",
                "http://purl.org/spar/pro/isDocumentContextFor": "remove_contributor"
            },
            "http://purl.org/spar/cito/Citation": {
                "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": "remove_type",
                "http://purl.org/spar/cito/hasCitingEntity": "remove_citing_entity",
                "http://purl.org/spar/cito/hasCitedEntity": "remove_cited_entity",
                "http://purl.org/spar/cito/hasCitationCreationDate": "remove_citation_creation_date",
                "http://purl.org/spar/cito/hasCitationTimeSpan": "remove_citation_time_span"
            },
            "http://purl.org/spar/fabio/Manifestation": {
                "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": "remove_type",
                "http://purl.org/dc/terms/format": "remove_media_type",
                "http://prismstandard.org/namespaces/basic/2.0/startingPage": "remove_starting_page",
                "http://prismstandard.org/namespaces/basic/2.0/endingPage": "remove_ending_page",
                "http://purl.org/vocab/frbr/core#exemplar": "remove_url"
            },
            "http://xmlns.com/foaf/0.1/Agent": {
                "http://www.w3.org/1999/02/22-rdf-syntax-ns#type": "remove_type",
                "http://xmlns.com/foaf/0.1/name": "remove_name",
                "http://xmlns.com/foaf/0.1/givenName": "remove_given_name",
                "http://xmlns.com/foaf/0.1/familyName": "remove_family_name"
            }
        }
        method_name = removal_methods[s_entity_type][self.predicate]
        sig = signature(getattr(s_entity, method_name))
        params_number = len(sig.parameters)
        if params_number > 0:
            o_entity_type = self._get_entity_type(self.base_iri, self.obj)
            o_entity = self._get_entity_from_res(self.endpoint, URIRef(self.obj), o_entity_type, self.resp_agent)
            getattr(s_entity, method_name)(o_entity)
        else:
            getattr(s_entity, method_name)()

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
    crud = Crud(graphset, s, p, o, endpoint, base_iri, resp_agent)
    crud.delete()
    return jsonify({"result": "Successful delete"})

@app.route("/done")
def done():
    brs = graphset.get_br()
    storer = Storer(graphset)
    storer.upload_all(endpoint)
    return jsonify({"result": "Successful upload"})

if __name__ == "__main__":
    app.run(debug=True)
