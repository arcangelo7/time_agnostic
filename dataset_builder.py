import requests, json, urllib, os
from oc_ocdm.graph.entities.bibliographic_entity import BibliographicEntity
from oc_ocdm.graph import GraphSet
from oc_ocdm.support import create_date
from oc_ocdm.metadata import MetadataSet
from oc_ocdm.graph.entities.bibliographic.bibliographic_resource import BibliographicResource
from tqdm import tqdm
from datetime import datetime
from support import Support
from rdflib import URIRef

class DatasetBuilder(object):
    def __init__(self, base_uri:str, resp_agent:str, info_dir:str = ""):
        self.base_uri = base_uri
        self.resp_agent = resp_agent
        self.info_dir = info_dir
        Support._hack_dates()

    def get_journal_data_from_crossref(self, journal_issn:str, your_email:str, path:str, small:bool=False, logs:bool=False):
        error_log_dict = dict()
        if not os.path.exists("./cache/"):
            os.makedirs("./cache/")
        if requests.get(url = f'http://api.crossref.org/journals/{{{journal_issn}}}').status_code != 200:
            raise("ISSN not found!")
        if small:
            journal_data = Support().handle_request(f"http://api.crossref.org/journals/{{{journal_issn}}}/works?rows=200&mailto={your_email}", "./cache/crossref_cache", error_log_dict)
        else:
            journal_data = Support().handle_request(f"http://api.crossref.org/journals/{{{journal_issn}}}/works?cursor=*&mailto={your_email}", "./cache/crossref_cache", error_log_dict)
            next_cursor = journal_data["message"]["next-cursor"]
            total_results = journal_data["message"]["total-results"]
            pbar = tqdm(total=total_results)
            cursors = set()
            while next_cursor not in cursors:
                cursors.add(next_cursor)
                next_chunk = Support().handle_request(f"http://api.crossref.org/journals/{{{journal_issn}}}/works?cursor={urllib.parse.quote(next_cursor)}&mailto={your_email}", "./cache/crossref_cache", error_log_dict)
                next_cursor = next_chunk["message"]["next-cursor"]
                items_retrieved = next_chunk["message"]["items"]
                journal_data["message"]["items"].extend(items_retrieved)
                pbar.update(20)
            pbar.close()
        Support().dump_json(journal_data, path)
        if logs:
            if not os.path.exists("./logs/"):
                os.makedirs("./logs/")
            Support().dump_json(json.dumps(error_log_dict), f"./logs/{journal_issn}_crossref_error_logs")
    
    @staticmethod
    def _manage_br_type(br:BibliographicResource, item:dict):
        switch = {
            "book": br.create_book,
            "book-chapter": br.create_book_chapter,
            "component": br.create_component,
            "dataset": br.create_dataset,
            "dissertation": br.create_dissertation,
            "journal": br.create_journal,
            "journal-article": br.create_journal_article,
            "journal-issue": br.create_issue,
            "monograph": br.create_monograph,
            "other": br.create_other,
            "posted-content": br.create_other,
            "proceedings": br.create_proceedings,
            "proceedings-article": br.create_proceedings_article,
            "reference-book": br.create_reference_book,
            "reference-entry": br.create_reference_entry,
            "report": br.create_report,
            "report-series": br.create_report_series,
            "None": br.create_other,
            None: br.create_other
        }
        switch[item["type"]]()
    
    @classmethod
    def _manage_volume_issue(cls, graphset:GraphSet, journal_br:BibliographicEntity, item_br:BibliographicEntity, item:dict, resp_agent:str, source:str):
        volume_br = None
        if "volume" in item:
            volume_br = graphset.add_br(resp_agent=resp_agent, source=source)
            volume_br.create_volume()
            volume_br.has_number(item["volume"])
            if journal_br is not None:
                volume_br.is_part_of(journal_br)
        if "issue" in item:
            issue_br = graphset.add_br(resp_agent=resp_agent, source=source)
            issue_br.create_issue()
            issue_br.has_number(item["issue"])
            if volume_br is not None:
                issue_br.is_part_of(volume_br)
            else:
                issue_br.is_part_of(journal_br)
            item_br.is_part_of(issue_br)
        elif "issue" not in item and volume_br is not None:
            item_br.is_part_of(volume_br)
        if "volume" not in item and "issue" not in item and journal_br is not None:
            item_br.is_part_of(journal_br)

    @classmethod
    def _manage_resource_embodiment(cls, graphset:GraphSet, item:dict, item_br:BibliographicEntity, digital_format:bool, resp_agent:str, source:str):
        if not digital_format:
            item_re = graphset.add_re(resp_agent=resp_agent, source=source)
            item_re.create_print_embodiment()
            if "page" in item:
                starting_page = item["page"].split("-")[0] if "-" in item["page"] else item["page"]
                ending_page = item["page"].split("-")[1] if "-" in item["page"] else item["page"]
                item_re.has_starting_page(starting_page)
                item_re.has_ending_page(ending_page)  
            item_br.has_format(item_re)          
        elif digital_format and "link" in item:
            URLs_found = set()
            for link in item["link"]:
                if link["URL"] not in URLs_found and link["content-type"] != "unspecified":
                    item_re = graphset.add_re(resp_agent=resp_agent, source=source)
                    item_re.create_digital_embodiment()
                    item_re.has_media_type(URIRef("https://w3id.org/spar/mediatype/" + link["content-type"]))
                    item_re.has_url(URIRef(link["URL"]))
                    URLs_found.add(link["URL"])
                    item_br.has_format(item_re)
        elif digital_format and not "link" in item:
            item_re = graphset.add_re(resp_agent=resp_agent, source=source)
            item_re.create_digital_embodiment()
            item_br.has_format(item_re)
    
    @classmethod
    def _manage_author_ra_ar(cls, graphset:GraphSet, item:dict, item_br:BibliographicResource, resp_agent:str, source:str):
        authorAgentRoles = list()
        for author in item["author"]:
            author_ra = graphset.add_ra(resp_agent=resp_agent, source=source)
            if "ORCID" in author:
                author_id = graphset.add_id(resp_agent=resp_agent, source=source)
                author_id.create_orcid(author["ORCID"])
                author_ra.has_identifier(author_id)
            if "given" in author:
                author_ra.has_given_name(author["given"])
            if "family" in author:
                author_ra.has_family_name(author["family"])
            if "given" in author and "family" in author:
                author_ra.has_name(author["given"] + " " + author["family"])
            # AgentRole
            author_ar = graphset.add_ar(resp_agent=resp_agent, source=source)
            author_ar.create_author()
            author_ar.is_held_by(author_ra)
            item_br.has_contributor(author_ar)
            authorAgentRoles.append(author_ar)       
        for index, authorAgentRole in enumerate(authorAgentRoles):
            if index+1 < len(authorAgentRoles):
                authorAgentRole.has_next(authorAgentRoles[index+1])         

    def _manage_citations(self, graphset:GraphSet, item:dict, citing_entity:BibliographicEntity, source:str):
        if "reference" in item:
            for reference in item["reference"]:
                if "DOI" in reference:
                    # Identifier
                    reference_id = graphset.add_id(resp_agent=self.resp_agent, source=source)
                    reference_id.create_doi(reference["DOI"])
                    # BibliographicResource
                    reference_br = graphset.add_br(resp_agent=self.resp_agent, source=source)
                    # reference_br.create_journal_article()
                    reference_br.has_identifier(reference_id)
                    citing_entity.has_citation(reference_br)
                    # Citation
                    reference_ci = graphset.add_ci(resp_agent=self.resp_agent, source=source)
                    reference_ci.has_citing_entity(citing_entity)
                    reference_ci.has_cited_entity(reference_br)
                    creation_date = citing_entity.get_pub_date()
                    reference_ci.has_citation_creation_date(creation_date)
                    #BibliographicReference
                    reference_be = graphset.add_be(resp_agent=self.resp_agent, source=source)
                    if "unstructured" in reference:
                        reference_be.has_content(reference["unstructured"])
                    reference_be.references_br(citing_entity)
                    citing_entity.contains_in_reference_list(reference_be)
    
    def generate_dataset(self, title:str, description:str=None) -> MetadataSet:
        metadataset = MetadataSet(self.base_uri)
        dataset = metadataset.add_dataset(title, self.base_uri)
        dataset.has_title(title)
        if description is not None:
            dataset.has_description(description)
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        dataset.has_modification_date(timestamp)
        return metadataset
    
    def generate_graph(self, journal_data_path:str) -> GraphSet:
        journal_graphset = GraphSet(base_iri=self.base_uri, info_dir=self.info_dir, wanted_label=False)
        with open(journal_data_path) as journal_data:
            journal_data_items = json.load(journal_data)["message"]["items"]
        journal_item = next((item for item in journal_data_items if item["type"] == "journal"), None)
        if journal_item is not None:
            source_journal = f"http://api.crossref.org/journals/{journal_item['ISSN'][0]}"
            journal_br = journal_graphset.add_br(resp_agent=self.resp_agent, source=source_journal)
            journal_br.create_journal()
            journal_id = journal_graphset.add_id(resp_agent=self.resp_agent, source=source_journal)
            journal_id.create_issn(journal_item["ISSN"][0])
            journal_br.has_identifier(journal_id)
            journal_br.has_title(journal_item["title"][0])
            if "issn-type" in journal_item:
                for issn_type in journal_item["issn-type"]:
                    digital_format = True if issn_type["type"] == "electronic" else False
                    DatasetBuilder._manage_resource_embodiment(journal_graphset, journal_item, journal_br, digital_format, self.resp_agent, source_journal)
            publisher_ra = journal_graphset.add_ra(resp_agent=self.resp_agent, source=source_journal)
            publisher_ra.has_name(journal_item["title"][0])
            publisher_ra.has_identifier(journal_id)
        pbar = tqdm(total=len(journal_data_items))
        for item in journal_data_items:
            # BibliographicResource
            if item["type"] != "journal":
                source_item = f"https://api.crossref.org/works/{item['DOI']}"
                # Identifier
                item_id = journal_graphset.add_id(resp_agent=self.resp_agent, source=source_item)
                item_id.create_doi(item["DOI"])
                item_br = journal_graphset.add_br(resp_agent=self.resp_agent, source=source_item)  
                DatasetBuilder._manage_br_type(item_br, item)
                item_br.has_identifier(item_id)
                if "title" in item:
                    item_br.has_title(item["title"][0])
                if "subtitle" in item:
                    item_br.has_subtitle(item["subtitle"][0])
                DatasetBuilder._manage_volume_issue(journal_graphset, journal_br, item_br, item, self.resp_agent, source_item)
                # ResourceEmbodiment
                if "published-online" in item:
                    DatasetBuilder._manage_resource_embodiment(journal_graphset, item, item_br, True, self.resp_agent, source_item)     
                if "published-print" in item:
                    DatasetBuilder._manage_resource_embodiment(journal_graphset, item, item_br, False, self.resp_agent, source_item)     
                if "issued" in item:
                    pub_date = item["issued"]["date-parts"][0]
                    iso_date_string = create_date(pub_date)
                    item_br.has_pub_date(iso_date_string)
                # ResponsibleAgent / AgentRole
                if "author" in item:
                    DatasetBuilder._manage_author_ra_ar(journal_graphset, item, item_br, self.resp_agent, source_item)
                if "publisher" in item and journal_item is None:
                    publisher_ra = journal_graphset.add_ra(resp_agent=self.resp_agent, source=source_item)
                    publisher_ra.has_name(item["publisher"])
                    journal_id = journal_graphset.add_id(resp_agent=self.resp_agent, source=source_journal)
                    journal_id.create_issn(item["ISSN"][0])
                    publisher_ra.has_identifier(journal_id)
                publisher_ar = journal_graphset.add_ar(resp_agent=self.resp_agent, source=source_item)
                publisher_ar.create_publisher()
                publisher_ar.is_held_by(publisher_ra)
                item_br.has_contributor(publisher_ar)
                # Citation
                self._manage_citations(journal_graphset, item, item_br, source_item)
                pbar.update(1)
            else:
                pbar.update(1)
        pbar.close()
        return journal_graphset