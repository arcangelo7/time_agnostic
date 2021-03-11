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

    def get_all_references_from_journal(self):
        journal_data_json = self.data
        journal_data_items = journal_data_json["message"]["items"]
        all_references = list()
        for item in journal_data_items:
            references = requests.get(url = f'https://w3id.org/oc/index/coci/api/v1/references/{item["DOI"]}?format=json')
            references_json = references.json()
            all_references.append(references_json)
        return all_references
    
    def update_graph(self, your_orcid):
        journal_graphset = GraphSet("https://arcangelo7.github.io/time_agnostic/")
        journal_data_items = self.data["message"]["items"]
        journal_br = journal_graphset.add_br(your_orcid)
        journal_br.create_journal()
        journal_item = next((item for item in journal_data_items if item["type"] == "journal"), None)
        journal_br.has_title(journal_item["title"][0])
        for item in journal_data_items:
            # AgentRole
            author_ar = journal_graphset.add_ar(your_orcid)
            author_ar.create_author()
            # ResponsibleAgent
            if "author" in item:
                for author in item["author"]:
                    journal_ra = journal_graphset.add_ra(your_orcid)
                    author_ar.is_held_by(journal_ra)
                    if "given" in author:
                        journal_ra.has_given_name(author["given"])
                    if "family" in author:
                        journal_ra.has_family_name(author["family"])
                    if "given" in author and "family" in author:
                        journal_ra.has_name(author["given"] + " " + author["family"])
            # BibliographicResource
            if item["type"] != "journal":
                journal_br = journal_graphset.add_br(your_orcid)  
                journal_br.create_journal_article()
                journal_br.has_title(item["title"][0])
                if "subtitle" in item:
                    journal_br.has_subtitle(item["subtitle"][0])
                # ResourceEmbodiment
                journal_re = journal_graphset.add_re(your_orcid)
                if "published-online" in item:
                    pub_date = item["published-online"]["date-parts"][0][0]
                    journal_re.create_digital_embodiment()
                if "published-print" in item:
                    pub_date = item["published-print"]["date-parts"][0][0]
                    journal_re.create_print_embodiment()
                journal_re.has_media_type(URIRef("https://www.iana.org/assignments/media-types/" + item["link"][0]["content-type"]))
                if "page" in item:
                    journal_re.has_starting_page(item["page"].split("-")[0])
                    journal_re.has_ending_page(item["page"].split("-")[1])
                journal_re.has_url(URIRef(item["link"][0]["URL"]))
                iso_date_string = create_date([pub_date])
                journal_br.has_pub_date(iso_date_string)
                journal_br.is_part_of(journal_br)
                journal_br.has_format(journal_re)
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
