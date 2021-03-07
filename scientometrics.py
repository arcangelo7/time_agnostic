import requests, requests_cache, json
from oc_ocdm.graph import GraphSet
from oc_ocdm.storer import Storer
from oc_ocdm.support import create_date
from rdflib import URIRef
import networkx as nx


def get_journal_data(journal_issn, i_am_polite):
    journal_data = requests.get(url = f'http://api.crossref.org/journals/{{{journal_issn}}}/works?mailto={i_am_polite}')
    journal_data_json = journal_data.json()
    return journal_data_json


def get_all_references_from_journal(journal_data_json):
    journal_data_items = journal_data_json["message"]["items"]
    all_references = list()
    for item in journal_data_items:
        references = requests.get(url = f'https://w3id.org/oc/index/coci/api/v1/references/{item["DOI"]}?format=json')
        references_json = references.json()
        all_references.append(references_json)
    return all_references


def update_graph(journal_data_json, graphset):
    journal_data_items = journal_data_json["message"]["items"]
    for item in journal_data_items:
        scientometrics_br = scientometrics_graphset.add_br(item["link"][0]["URL"])
        scientometrics_br.has_title(item["title"][0])
        iso_date_string = create_date([item["published-print"]["date-parts"][0][0]])
        scientometrics_br.has_pub_date(iso_date_string)
        # for reference in item["reference"]:
        #     my_br.has_related_document(URIRef("http://related_document_uri/"))
    graphset.commit_changes()


# Crossref test
requests_cache.install_cache('cache')
issn_web_scientometrics = "1588-2861"
my_mail = "arcangelo.massari@studio.unibo.it"
journal_data = get_journal_data(issn_web_scientometrics, my_mail)

# REST API for COCI test
all_references = get_all_references_from_journal(journal_data)

# oc_ocdm test
scientometrics_graphset = GraphSet("https://arcangelo7.github.io/time_agnostic/")
update_graph(journal_data, scientometrics_graphset)

# Retrieved data dump
with open('data/scientometrics.json', 'w') as outfile:
    json.dump(journal_data, outfile)
with open('data/references.json', 'w') as outfile:
    json.dump(all_references, outfile)
storer = Storer(scientometrics_graphset)
storer.store_graphs_in_file("data/graph.json", "./")


