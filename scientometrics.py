import requests, json
from oc_ocdm.graph import GraphSet

def get_all_references_from_journal(journal_issn, i_am_polite):
    journal_data = requests.get(url = f'http://api.crossref.org/journals/{{{journal_issn}}}/works?mailto={i_am_polite}')
    journal_data_json = journal_data.json()
    journal_data_items = journal_data_json["message"]["items"]
    all_references = list()
    for item in journal_data_items:
        references = requests.get(url = f'https://w3id.org/oc/index/coci/api/v1/references/{item["DOI"]}?format=json')
        try:
            references_json = references.json()
            all_references.append(references_json)
        except json.decoder.JSONDecodeError:
            pass
    return all_references

issn_web_scientometrics = "1588-2861"
my_mail = "arcangelo.massari@studio.unibo.it"
all_references = get_all_references_for_journal(issn_web_scientometrics, my_mail)
with open('data/references.json', 'w') as outfile:
    json.dump(all_references, outfile)