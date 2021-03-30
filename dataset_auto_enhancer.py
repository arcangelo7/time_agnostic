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
from SPARQLWrapper import SPARQLWrapper, JSON, RDFXML

class DatasetAutoEnhancer(object):
    def __init__(self, base_uri, resp_agent, ts_url='http://localhost:9999/bigdata/sparql', dataset=None):
        self.resp_agent = resp_agent
        self.base_uri = base_uri
        if dataset is not None:
            self.dataset = dataset
            self.dataset.commit_changes()
            self.provset = ProvSet(self.dataset, self.base_uri)
            self.provset.generate_provenance()
        else:
            self.ts_url = ts_url

    def merge_graphset_by_id(self, entities_set):
        switcher = {
                "br": self.dataset.get_br,
                "ra": self.dataset.get_ra
        }
        for entity in entities_set:
            entities = switcher[entity]()
            ids_found = dict()
            pbar = tqdm(total=len(entities_set))
            for entity_obj in entities:
                entity_ids = entity_obj.get_identifiers()
                if len(entity_ids) > 0:
                    entity_id = entity_ids[0]
                else:
                    pbar.update(1)
                    continue
                entity_id_literal = entity_id.get_literal_value()
                if entity_id_literal in ids_found:
                    prev_entity = self.dataset.get_entity(URIRef(ids_found[entity_id_literal].res))
                    try:
                        prev_entity.merge(entity_obj)
                    except TypeError:
                        print(prev_entity, entity_obj)
                        pass
                ids_found[entity_id_literal] = entity_obj
                pbar.update(1)
            pbar.close()
        print("Generating provenance...")
        self.dataset.commit_changes()
        self.provset.generate_provenance()
        return self.dataset, self.provset
    
    def merge_triplestore_by_id(self, entities_set):
        enhanced_graphset = GraphSet(self.base_uri)
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
        store = SPARQLStore(self.ts_url, returnFormat="json")
        for entity in entities_set:
            ids_found = dict()
            query = f"""
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
            qres = store.query(query)
            for row in qres:
                if str(row[1]) in ids_found:
                    query_duplicated_graph = f"""
                        CONSTRUCT {{<{str(row[0])}> ?p ?o}}
                        WHERE {{<{str(row[0])}> ?p ?o}}
                    """
                    query_preexisting_graph = f"""
                        CONSTRUCT {{<{ids_found[str(row[1])]}> ?p ?o}}
                        WHERE {{<{ids_found[str(row[1])]}> ?p ?o}}
                    """
                    duplicated_data = store.query(query_duplicated_graph).serialize(format='json')
                    duplicated_graph = Graph().parse(data=duplicated_data, format='json-ld')
                    preexisting_data = store.query(query_preexisting_graph).serialize(format='json')
                    preexisting_graph = Graph().parse(data=preexisting_data, format='json-ld')
                    duplicated_entity = switcher[entity]["add"](self.resp_agent, res=URIRef(str(row[0])), preexisting_graph=duplicated_graph)
                    preexisting_entity = switcher[entity]["add"](self.resp_agent, res=URIRef(ids_found[str(row[1])]), preexisting_graph=preexisting_graph)
                    preexisting_entity.merge(duplicated_entity)
                    # enhanced_graphset.commit_changes()
                else:
                    ids_found[str(row[1])] = str(row[0])
        # enhanced_graphset.sync_with_triplestore(self.ts_url, self.resp_agent)
        # Support().upload_dataset(enhanced_graphset, self.ts_url)
    
    def add_reference_data_from_coci(self, journal_issn):
        graphset = GraphSet(self.base_uri)
        queryString = f"""
            PREFIX dcterm: <http://purl.org/dc/terms/>
            PREFIX : <https://github.com/arcangelo7/time_agnostic/>
            PREFIX fabio: <http://purl.org/spar/fabio/>
            PREFIX frbr: <http://purl.org/vocab/frbr/core#>
            PREFIX datacite: <http://purl.org/spar/datacite/>
            PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
            PREFIX cito: <http://purl.org/spar/cito/>
            SELECT ?citingDOI (GROUP_CONCAT(?citedDOI; SEPARATOR=", ") AS ?citedDOIs)
            WHERE {{
                ?s a fabio:JournalArticle;
                    datacite:hasIdentifier ?doiEntity;
                    frbr:partOf+/datacite:hasIdentifier/literal:hasLiteralValue "{journal_issn}".
                ?doiEntity literal:hasLiteralValue ?citingDOI.
                OPTIONAL {{
                    ?s cito:cites/datacite:hasIdentifier/literal:hasLiteralValue ?citedDOI.
                }}
            }}
            GROUP BY ?citingDOI
        """
        sparql = SPARQLWrapper(self.ts_url)
        sparql.setQuery(queryString)
        sparql.setReturnFormat(JSON)
        results = sparql.query().convert()
        results_dict = dict()
        for result in results["results"]["bindings"]:
            results_dict[result["citingDOI"]["value"]] = result["citedDOIs"]["value"].split(", ")
        logs = dict()
        pbar = tqdm(total=len(results_dict))
        for citing_doi in results_dict:
            references = Support().handle_request(f"https://w3id.org/oc/index/coci/api/v1/references/{citing_doi}", "./cache/coci_cache", logs)
            for reference in references:
                if reference["cited"] not in results_dict[citing_doi]:
                    citing_entity_query = f"""
                        PREFIX datacite: <http://purl.org/spar/datacite/>
                        CONSTRUCT {{?s ?p ?o}}
                        WHERE {{
                            <{self.base_uri + citing_doi}> ^datacite:hasIdentifier ?s.
                            ?s ?p ?o.
                        }}
                    """
                    sparql.setQuery(citing_entity_query)
                    sparql.setReturnFormat(RDFXML)
                    results = sparql.query().convert()
                    preexisting_graph = Graph().parse(data=results.serialize(format='xml'), format='xml')
                    citing_entity = graphset.add_br(self.resp_agent, preexisting_graph=preexisting_graph)
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
                            ?s ?p ?o.
                        }}
                    """
                    sparql.setQuery(reference_ci_query)
                    sparql.setReturnFormat(RDFXML)
                    results = sparql.query().convert()
                    preexisting_graph = Graph().parse(data=results.serialize(format='xml'), format='xml')
                    reference_ci = graphset.add_ci(self.resp_agent, preexisting_graph=preexisting_graph)
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





                





    