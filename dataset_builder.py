import requests, requests_cache, json, urllib
from oc_ocdm.graph import GraphSet
from oc_ocdm.storer import Storer
from oc_ocdm.support import create_date
from rdflib import URIRef

class DatasetBuilder(object):
    def __init__(self, journal_issn, your_email):
        requests_cache.install_cache('cache')
        journal_data = requests.get(url = f'http://api.crossref.org/journals/{{{journal_issn}}}/works?cursor=*&mailto={your_email}').json()
        next_cursor = journal_data["message"]["next-cursor"]
        cursors = set()
        while next_cursor not in cursors:
            cursors.add(next_cursor)
            next_chunk = requests.get(url = f'http://api.crossref.org/journals/{{{journal_issn}}}/works?cursor={urllib.parse.quote(next_cursor)}&mailto={your_email}').json()
            next_cursor = next_chunk["message"]["next-cursor"]
            items_retrieved = next_chunk["message"]["items"]
            for item in items_retrieved:
                journal_data["message"]["items"].append(item)
        self.data = journal_data

    def _manage_citations(self, graphset, item, citing_entity, your_orcid):
        try:
            references = requests.get(url = f'https://w3id.org/oc/index/coci/api/v1/references/{item["DOI"]}?format=json').json()
            for reference in references:
                reference_id = graphset.add_id(your_orcid)
                reference_id.create_doi(reference["cited"])
                # print(reference["cited"])
                reference_br = graphset.add_br(your_orcid)
                reference_br.has_identifier(reference_id)
                # Citation
                reference_ci = graphset.add_ci(your_orcid)
                reference_ci.has_citing_entity(citing_entity)
                reference_ci.has_cited_entity(reference_br)
                reference_ci.has_citation_creation_date(reference["creation"])
                reference_ci.has_citation_time_span(reference["timespan"])
        except json.decoder.JSONDecodeError: 
            print("\n\njson.decoder.JSONDecodeError")
            print(item["DOI"] + "\n\n")
    
    def create_graph_from_crossref_data(self, your_orcid):
        journal_graphset = GraphSet("https://arcangelo7.github.io/time_agnostic/")
        journal_data_items = self.data["message"]["items"]
        journal_br = journal_graphset.add_br(your_orcid)
        journal_br.create_journal()
        journal_item = next(item for item in journal_data_items if item["type"] == "journal")
        journal_id = journal_graphset.add_id(your_orcid)
        journal_id.create_issn(journal_item["ISSN"][0])
        journal_br.has_identifier(journal_id)
        journal_br.has_title(journal_item["title"][0])
        journal_re = journal_graphset.add_re(your_orcid)
        journal_re.create_print_embodiment()
        journal_re.create_digital_embodiment()
        journal_re.has_url(URIRef(journal_item["URL"]))
        journal_br.has_format(journal_re)
        for item in journal_data_items:
            # Identifier
            item_id = journal_graphset.add_id(your_orcid)
            item_id.create_doi(item["DOI"])
            # BibliographicResource
            if item["type"] != "journal":
                item_br = journal_graphset.add_br(your_orcid)  
                item_br.create_journal_article()
                item_br.has_identifier(item_id)
                item_br.has_title(item["title"][0])
                if "subtitle" in item:
                    item_br.has_subtitle(item["subtitle"][0])
                # ResourceEmbodiment
                item_re = journal_graphset.add_re(your_orcid)
                if "published-online" in item:
                    pub_date = item["published-online"]["date-parts"][0][0]
                    item_re.create_digital_embodiment()
                if "published-print" in item:
                    pub_date = item["published-print"]["date-parts"][0][0]
                    item_re.create_print_embodiment()
                item_re.has_media_type(URIRef("https://www.iana.org/assignments/media-types/" + item["link"][0]["content-type"]))
                if "page" in item:
                    item_re.has_starting_page(item["page"].split("-")[0])
                    item_re.has_ending_page(item["page"].split("-")[1])
                item_re.has_url(URIRef(item["URL"]))
                iso_date_string = create_date([pub_date])
                item_br.has_pub_date(iso_date_string)
                item_br.is_part_of(journal_br)
                item_br.has_format(item_re)
            # ResponsibleAgent
            if "author" in item:
                for author in item["author"]:
                    item_ra = journal_graphset.add_ra(your_orcid)
                    if "ORCID" in author:
                        author_id = journal_graphset.add_id(your_orcid)
                        author_id.create_orcid(author["ORCID"])
                        item_ra.has_identifier(author_id)
                    if "given" in author:
                        item_ra.has_given_name(author["given"])
                    if "family" in author:
                        item_ra.has_family_name(author["family"])
                    if "given" in author and "family" in author:
                        item_ra.has_name(author["given"] + " " + author["family"])
                    # AgentRole
                    author_ar = journal_graphset.add_ar(your_orcid)
                    author_ar.create_author()
                    author_ar.is_held_by(item_ra)
                    item_br.has_contributor(author_ar)
            self._manage_citations(journal_graphset, item, item_br, your_orcid)
        journal_graphset.commit_changes()
        return journal_graphset

    def dump_data(self, path, data=None):
        if data is None:
            data = self.data
        with open(path, 'w') as outfile:
            json.dump(data, outfile, sort_keys=True, indent=4)
    
    def dump_dataset(self, data, path):
        storer = Storer(data)
        storer.store_graphs_in_file(path, "./")
