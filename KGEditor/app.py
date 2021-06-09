from flask import Flask, render_template, request, jsonify, session
from oc_ocdm.graph import GraphSet
from oc_ocdm.prov import ProvSet
from oc_ocdm.graph.graph_entity import GraphEntity
from oc_ocdm import Storer
from oc_ocdm.support import create_date
from SPARQLWrapper import SPARQLWrapper, JSON, RDFXML
from rdflib import URIRef, XSD
from rdflib.term import _toPythonMapping
import json
from inspect import signature


app = Flask(__name__)
app.config["SECRET_KEY"] = b'\x94R\x06?\xa4!+\xaa\xae\xb2\xf3Z\xb4\xb7\xab\xf8'
endpoint = "http://localhost:9999/blazegraph/sparql"
base_iri = "https://github.com/arcangelo7/time_agnostic/"
info_dir_graph = "./data/info_dir/graph/"
info_dir_prov = "./data/info_dir/prov/"
graphset = GraphSet(base_iri=base_iri, info_dir=info_dir_graph, wanted_label=False)
with open('KGEditor/static/config/config.json', 'r') as f:
    config = json.load(f)
update_query = dict()

def _hack_dates() -> None:
    if XSD.gYear in _toPythonMapping:
        _toPythonMapping.pop(XSD.gYear)
    if XSD.gYearMonth in _toPythonMapping:
        _toPythonMapping.pop(XSD.gYearMonth)

def get_entity_type(base_iri:str, res:str) -> str:
    type_of_entity = res.replace(base_iri, "").split("/")[0]
    type_of_entity = str(GraphEntity.short_name_to_type_iri[type_of_entity])
    return type_of_entity

def get_entity_from_res(
        res:URIRef, res_type:str, resp_agent:str, 
        endpoint:str = endpoint, graphset:GraphSet = graphset, config:dict = config) -> GraphEntity:
    sparql = SPARQLWrapper(endpoint)
    query = f"""
        CONSTRUCT {{<{res}> ?p ?o}}
        WHERE {{<{res}> ?p ?o}}
    """
    sparql.setQuery(query)
    sparql.setReturnFormat(RDFXML)
    graph = sparql.query().convert()
    entity = getattr(graphset, config[res_type]["add"])(resp_agent=resp_agent, res=res, preexisting_graph=graph)
    return entity

def save_create_query(subj:str, predicate:str, obj:str, resp_agent:str,  
        base_iri:str=base_iri, config:dict=config
    ) -> None:
    s_entity_type = get_entity_type(base_iri=base_iri, res=subj)
    s_entity = get_entity_from_res(res=URIRef(subj), res_type=s_entity_type, resp_agent=resp_agent)
    method_name = config[s_entity_type][predicate]["create"]
    if (isinstance(method_name, dict)):
        if predicate == "http://www.essepuntato.it/2010/06/literalreification/hasLiteralValue":
            identifier_scheme = s_entity.get_scheme()
            method_name = method_name[str(identifier_scheme)]
        else:
            method_name = method_name[obj]
    if predicate == "http://prismstandard.org/namespaces/basic/2.0/publicationDate":
        obj_list = obj.split("-")
        integer_map = map(int, obj_list)
        integer_list = list(integer_map)
        iso_date_string = create_date(integer_list)
        obj = iso_date_string
    sig = signature(getattr(s_entity, method_name))
    params_number = len(sig.parameters)
    if params_number > 0 and base_iri in obj:
        o_entity_type = get_entity_type(base_iri, obj)
        o_entity = get_entity_from_res(res=URIRef(obj), res_type=o_entity_type, resp_agent=resp_agent)
        update_query[subj+predicate+obj] = {
            "s_entity": s_entity,
            "method_name": method_name,
            "o_entity": o_entity
        }
    elif params_number > 0 and "http" in obj: # e.g. for types
        update_query[subj+predicate+obj] = {
            "s_entity": s_entity,
            "method_name": method_name,
            "o_entity": URIRef(obj)
        }
    elif params_number == 0: # e.g. create_digital_embodiment, create_journal_article, create_publisher
        update_query[subj+predicate+obj] = {
            "s_entity": s_entity,
            "method_name": method_name,
            "o_entity": ""
        }
    else:
        update_query[subj+predicate+obj] = {
            "s_entity": s_entity,
            "method_name": method_name,
            "o_entity": obj
        }

