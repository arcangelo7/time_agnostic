import os, zipfile, json, time, requests, requests_cache
from requests import Session
from zipfile import ZipFile
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from oc_ocdm.storer import Storer
from oc_ocdm.reader import Reader
from oc_ocdm.graph import GraphSet

class Support(object):
    def _requests_retry_session(
        self,
        retries=3,
        backoff_factor=0.3,
        status_forcelist=(500, 502, 504, 520, 521),
        session=None
    ) -> Session:
        session = session or requests.Session()
        retry = Retry(
            total=retries,
            read=retries,
            connect=retries,
            backoff_factor=backoff_factor,
            status_forcelist=status_forcelist,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        return session
    
    def handle_request(self, url:str, cache_path:str, error_log_dict:dict):
        requests_cache.install_cache(cache_path)
        try:
            data = self._requests_retry_session().get(url, timeout=60)
            if data.status_code == 200:
                return data.json()
            else:
                error_log_dict[url] = data.status_code
        except Exception as e:
            error_log_dict[url] = str(e)

    def _zipdir(self, path:str, ziph:ZipFile):
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d != "small"]
            for file in files:
                ziph.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), os.path.join(path, '..')))
    
    def zip_data(self, path:str):
        zipf = zipfile.ZipFile('output.zip', 'w', zipfile.ZIP_DEFLATED)
        self._zipdir(path, zipf)
        zipf.close()
    
    def minify_json(self, path:str):
        print(f"[Support: INFO] Minifing file {path}")
        file_data = open(path, "r", encoding="utf-8").read()
        json_data = json.loads(file_data) 
        json_string = json.dumps(json_data, separators=(',', ":")) 
        path = str(path).replace(".json", "")
        new_path = "{0}_minify.json".format(path)
        open(new_path, "w+", encoding="utf-8").write(json_string) 

    def measure_runtime(self, func:callable):
        start = time.time()
        func()
        end = time.time()
        print(end - start)

    def dump_dataset(self, data:GraphSet, path:str):
        storer = Storer(data)
        storer.store_graphs_in_file(path, "./")
        # data.commit_changes()
    
    def upload_dataset(self, data:GraphSet, ts_url:str="http://localhost:9999/blazegraph/sparql"):
        storer = Storer(data)
        storer.upload_all(ts_url)
    
    def dump_json(self, json_data:dict, path:str):
        with open(path, 'w') as outfile:
            print("Writing to file...")
            json.dump(json_data, outfile, sort_keys=True, indent=4)
    
    def get_graph_from_file(self, rdf_file_path:str, base_iri:str, resp_agent:str, info_dir:str) -> GraphSet:
        print(f"[Support: INFO] Importing GraphSet from {rdf_file_path}")
        reader = Reader()
        rdf_file = reader.load(rdf_file_path)
        graphset = GraphSet(base_iri=base_iri, info_dir=info_dir, wanted_label=False)
        reader.import_entities_from_graph(graphset, rdf_file, resp_agent, enable_validation=False)
        return graphset
