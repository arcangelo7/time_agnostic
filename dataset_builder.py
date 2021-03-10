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
            journal_data["message"]["items"].append(items_retrieved)
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
    
    def update_graph(self):
        scientometrics_graphset = GraphSet("https://arcangelo7.github.io/time_agnostic/")
        journal_data_items = self.data["message"]["items"]
        for item in journal_data_items:
            try:
                # a volte gli articoli ritornati da crossref non hanno il campo "author". È molto raro, ma accade.
                responsible_agent_name = item["author"][0]["given"] + " " + item["author"][0]["family"]
                responsible_agent = scientometrics_graphset.add_ra(responsible_agent_name)
                responsible_agent.has_given_name(item["author"][0]["given"])
                responsible_agent.has_family_name(item["author"][0]["family"])
                # non ho ancora gestito il problema dell'omonimia, ma sono consapevole che vada gestito
                scientometrics_br = scientometrics_graphset.add_br(responsible_agent)
                scientometrics_br.has_title(item["title"][0])
                iso_date_string = create_date([item["published-print"]["date-parts"][0][0]])
                scientometrics_br.has_pub_date(iso_date_string)
            except KeyError:
                pass
        scientometrics_graphset.commit_changes()
        return scientometrics_graphset

    def dump_data(self, path, data=None):
        if data is None:
            data = self.data
        with open(path, 'w') as outfile:
            json.dump(data, outfile)
    
    def dump_dataset(self, data, path):
        storer = Storer(data)
        storer.store_graphs_in_file(path, "./")
