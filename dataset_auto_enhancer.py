import re, rdflib, json, urllib, itertools, os
from support import Support
from dataset_builder import DatasetBuilder
from tqdm import tqdm
from rdflib import URIRef, Graph
from rdflib.serializer import Serializer
from rdflib.plugins.sparql.results.jsonresults import JSONResultSerializer
from rdflib.plugins.sparql import prepareQuery
from oc_ocdm.support.query_utils import get_update_query
from datetime import datetime
from oc_ocdm.graph.graph_entity import GraphEntity
from oc_ocdm.graph import GraphSet
from oc_ocdm.prov import ProvSet
from oc_ocdm.reader import Reader
from oc_ocdm.support import create_date
from SPARQLWrapper import SPARQLWrapper, JSON, RDFXML
from collections import OrderedDict

class DatasetAutoEnhancer(object):
    def __init__(self, base_uri:str, resp_agent:str, info_dir:str=""):
        self.base_iri = base_uri
        self.resp_agent = resp_agent
        self.info_dir = info_dir

    def _get_entity_and_ids_from_res(self, sparql:SPARQLWrapper, graphset:GraphSet, res:URIRef, switcher:dict, entity:str):
        query = f"""
            CONSTRUCT {{<{res}> ?p ?o}}
            WHERE {{<{res}> ?p ?o}}
        """
        sparql.setQuery(query)
        sparql.setReturnFormat(RDFXML)
        data = sparql.query().convert()
        graph = Graph().parse(data=data.serialize(format='xml'), format='xml')
        entity = switcher[entity]["add"](self.resp_agent, res=res, preexisting_graph=graph)
        ids = entity.get_identifiers()
        ids_entities = set()
        for identifier in ids:
            id_query = f"""
                CONSTRUCT {{<{identifier.res}> ?p ?o}}
                WHERE {{<{identifier.res}> ?p ?o}}
            """
            sparql.setQuery(id_query)
            sparql.setReturnFormat(RDFXML)
            id_data = sparql.query().convert()
            id_graph = Graph().parse(data=id_data.serialize(format='xml'), format='xml')
            id_entity = graphset.add_id(resp_agent=self.resp_agent, res=identifier.res, preexisting_graph=id_graph)
            ids_entities.add(id_entity)
        return entity, ids_entities
    
    def merge_by_id(self, entities_set:set, ts_url:str='http://localhost:9999/bigdata/sparql') -> GraphSet:
        enhanced_graphset = GraphSet(base_iri=self.base_iri, info_dir=self.info_dir, wanted_label=False)
        sparql = SPARQLWrapper(ts_url)
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
            pbar = tqdm(total=len(results["results"]["bindings"]))
            for result in results["results"]["bindings"]:
                if result["literalValue"]["value"] in ids_found and result["s"]["value"] != ids_found[result["literalValue"]["value"]]:
                    preexisting_entity, preexisting_ids = self._get_entity_and_ids_from_res(sparql=sparql, graphset=enhanced_graphset, res=URIRef(ids_found[result["literalValue"]["value"]]), switcher=switcher, entity=entity)
                    duplicated_entity, duplicated_ids = self._get_entity_and_ids_from_res(sparql=sparql, graphset=enhanced_graphset, res=URIRef(result["s"]["value"]), switcher=switcher, entity=entity)
                    try:
                        print(f'[DatasetAutoEnhancer: INFO] Merging {result["s"]["value"]} with {ids_found[result["literalValue"]["value"]]}')
                        preexisting_entity.merge(duplicated_entity)
                        for preexisting_id, duplicated_id in itertools.product(preexisting_ids, duplicated_ids):
                            if preexisting_id != duplicated_id:
                                print(f'[DatasetAutoEnhancer: INFO] Merging {preexisting_id.res} with {duplicated_id.res}')
                                preexisting_id.merge(duplicated_id)
                    except TypeError:
                        pass
                else:
                    ids_found[result["literalValue"]["value"]] = result["s"]["value"]
                pbar.update(1)
            pbar.close()
        return enhanced_graphset
        
    def add_coci_data(self, journal_issn:str, ts_url:str='http://localhost:9999/bigdata/sparql') -> GraphSet:
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
    
    def add_crossref_reference_data(self, ts_url:str = 'http://localhost:9999/bigdata/sparql') -> GraphSet:
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
            crossref_info = Support().handle_request(f"https://api.crossref.org/works/{result['citedEntityDOI']['value']}", "./cache/crossref_cache", logs)
            if crossref_info is not None:
                item = crossref_info["message"]
                # Journal BR
                if "ISSN" in item:
                    journal_br = enhanced_graphset.add_br(resp_agent=self.resp_agent)
                    journal_br.create_journal()
                    journal_id = enhanced_graphset.add_id(self.resp_agent)
                    journal_id.create_issn(item["ISSN"][0])
                    journal_br.has_identifier(journal_id)
                    if "publisher" in item:
                        journal_br.has_title(item["publisher"])
                        publisher_ra = enhanced_graphset.add_ra(self.resp_agent)
                        publisher_ra.has_name(item["publisher"])
                        publisher_ra.has_identifier(journal_id)
                        publisher_ar = enhanced_graphset.add_ar(self.resp_agent)
                        publisher_ar.create_publisher()
                        publisher_ar.is_held_by(publisher_ra)
                reference_br_uri = URIRef(result['citedEntity']['value'])
                preexisting_graph_query = f"""
                    CONSTRUCT {{<{reference_br_uri}> ?p ?o}}
                    WHERE {{<{reference_br_uri}> ?p ?o}}
                """
                sparql.setQuery(preexisting_graph_query)
                sparql.setReturnFormat(RDFXML)
                preexisting_graph_data = sparql.query().convert()
                preexisting_graph = Graph().parse(data=preexisting_graph_data.serialize(format='xml'), format='xml')
                reference_br = enhanced_graphset.add_br(self.resp_agent, res=reference_br_uri, preexisting_graph=preexisting_graph)
                try:
                    DatasetBuilder._manage_br_type(reference_br, item)
                except KeyError as e:
                    print(e)
                if len(item["title"]) > 0:
                    reference_br.has_title(item["title"][0])
                if len(item["subtitle"]) > 0:
                    reference_br.has_subtitle(item["subtitle"][0])  
                DatasetBuilder._manage_volume_issue(enhanced_graphset, journal_br, reference_br, item, self.resp_agent)
                # ResourceEmbodiment
                if "published-online" in item:
                    DatasetBuilder._manage_resource_embodiment(enhanced_graphset, item, reference_br, self.resp_agent, digital_format=True)     
                if "published-print" in item:
                    DatasetBuilder._manage_resource_embodiment(enhanced_graphset, item, reference_br, self.resp_agent, digital_format=False)     
                pub_date = item["issued"]["date-parts"][0][0]
                if pub_date is not None:
                    iso_date_string = create_date([pub_date])
                    reference_br.has_pub_date(iso_date_string)
                if "author" in item:
                    DatasetBuilder._manage_author_ra_ar(enhanced_graphset, item, reference_br, self.resp_agent)
            pbar.update(1)
        if len(logs) > 0:
            print("[DatasetAutoEnhancer: INFO] Errors have been found. Writing logs to ./logs/crossref.json")
            if not os.path.exists("./logs/"):
                os.makedirs("./logs/")
            Support().dump_json(logs, "./logs/crossref.json")
        pbar.close()
        return enhanced_graphset
    
    def add_unstructured_reference_data(self, journal_data_path:str, ts_url:str = 'http://localhost:9999/bigdata/sparql') -> GraphSet:
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
    
    def _generate_crossref_query_from_metadata(self, metadata:dict):
        switch = {
            "unstructured": {
                "type": "query",
                "keyword": "bibliographic"
            }, 
            "journal-title": {
                "type": "query",
                "keyword": "container-title"
            },
            "author": {
                "type": "query",
                "keyword": "author"
            }, 
            "ISBN": {
                "type": "filter",
                "keyword": "isbn"
            },
            "year": {
                "type": "filter",
                "keyword": "from-index-date"
            }
        }
        if "year" in metadata:
            metadata.move_to_end("year", last=True)
        if "ISBN" in metadata:
            metadata.move_to_end("ISBN", last=True)
        query_string = "https://api.crossref.org/works?"
        for k, v in metadata.items():
            if k in switch:
                keyword = switch[k]['keyword']
                value = urllib.parse.quote(v)
                if switch[k]["type"] == "query":
                    query_param = f"query.{keyword}={value}&"
                elif switch[k]["type"] == "filter":
                    if "filter=" not in query_string:
                        query_param = f"filter={keyword}:{value},"
                    else:
                        query_param = f"{keyword}:{value},"
                query_string += query_param
        return query_string[:-1]
    
    def add_reference_data_without_doi(self, journal_data_path:str, ts_url:str = 'http://localhost:9999/bigdata/sparql') -> GraphSet:
        logs = dict()
        sparql = SPARQLWrapper(ts_url)
        graphset = GraphSet(base_iri=self.base_iri, info_dir=self.info_dir, wanted_label=False)
        with open(journal_data_path) as journal_data:
            journal_data_items = json.load(journal_data)["message"]["items"]
        pbar = tqdm(total=len(journal_data_items))
        for item in journal_data_items:
            if "reference" in item:
                for reference in item["reference"]:
                    if "DOI" not in reference and len(reference) > 2: # That is, if there is more information than just key and unstructured
                        query_string = self._generate_crossref_query_from_metadata(OrderedDict(reference))
                        search = Support().handle_request(url=query_string, cache_path="./cache/crossref_cache", error_log_dict=logs)
                        if len(search["message"]["items"]) > 0:
                            new_doi = search["message"]["items"][0]["DOI"]
                            citing_entity_query = f"""
                                PREFIX datacite: <http://purl.org/spar/datacite/>
                                PREFIX literal: <http://www.essepuntato.it/2010/06/literalreification/>
                                PREFIX cito: <http://purl.org/spar/cito/>
                                CONSTRUCT {{?s ?p ?o}}
                                WHERE {{
                                    ?s datacite:hasIdentifier/literal:hasLiteralValue "{item["DOI"]}".
                                    FILTER NOT EXISTS {{?s cito:cites/datacite:hasIdentifier/literal:hasLiteralValue "{new_doi}"}}
                                    ?s ?p ?o.
                                }}
                            """
                            sparql.setQuery(citing_entity_query)
                            sparql.setReturnFormat(RDFXML)
                            results = sparql.query().convert()
                            preexisting_graph = Graph().parse(data=results.serialize(format='xml'), format='xml')
                            subjects = dict()
                            if (None, URIRef("http://prismstandard.org/namespaces/basic/2.0/publicationDate"), None) in results:
                                for s, p, o in results.triples((None, None, None)):
                                    if p == URIRef('http://prismstandard.org/namespaces/basic/2.0/publicationDate'):
                                        subjects[s] = o
                            else:
                                for s in results.subjects():
                                    subjects[s] = ""
                            # There could be duplicates if not already merged
                            for subject in subjects:
                                citing_entity = graphset.add_br(self.resp_agent, res=subject, preexisting_graph=preexisting_graph)
                                # Identifier
                                reference_id = graphset.add_id(self.resp_agent)
                                reference_id.create_doi(new_doi)
                                # BibliographicResource
                                reference_br = graphset.add_br(self.resp_agent)
                                reference_br.has_identifier(reference_id)
                                citing_entity.has_citation(reference_br)
                                # Citation
                                reference_ci = graphset.add_ci(self.resp_agent)
                                reference_ci.has_citing_entity(citing_entity)
                                reference_ci.has_cited_entity(reference_br)
                                if subjects[subject] != "":
                                    reference_ci.has_citation_creation_date(str(subjects[subject]))
            pbar.update(1)
        pbar.close()
        return graphset












                





    