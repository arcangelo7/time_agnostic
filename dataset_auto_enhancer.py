import re, rdflib, json, urllib
from support import Support
from dataset_builder import DatasetBuilder
from tqdm import tqdm
from rdflib import URIRef, Namespace, ConjunctiveGraph, Graph, plugin
from rdflib.serializer import Serializer
from rdflib.plugins.sparql.results.jsonresults import JSONResultSerializer
from rdflib.plugins.sparql import prepareQuery
from oc_ocdm.support.query_utils import get_update_query
from datetime import datetime
from oc_ocdm.graph.graph_entity import GraphEntity
from oc_ocdm.graph import GraphSet
from oc_ocdm.prov import ProvSet
from oc_ocdm.reader import Reader
from SPARQLWrapper import SPARQLWrapper, JSON, RDFXML

class DatasetAutoEnhancer(object):
    def __init__(self, base_uri:str, resp_agent:str, info_dir:str=""):
        self.base_iri = base_uri
        self.resp_agent = resp_agent
        self.info_dir = info_dir

    def merge_by_id_from_file(self, entities_set:set, rdf_file_path:str) -> GraphSet:
        enhanced_graphset = Support().get_graph_from_file(rdf_file_path, self.base_iri, self.resp_agent, self.info_dir)        
        switcher = {
            "br": {
                "class": "fabio:Expression",
                "get": enhanced_graphset.get_br
                },
            "ra": {
                "class": "foaf:Agent",
                "get": enhanced_graphset.get_ra
                }
        }
        reader = Reader()
        for entity in entities_set:
            entities = switcher[entity]["get"]()
            ids_found = dict()
            print(f"[DatasetAutoEnhancer: INFO] Merging entities of type {switcher[entity]['class']}")
            pbar = tqdm(total=len(entities))
            for entity_obj in entities:
                entity_ids = entity_obj.get_identifiers()
                if len(entity_ids) > 0:
                    entity_id = entity_ids[0]
                else:
                    pbar.update(1)
                    continue
                entity_id_literal = entity_id.get_literal_value()
                if entity_id_literal in ids_found:
                    prev_entity = enhanced_graphset.get_entity(URIRef(ids_found[entity_id_literal].res))
                    try:
                        print(f'[DatasetAutoEnhancer: INFO] Merging {prev_entity.res} with {entity_obj.res}')
                        prev_entity.merge(entity_obj)
                    except TypeError:
                        pass
                ids_found[entity_id_literal] = entity_obj
                pbar.update(1)
            pbar.close()
        return enhanced_graphset
    
    def merge_by_id_from_triplestore(self, entities_set:set, ts_url:str='http://localhost:9999/bigdata/sparql') -> GraphSet:
        enhanced_graphset = GraphSet(base_iri=self.base_iri, info_dir=self.info_dir, wanted_label=False)
        switcher = {
            "br": {
                "class": "fabio:Expression",
                "add": enhanced_graphset.add_br
                },
            "ra": {
                "class": "foaf:Agent",
                "add": enhanced_graphset.add_ra
                }
        }
        sparql = SPARQLWrapper(ts_url)
        for entity in entities_set:
            ids_found = dict()
            queryString = f"""
                PREFIX datacite: <http://purl.org/spar/datacite/>
                PREFIX fabio: <http://purl.org/spar/fabio/>
                PREFIX foaf: <http://xmlns.com/foaf/0.1/>
                PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
                SELECT ?s ?literalValue
                WHERE
                {{
                    ?s a {switcher[entity]["class"]};
                        datacite:hasIdentifier/literal:hasLiteralValue ?literalValue.
                }}
            """
            sparql.setQuery(queryString)
            sparql.setReturnFormat(JSON)
            results = sparql.query().convert()
            print(f"[DatasetAutoEnhancer: INFO] Merging entities of type {switcher[entity]['class']}...")
            pbar = tqdm(total=len(results["results"]["bindings"]))
            for result in results["results"]["bindings"]:
                if result["literalValue"]["value"] in ids_found and result["s"]["value"] != ids_found[result["literalValue"]["value"]]:
                    query_duplicated_graph = f"""
                        CONSTRUCT {{<{result["s"]["value"]}> ?p ?o}}
                        WHERE {{<{result["s"]["value"]}> ?p ?o}}
                    """
                    query_preexisting_graph = f"""
                        CONSTRUCT {{<{ids_found[result["literalValue"]["value"]]}> ?p ?o}}
                        WHERE {{<{ids_found[result["literalValue"]["value"]]}> ?p ?o}}
                    """
                    sparql.setQuery(query_duplicated_graph)
                    sparql.setReturnFormat(RDFXML)
                    duplicated_data = sparql.query().convert()
                    duplicated_graph = Graph().parse(data=duplicated_data.serialize(format='xml'), format='xml')
                    sparql.setQuery(query_preexisting_graph)
                    sparql.setReturnFormat(RDFXML)
                    preexisting_data = sparql.query().convert()
                    preexisting_graph = Graph().parse(data=preexisting_data.serialize(format='xml'), format='xml')
                    duplicated_entity = switcher[entity]["add"](self.resp_agent, res=URIRef(result["s"]["value"]), preexisting_graph=duplicated_graph)
                    preexisting_entity = switcher[entity]["add"](self.resp_agent, res=URIRef(ids_found[result["literalValue"]["value"]]), preexisting_graph=preexisting_graph)
                    try:
                        print(f'[DatasetAutoEnhancer: INFO] Merging {result["s"]["value"]} with {ids_found[result["literalValue"]["value"]]}')
                        preexisting_entity.merge(duplicated_entity)
                    except TypeError:
                        pass
                else:
                    ids_found[result["literalValue"]["value"]] = result["s"]["value"]
                pbar.update(1)
            pbar.close()
        return enhanced_graphset
    
    def add_coci_data_from_file(self, journal_issn:str, rdf_file_path:str) -> GraphSet:
        rdf_file = Reader().load(rdf_file_path)
        enhanced_graphset = GraphSet(base_iri=self.base_iri, wanted_label=False)
        Reader().import_entities_from_graph(enhanced_graphset, rdf_file, self.resp_agent, enable_validation=False)
        results_dict = dict()
        queryString = f"""
            PREFIX dcterm: <http://purl.org/dc/terms/>
            PREFIX fabio: <http://purl.org/spar/fabio/>
            PREFIX frbr: <http://purl.org/vocab/frbr/core#>
            PREFIX datacite: <http://purl.org/spar/datacite/>
            PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
            PREFIX cito: <http://purl.org/spar/cito/>
            SELECT ?res ?citingDOI (GROUP_CONCAT(?citedDOI; SEPARATOR=", ") AS ?citedDOIs)
            WHERE {{
                ?res a fabio:JournalArticle;
                    datacite:hasIdentifier ?doiEntity;
                    frbr:partOf+/datacite:hasIdentifier/literal:hasLiteralValue "{journal_issn}".
                ?doiEntity literal:hasLiteralValue ?citingDOI.
                OPTIONAL {{
                    ?res cito:cites/datacite:hasIdentifier/literal:hasLiteralValue ?citedDOI.
                }}
            }}
            GROUP BY ?res ?citingDOI
        """
        results = rdf_file.query(queryString)
        for row in results:
            results_dict[str(row.citingDOI)] = {
                "res": row.res,
                "citedDOIs": row.citedDOIs.split(", ")
            }
        logs = dict()
        pbar = tqdm(total=len(results_dict))
        for citing_doi in results_dict:
            references = Support().handle_request(f"https://w3id.org/oc/index/coci/api/v1/references/{citing_doi}", "./cache/coci_cache", logs)
            for reference in references:
                if reference["cited"] not in results_dict[citing_doi]["citedDOIs"]:
                    citing_entity = enhanced_graphset.get_entity(results_dict[citing_doi]["res"])
                    # Identifier
                    reference_id = enhanced_graphset.add_id(self.resp_agent)
                    reference_id.create_doi(reference["cited"])
                    # BibliographicResource
                    reference_br = enhanced_graphset.add_br(self.resp_agent)
                    reference_br.has_identifier(reference_id)
                    citing_entity.has_citation(reference_br)
                    # Citation
                    reference_ci = enhanced_graphset.add_ci(self.resp_agent)
                    reference_ci.has_citing_entity(citing_entity)
                    reference_ci.has_cited_entity(reference_br)
                    reference_ci.has_citation_creation_date(reference["creation"])
                    reference_ci.has_citation_time_span(reference["timespan"])
                    if reference["journal_sc"] == "yes":
                        reference_ci.create_journal_self_citation()
                    if reference["author_sc"] == "yes":
                        reference_ci.create_author_self_citation()
                else:
                    reference_ci_query = f"""
                        PREFIX datacite: <http://purl.org/spar/datacite/>
                        PREFIX cito: <http://purl.org/spar/cito/>
                        PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
                        CONSTRUCT {{?s ?p ?o}}
                        WHERE {{
                            ?s cito:hasCitingEntity/datacite:hasIdentifier/literal:hasLiteralValue "{reference["citing"]}".
                            ?s cito:hasCitedEntity/datacite:hasIdentifier/literal:hasLiteralValue "{reference["cited"]}".
                            ?s ?p ?o.
                        }}
                    """
                    reference_ci_results = rdf_file.query(reference_ci_query)
                    subjects = set()
                    # If the data already exists, do not add it again
                    if (None, URIRef("http://purl.org/spar/cito/hasCitationTimeSpan"), None) not in reference_ci_results:
                        for row in reference_ci_results:
                            subjects.add(row[0])
                    # There could be duplicates if not already merged
                    for subject in subjects:
                        reference_ci = enhanced_graphset.get_entity(subject)
                        reference_ci.has_citation_time_span(reference["timespan"])
                        if reference["journal_sc"] == "yes":
                            reference_ci.create_journal_self_citation()
                        if reference["author_sc"] == "yes":
                            reference_ci.create_author_self_citation()
            pbar.update(1) 
        pbar.close()
        if len(logs) > 0:
            print("[DatasetAutoEnhancer: INFO] Errors have been found. Writing logs to ./logs/coci.json")
            Support().dump_json(logs, "./logs/coci.json")
        return enhanced_graphset                   

        
    def add_coci_data_from_triplestore(self, journal_issn:str, ts_url:str='http://localhost:9999/bigdata/sparql') -> GraphSet:
        graphset = GraphSet(base_iri=self.base_iri, info_dir=self.info_dir, wanted_label=False)
        queryString = f"""
            PREFIX dcterm: <http://purl.org/dc/terms/>
            PREFIX : <https://github.com/arcangelo7/time_agnostic/>
            PREFIX fabio: <http://purl.org/spar/fabio/>
            PREFIX frbr: <http://purl.org/vocab/frbr/core#>
            PREFIX datacite: <http://purl.org/spar/datacite/>
            PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
            PREFIX cito: <http://purl.org/spar/cito/>
            SELECT ?res ?citingDOI (GROUP_CONCAT(?citedDOI; SEPARATOR=", ") AS ?citedDOIs)
            WHERE {{
                ?res a fabio:JournalArticle;
                    datacite:hasIdentifier ?doiEntity;
                    frbr:partOf+/datacite:hasIdentifier/literal:hasLiteralValue "{journal_issn}".
                ?doiEntity literal:hasLiteralValue ?citingDOI.
                OPTIONAL {{
                    ?res cito:cites/datacite:hasIdentifier/literal:hasLiteralValue ?citedDOI.
                }}
            }}
            GROUP BY ?res ?citingDOI
        """
        sparql = SPARQLWrapper(ts_url)
        sparql.setQuery(queryString)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()
        results_dict = dict()
        for result in results["results"]["bindings"]:
            results_dict[result["citingDOI"]["value"]] = {
                "res": result["res"]["value"],
                "citedDOIs": result["citedDOIs"]["value"].split(", ")
                }
        logs = dict()
        pbar = tqdm(total=len(results_dict))
        for citing_doi in results_dict:
            references = Support().handle_request(f"https://w3id.org/oc/index/coci/api/v1/references/{citing_doi}", "./cache/coci_cache", logs)
            for reference in references:
                if reference["cited"] not in results_dict[citing_doi]["citedDOIs"]:
                    citing_entity_query = f"""
                        PREFIX datacite: <http://purl.org/spar/datacite/>
                        PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
                        CONSTRUCT {{?s ?p ?o}}
                        WHERE {{
                            ?s datacite:hasIdentifier/literal:hasLiteralValue "{citing_doi}".
                            ?s ?p ?o.
                        }}
                    """
                    sparql.setQuery(citing_entity_query)
                    sparql.setReturnFormat(RDFXML)
                    results = sparql.query().convert()
                    preexisting_graph = Graph().parse(data=results.serialize(format='xml'), format='xml')
                    citing_entity = graphset.add_br(self.resp_agent, res=URIRef(results_dict[citing_doi]["res"]), preexisting_graph=preexisting_graph)
                    # Identifier
                    reference_id = graphset.add_id(self.resp_agent)
                    reference_id.create_doi(reference["cited"])
                    # BibliographicResource
                    reference_br = graphset.add_br(self.resp_agent)
                    reference_br.has_identifier(reference_id)
                    citing_entity.has_citation(reference_br)
                    # Citation
                    reference_ci = graphset.add_ci(self.resp_agent)
                    reference_ci.has_citing_entity(citing_entity)
                    reference_ci.has_cited_entity(reference_br)
                    reference_ci.has_citation_creation_date(reference["creation"])
                    reference_ci.has_citation_time_span(reference["timespan"])
                    if reference["journal_sc"] == "yes":
                        reference_ci.create_journal_self_citation()
                    if reference["author_sc"] == "yes":
                        reference_ci.create_author_self_citation()
                else:
                    reference_ci_query = f"""
                        PREFIX datacite: <http://purl.org/spar/datacite/>
                        PREFIX cito: <http://purl.org/spar/cito/>
                        PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
                        CONSTRUCT {{?s ?p ?o}}
                        WHERE {{
                            ?s cito:hasCitingEntity/datacite:hasIdentifier/literal:hasLiteralValue "{reference["citing"]}".
                            ?s cito:hasCitedEntity/datacite:hasIdentifier/literal:hasLiteralValue "{reference["cited"]}".
                            ?s ?p ?o.
                        }}
                    """
                    sparql.setQuery(reference_ci_query)
                    sparql.setReturnFormat(RDFXML)
                    results = sparql.query().convert()
                    subjects = set()
                    # If the data already exists, do not add it again
                    if (None, URIRef("http://purl.org/spar/cito/hasCitationTimeSpan"), None) not in results:
                        preexisting_graph = Graph().parse(data=results.serialize(format='xml'), format='xml')
                        for subject in results.subjects():
                            subjects.add(subject)
                    # There could be duplicates if not already merged
                    for subject in subjects:
                        reference_ci = graphset.add_ci(self.resp_agent, res= URIRef(subject),preexisting_graph=preexisting_graph)
                        reference_ci.has_citation_time_span(reference["timespan"])
                        if reference["journal_sc"] == "yes":
                            reference_ci.create_journal_self_citation()
                        if reference["author_sc"] == "yes":
                            reference_ci.create_author_self_citation()
            pbar.update(1)
        pbar.close()
        if len(logs) > 0:
            print("[DatasetAutoEnhancer: INFO] Errors have been found. Writing logs to ./logs/coci.json")
            Support().dump_json(logs, "./logs/coci.json")
        return graphset
    
    def add_crossref_reference_data_from_triplestore(self, ts_url:str = 'http://localhost:9999/bigdata/sparql') -> GraphSet:
        enhanced_graphset = GraphSet(base_iri=self.base_iri, info_dir=self.info_dir, wanted_label=False)
        queryString = """
            PREFIX cito: <http://purl.org/spar/cito/>
            PREFIX datacite: <http://purl.org/spar/datacite/>
            PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
            SELECT ?citedEntity ?citedEntityDOI
            WHERE {
                ?citation cito:hasCitedEntity ?citedEntity.
                ?citedEntity datacite:hasIdentifier/literal:hasLiteralValue ?citedEntityDOI.
            }
        """
        sparql = SPARQLWrapper(ts_url)
        sparql.setQuery(queryString)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()
        logs = dict()
        pbar = tqdm(total=len(results["results"]["bindings"]))
        for result in results["results"]["bindings"]:
            crossref_info = Support().handle_request(f"https://api.crossref.org/works/{{{result['citedEntityDOI']['value']}}}", "./cache/crossref_cache", logs)
            if crossref_info is not None:
                Support().dump_json(crossref_info, "./test/crossref_info.json")
                if len(logs) > 0:
                    print("[DatasetAutoEnhancer: INFO] Errors have been found. Writing logs to ./logs/crossref.json")
                    Support().dump_json(logs, "./logs/crossref.json")
                return
            else:
                pbar.update(1)
        pbar.close()
    
    def add_unstructured_reference_data_from_triplestore(self, journal_data_path:str, ts_url:str = 'http://localhost:9999/bigdata/sparql') -> GraphSet:
        with open(journal_data_path) as journal_data:
            journal_data_items = json.load(journal_data)["message"]["items"]
        unstructured = dict()
        structured = dict()
        for item in journal_data_items:
            if "reference" in item:
                for reference in item["reference"]:
                    if "DOI" not in reference:
                        unstructured[item["DOI"]] = {"unstructured": reference["unstructured"]}
        logs = dict()
        pbar = tqdm(total=len(unstructured))
        for doi, unstructured in unstructured.items():
            unstructured_field = unstructured["unstructured"]
            doi_in_unstructured = re.search("10.\d{4,9}/[-._;()/:A-Z0-9]+", unstructured_field, flags=re.IGNORECASE)
            if doi_in_unstructured is not None:
                doi_in_unstructured = doi_in_unstructured.group()
                structured[doi] = {"reference_doi": doi_in_unstructured, "unstructured": unstructured_field, "method": "regex"}
            else:
                search = Support().handle_request(f"https://api.crossref.org/works?query.bibliographic={urllib.parse.quote(unstructured['unstructured'])}", cache_path="./cache/crossref_cache", error_log_dict=logs)
                if search is None:
                    continue
                hits = search["message"]["items"]
                score = dict()
                for hit in hits:
                    score[hit["DOI"]] = hit["score"]
                    if "author" in hit:
                        for author in hit["author"]:
                            if "family" in author:
                                if author["family"].lower() in unstructured_field.lower():
                                    score[hit["DOI"]] += 50
                            if "given" in author:
                                if author["given"].lower() in unstructured_field.lower():
                                    score[hit["DOI"]] += 50
                    if "publisher" in hit:
                        if hit["publisher"].lower() in unstructured_field.lower():
                            score[hit["DOI"]] += 50
                    if "title" in hit:
                        if hit["title"][0].lower() in unstructured_field.lower():
                            score[hit["DOI"]] += 100
                v_score = list(score.values())
                k_score = list(score.keys())
                max_score = k_score[v_score.index(max(v_score))]
                if max(v_score) > 200:
                    structured[doi] = {"reference_doi": max_score, "unstructured": unstructured_field, "method": f"Crossref ({max(v_score)})"}
            pbar.update(1)
        pbar.close()
        Support().dump_json(structured, "./test/structured.json")
        if len(logs) > 0:
            print("[DatasetAutoEnhancer: INFO] Errors have been found. Writing logs to ./logs/crossref.json")
            Support().dump_json(logs, "./logs/crossref.json")










                





    