
from rdflib import URIRef
from support import Support
from urllib.parse import quote

logs = dict()
api_call_uri = f"https://api.crossref.org/works/{quote('10.1002/(sici)1097-4571(199203)43:2<156::aid-asi8>3.0.co;2-u')}"

crossref_info = Support().handle_request(api_call_uri, "./cache/crossref_cache", logs)
URIRef(api_call_uri)