def save_delete_query(
        subj:str, predicate:str, obj:str, resp_agent:str,
        base_iri:str=base_iri, config:dict=config
    ) -> None:
    s_entity_type = get_entity_type(base_iri=base_iri, res=subj)
    s_entity = get_entity_from_res(res=URIRef(subj), res_type=s_entity_type, resp_agent=resp_agent)
    method_name = config[s_entity_type][predicate]["delete"]
    sig = signature(getattr(s_entity, method_name))
    params_number = len(sig.parameters)
    if params_number > 0 and base_iri in obj:
        o_entity_type = get_entity_type(base_iri, obj)
        o_entity = get_entity_from_res(res=URIRef(obj), res_type=o_entity_type, resp_agent=resp_agent)
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

def decode_html(string:str) -> str:
    map = {
        '&': '&#38;',
        '<': '&#60;',
        '>': '&#62;',
        '"': '&#34;',
        "'": '&#039;',
        "/": "&#47;"
    }
    decoded_string = "".join([map[char] if char in map else char for char in string])
    return decoded_string

_hack_dates()

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
        for triple_incoming in response_incoming["results"]["bindings"]:
            triple_incoming["subject"]["value"] = decode_html(triple_incoming["subject"]["value"])
            triple_incoming["predicate"]["value"] = decode_html(triple_incoming["predicate"]["value"])
            triple_incoming["object"]["value"] = decode_html(triple_incoming["object"]["value"])
        for triple_outgoing in response_outgoing["results"]["bindings"]:
            triple_outgoing["subject"]["value"] = decode_html(triple_outgoing["subject"]["value"])
            triple_outgoing["predicate"]["value"] = decode_html(triple_outgoing["predicate"]["value"])
            triple_outgoing["object"]["value"] = decode_html(triple_outgoing["object"]["value"])
        res = decode_html(res)
        global base_iri
        base_iri = decode_html(base_iri)
    except Exception as e:
        app.logger.error('Something went wrong')
        print(e)
    return render_template("entity.jinja2", res=res, response_outgoing=response_outgoing, response_incoming=response_incoming, baseUri=base_iri)

@app.route("/create")
def create():
    s = request.args.get("triple[s]", None).strip()
    p = request.args.get("triple[p]", None).strip()
    o = request.args.get("triple[o]", None).strip()
    save_create_query(subj=s, predicate=p, obj=o, resp_agent=session["resp_agent"])
    return jsonify({"result": "Successful creation"})

@app.route("/update")
def update():
    prev_s = request.args.get("prev_triple[s]", None).strip()
    prev_p = request.args.get("prev_triple[p]", None).strip()
    prev_o = request.args.get("prev_triple[o]", None).strip()
    new_s = request.args.get("new_triple[s]", None).strip()
    new_p = request.args.get("new_triple[p]", None).strip()
    new_o = request.args.get("new_triple[o]", None).strip()
    save_delete_query(subj=prev_s, predicate=prev_p, obj=prev_o, resp_agent=session["resp_agent"])
    save_create_query(subj=new_s, predicate=new_p, obj=new_o, resp_agent=session["resp_agent"])
    return jsonify({"result": "Successful update"})

@app.route("/delete")
def delete():
    s = request.args.get("triple[s]", None).strip()
    p = request.args.get("triple[p]", None).strip()
    o = request.args.get("triple[o]", None).strip()
    save_delete_query(subj=s, predicate=p, obj=o, resp_agent=session["resp_agent"])
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
    global update_query
    global graphset
    print(update_query)
    for _, v in update_query.items():
        if v["o_entity"] != "":
            getattr(v["s_entity"], v["method_name"])(v["o_entity"])
        else:
            getattr(v["s_entity"], v["method_name"])()
    provset = ProvSet(prov_subj_graph_set=graphset, base_iri=base_iri, info_dir=info_dir_prov, wanted_label=False)
    provset.generate_provenance()
    storer_graph = Storer(graphset)
    storer_prov = Storer(provset)
    storer_graph.upload_all(endpoint)
    storer_prov.upload_all(endpoint)
    graphset.commit_changes()
    update_query = {}
    return jsonify({"result": "Successful upload"})

@app.route("/saveRA")
def save_resp_agent():
    resp_agent = request.args.get("resp_agent", None)
    session["resp_agent"] = resp_agent
    return jsonify({"result": "Successful authentication"})

@app.route("/getRA")
def get_resp_agent():
    if "resp_agent"  in session:
        return jsonify({"result": session["resp_agent"]})
    else:
        return jsonify({"result": ""})

if __name__ == "__main__":
    app.run(debug=True)
