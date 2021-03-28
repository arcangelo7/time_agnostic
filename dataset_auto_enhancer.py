import re, sparql, rdflib, json
from support import Support
from tqdm import tqdm
from rdflib import URIRef, Namespace, ConjunctiveGraph, Graph
from rdflib.plugins.sparql.results.jsonresults import JSONResultSerializer
from rdflib.plugins.stores.sparqlstore import SPARQLStore
from oc_ocdm.support.query_utils import get_update_query
from datetime import datetime
from oc_ocdm.graph.graph_entity import GraphEntity
from oc_ocdm.graph import GraphSet
from oc_ocdm.prov import ProvSet

class DatasetAutoEnhancer(object):
    def __init__(self, resp_agent, base_uri, ts_url='http://localhost:9999/bigdata/sparql', dataset=None):
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
                        datacite:hasIdentifier ?o.
                    ?o literal:hasLiteralValue ?literalValue.
                }}
                LIMIT 1000
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

                





    