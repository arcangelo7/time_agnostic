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
import numpy as np

class DatasetAutoEnhancer(object):
    def __init__(self, base_uri:str, resp_agent:str, info_dir:str=""):
        self.base_iri = base_uri
        self.resp_agent = resp_agent
        self.info_dir = info_dir

    def _get_rich_entity_from_res(self, sparql:SPARQLWrapper, graphset:GraphSet, res:URIRef, switcher:dict, entity:str) -> GraphEntity:
        query = f"""
            CONSTRUCT {{
                <{res}> ?p ?o.
                ?s ?other_p <{res}>.
            }}
            WHERE {{
                <{res}> ?p ?o.
                ?s ?other_p <{res}>.
            }}
        """
        sparql.setQuery(query)
        sparql.setReturnFormat(RDFXML)
        data = sparql.query().convert()
        graph = Graph().parse(data=data.serialize(format='xml'), format='xml')
        entity = switcher[entity]["add"](self.resp_agent, res=res, preexisting_graph=graph)
        # ids = entity.get_identifiers()
        # ids_entities = set()
        # for identifier in ids:
        #     id_query = f"""
        #         CONSTRUCT {{<{identifier.res}> ?p ?o}}
        #         WHERE {{<{identifier.res}> ?p ?o}}
        #     """
        #     sparql.setQuery(id_query)
        #     sparql.setReturnFormat(RDFXML)
        #     id_data = sparql.query().convert()
        #     id_graph = Graph().parse(data=id_data.serialize(format='xml'), format='xml')
        #     id_entity = graphset.add_id(resp_agent=self.resp_agent, res=identifier.res, preexisting_graph=id_graph)
        #     ids_entities.add(id_entity)
        return entity
    
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
                    preexisting_entity = self._get_rich_entity_from_res(sparql=sparql, graphset=enhanced_graphset, res=URIRef(ids_found[result["literalValue"]["value"]]), switcher=switcher, entity=entity)
                    duplicated_entity = self._get_rich_entity_from_res(sparql=sparql, graphset=enhanced_graphset, res=URIRef(result["s"]["value"]), switcher=switcher, entity=entity)
                    # try:
                    # print(f'[DatasetAutoEnhancer: INFO] Merging {result["s"]["value"]} with {ids_found[result["literalValue"]["value"]]}')
                    preexisting_entity.merge(duplicated_entity)
                    # for preexisting_id, duplicated_id in itertools.product(preexisting_ids, duplicated_ids):
                    #     if preexisting_id != duplicated_id:
                    #         print(f'[DatasetAutoEnhancer: INFO] Merging {preexisting_id.res} with {duplicated_id.res}')
                    #         preexisting_id.merge(duplicated_id)
                    # except TypeError:
                    #     pass
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
        
    def _generate_crossref_query_from_metadata(self, metadata:dict) -> str:
        switch = {
            "unstructured": "bibliographic", 
            "journal-title": "container-title",
            "volume-title": "container-title",
            "series-title": "container-title",
            "author": "author"
        }
        query_string = "https://api.crossref.org/works?"
        for k, v in metadata.items():
            if k in switch:
                keyword = switch[k]
                value = urllib.parse.quote(v)
                query_param = f"query.{keyword}={value}&"
                query_string += query_param
        return query_string[:-1]
    
    def _levenshtein_distance(self, target:str, source:str) -> int:
        # Build matrix of correct size
        target = [k for k in "#" + target]
        source = [k for k in "#" + source]
        sol = np.zeros(shape=(len(source), len(target)))
        # first row & column
        sol[0] = [j for j in range(len(target))]
        sol[:,0] = [j for j in range(len(source))]
        # Add anchor value
        if target[1] != source[1]:
            sol[1,1] = 2
        # Fill in rest
        # Through every column
        for c in range(1, len(target)):
            #Through evert row
            for r in range(1, len(source)):
                # Not same letter
                if target[c] != source[r]:
                    sol[r,c] = min(sol[r-1,c], sol[r,c-1]) + 1
                #Same letter
                else:
                    sol[r,c] = sol[r-1,c-1]
        min_edit_distance = int(sol[-1,-1])
        return min_edit_distance
    
    def _match_first_author(self, source_metadata:dict, target_metadata:dict) -> float:
        if "author" in source_metadata and "author" in target_metadata:
            if " " in source_metadata["author"]:
                first_name_a = source_metadata["author"].split()[0]
                last_name_a = source_metadata["author"].split()[1]
            else:
                return 0.0
            if "family" in target_metadata["author"][0] and "given" in target_metadata["author"][0]:
                first_name_b = target_metadata["author"][0]["given"].replace(".", "")
                last_name_b = target_metadata["author"][0]["family"]
            else: 
                return 0.0
            first_name_a = first_name_a.title()
            last_name_a = last_name_a.title()
            first_name_b = first_name_b.title()
            last_name_b = last_name_b.title()
            first_name_a = "".join(re.findall("[A-Z]", first_name_a)) 
            first_name_b = "".join(re.findall("[A-Z]", first_name_b))
            e = 0.0
            if first_name_a == first_name_b:
                e = 1.0
            m_first_author = 0.8 - 0.8 * self._levenshtein_distance(last_name_a, last_name_b) / max(len(last_name_a), len(last_name_b)) + 0.2 * e
        else:
            m_first_author = 0.0
        return m_first_author
    
    def _match_title(self, source_metadata:dict, target_metadata:dict) -> float:
        if "volume-title" in source_metadata and "title" in target_metadata and len(target_metadata["title"][0]) > 0:
            title_a = source_metadata["volume-title"]
            title_b = target_metadata["title"][0]
            match_title = 1 - self._levenshtein_distance(title_a, title_b) / max(len(title_a), len(title_b))
        else:
            match_title = 0.0
        return match_title
    
    def _match_source(self, source_metadata:dict, target_metadata:dict) -> float:
        if "ISBN" in source_metadata and "ISBN" in target_metadata:
            if source_metadata["ISBN"] == target_metadata["ISBN"][0]:
                match_source = 1.0
                return match_source
        if "journal-title" in source_metadata:
            source_a = source_metadata["journal-title"]
        elif "volume-title" in source_metadata:
            source_a = source_metadata["volume-title"]
        elif "series-title" in source_metadata:
            source_a = source_metadata["series-title"]
        else:
            return 0.0
        if "container-title" in target_metadata and len(target_metadata["container-title"][0]) > 0:
            source_b_long = target_metadata["container-title"][0]
            match_source_long = 1 - (self._levenshtein_distance(source_a, source_b_long) - abs(len(source_a) - len(source_b_long))) / min(len(source_a), len(source_b_long))
            if "short-container-title" in target_metadata and len(target_metadata["short-container-title"][0]) > 0:
                source_b_short = target_metadata["short-container-title"][0]
                match_source_short = 1 - (self._levenshtein_distance(source_a, source_b_short) - abs(len(source_a) - len(source_b_short))) / min(len(source_a), len(source_b_short))
                match_source = max(match_source_long, match_source_short)
            else:
                match_source = match_source_long
        else:
            match_source = 0.0
        return match_source
    
    def _match_other(self, source_metadata:dict, target_metadata:dict):
        e_y = 0.0
        e_v = 0.0
        e_i = 0.0
        e_b = 0.0
        if "year" in source_metadata and "issued" in target_metadata:
            if target_metadata["issued"]["date-parts"][0][0] is not None:
                year_a = int(source_metadata["year"].replace("–", "-").replace("/", "-").replace(".", "").split("-")[0])
                year_b = target_metadata["issued"]["date-parts"][0][0]
                if year_a == year_b:
                    e_y = 1.0
        if "volume" in source_metadata and "volume" in target_metadata:
            volume_number_a = source_metadata["volume"]
            volume_number_b = target_metadata["volume"]
            if volume_number_a == volume_number_b:
                e_v = 1.0          
        if "issue" in source_metadata and "issue" in target_metadata:
            issue_number_a = source_metadata["issue"]
            issue_number_b = target_metadata["issue"]
            if issue_number_a == issue_number_b:
                e_i = 1.0     
        if "first-page" in source_metadata and "page" in target_metadata:       
            begin_page_a = source_metadata["first-page"]
            begin_page_b = target_metadata["page"].split("-")[0]
            if begin_page_a == begin_page_b:
                e_b = 1.0
        match_other = 0.1 * e_y + 0.2 * e_v + 0.1 * e_i + 0.6 * e_b 
        return match_other

    def _is_a_match(self, source_metadata:dict, target_metadata:dict) -> tuple[bool, float]:
        match_first_author = self._match_first_author(source_metadata, target_metadata)
        match_title = self._match_title(source_metadata, target_metadata)
        match_source = self._match_source(source_metadata, target_metadata)
        match_other = self._match_other(source_metadata, target_metadata)
        similarity_a_b = 7 * match_first_author + 14 * match_title + 5 * match_source + 14 * match_other
        if similarity_a_b >= 15.0:
            return True, similarity_a_b
        else:
            return False, similarity_a_b
    
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
                        query_string = self._generate_crossref_query_from_metadata(reference)
                        search = Support().handle_request(url=query_string, cache_path="./cache/crossref_cache", error_log_dict=logs)
                        if search is not None:
                            if len(search["message"]["items"]) > 0:
                                best_matches = list()
                                for item in search["message"]["items"][:10]: # Check only the first 10 results, which are already ordered by score
                                    is_a_match, score = self._is_a_match(reference, item)
                                    if is_a_match:
                                        best_matches.append({"item": item, "score": score})
                                if len(best_matches) > 0:
                                    best_match = sorted(best_matches, key=lambda k: k["score"], reverse=True)[0]["item"]
                                    new_doi = best_match["DOI"]
                                else:
                                    continue
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












                





    