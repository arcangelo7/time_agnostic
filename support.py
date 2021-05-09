import os, zipfile, json, time, requests, requests_cache, rdflib
from requests import Session
from zipfile import ZipFile
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from oc_ocdm.storer import Storer
from oc_ocdm.reader import Reader
from oc_ocdm.graph import GraphSet
from oc_ocdm.prov import ProvSet
from rdflib import Graph
from rdflib.query import ResultParser, ResultSerializer
from rdflib.plugin import register, Serializer, Parser
from rdflib.plugins.sparql.results.csvresults import CSVResultSerializer, CSVResultParser

class Support(object):
    def _requests_retry_session(
        self,
        tries=1,
        status_forcelist=(500, 502, 504, 520, 521, 522),
        session=None
    ) -> Session:
        session = session or requests.Session()
        retry = Retry(
            total=tries,
            read=tries,
            connect=tries,
            status_forcelist=status_forcelist,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    def handle_request(self, url:str, cache_path:str, error_log_dict:dict) -> None:
        requests_cache.install_cache(cache_path)
        try:
            data = self._requests_retry_session().get(url, timeout=60)
            if data.status_code == 200:
                return data.json()
            else:
                error_log_dict[url] = data.status_code
        except Exception as e:
            error_log_dict[url] = str(e)

    def _zipdir(self, path:str, ziph:ZipFile) -> None:
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d != "small"]
            for file in files:
                ziph.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), os.path.join(path, '..')))
    
    def zip_data(self, path:str) -> None:
        zipf = zipfile.ZipFile('output.zip', 'w', zipfile.ZIP_DEFLATED)
        self._zipdir(path, zipf)
        zipf.close()
    
    def minify_json(self, path:str) -> None:
        print(f"[Support: INFO] Minifing file {path}")
        file_data = open(path, "r", encoding="utf-8").read()
        json_data = json.loads(file_data) 
        json_string = json.dumps(json_data, separators=(',', ":")) 
        path = str(path).replace(".json", "")
        new_path = "{0}_minify.json".format(path)
        open(new_path, "w+", encoding="utf-8").write(json_string) 

    def measure_runtime(self, func:callable) -> None:
        start = time.time()
        func()
        end = time.time()
        print(end - start)

    @staticmethod
    def dump_dataset(data:GraphSet, path:str) -> None:
        storer = Storer(data)
        storer.store_graphs_in_file(file_path=path, context_path=None)
    
    @staticmethod
    def upload_dataset(data:GraphSet, ts_url:str="http://localhost:9999/blazegraph/sparql") -> None:
        storer = Storer(data)
        storer.upload_all(ts_url)
    
    @staticmethod
    def upload_and_store_dataset(data:GraphSet, path:str, ts_url:str="http://localhost:9999/blazegraph/sparql", base_iri:str="https://github.com/arcangelo7/time_agnostic/") -> None:
        storer = Storer(data)
        storer.store_graphs_in_file(file_path=path, context_path=None)
        storer.upload_all(ts_url)
    
    def dump_json(self, json_data:dict, path:str) -> None:
        with open(path, 'w') as outfile:
            print("[Support: INFO] Writing to file")
            json.dump(json_data, outfile, sort_keys=True, indent=4)
    
    def get_graph_from_file(self, rdf_file_path:str, base_iri:str, resp_agent:str, info_dir:str) -> GraphSet:
        print(f"[Support: INFO] Importing GraphSet from {rdf_file_path}")
        reader = Reader()
        rdf_file = reader.load(rdf_file_path)
        graphset = GraphSet(base_iri=base_iri, info_dir=info_dir, wanted_label=False)
        reader.import_entities_from_graph(graphset, rdf_file, resp_agent, enable_validation=False)
        return graphset

    @staticmethod
    def generate_provenance(graphset:GraphSet, base_iri:str, info_dir:str = "") -> ProvSet:
        print("Generating Provenance...")
        provset = ProvSet(prov_subj_graph_set=graphset, base_iri=base_iri, info_dir=info_dir, wanted_label=False)
        provset.generate_provenance()
        return provset

    



