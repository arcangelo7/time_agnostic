import re, rdflib, json
from support import Support
from dataset_builder import DatasetBuilder
from tqdm import tqdm
from rdflib import URIRef, Namespace, ConjunctiveGraph, Graph
from rdflib.plugins.sparql.results.jsonresults import JSONResultSerializer
from rdflib.plugins.stores.sparqlstore import SPARQLStore
from oc_ocdm.support.query_utils import get_update_query
from datetime import datetime
from oc_ocdm.graph.graph_entity import GraphEntity
from oc_ocdm.graph import GraphSet
from oc_ocdm.prov import ProvSet
from oc_ocdm.reader import Reader
from SPARQLWrapper import SPARQLWrapper, JSON, RDFXML

class DatasetAutoEnhancer(object):
    def __init__(self, base_uri:str, resp_agent:str, info_dir:str=""):
        self.base_uri = base_uri
        self.resp_agent = resp_agent
        self.info_dir = info_dir

    def merge_by_id_from_file(self, entities_set:set, rdf_file_path:str):
        reader = Reader()
        rdf_file = reader.load(rdf_file_path)
        enhanced_graphset = GraphSet(base_iri="https://github.com/arcangelo7/time_agnostic/", info_dir=self.info_dir, wanted_label=False)
        reader.import_entities_from_graph(enhanced_graphset, rdf_file, "https://orcid.org/0000-0002-8420-0696", enable_validation=False)
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
                        print(f'Merging {prev_entity.res} with {entity_obj.res}')
                        prev_entity.merge(entity_obj)
                    except TypeError:
                        pass
                ids_found[entity_id_literal] = entity_obj
                pbar.update(1)
            pbar.close()
        return enhanced_graphset
    
    def merge_by_id_from_triplestore(self, entities_set:set, ts_url:str='http://localhost:9999/bigdata/sparql'):
        enhanced_graphset = GraphSet(base_iri=self.base_uri, info_dir=self.info_dir, wanted_label=False)
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
        sparql = SPARQLWrapper(self.ts_url)
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
            print(f"Merging entities of type {switcher[entity]['class']}...")
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
                        print(f'Merging {result["s"]["value"]} with {ids_found[result["literalValue"]["value"]]}')
                        preexisting_entity.merge(duplicated_entity)
                    except TypeError:
                        pass
                else:
                    ids_found[result["literalValue"]["value"]] = result["s"]["value"]
                pbar.update(1)
            pbar.close()
        return enhanced_graphset
    
    def add_reference_data_from_coci(self, journal_issn:str, ts_url:str='http://localhost:9999/bigdata/sparql'):
        graphset = GraphSet(base_iri=self.base_uri, info_dir=self.info_dir, wanted_label=False)
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
        sparql = SPARQLWrapper(self.ts_url)
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
            print("Errors have been found. Writing logs...")
            Support().dump_json(logs, "./logs/coci.json")
        return graphset





                





    