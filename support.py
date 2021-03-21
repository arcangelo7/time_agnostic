import os, zipfile, json, time
from oc_ocdm.storer import Storer

class Support(object):
    def _zipdir(self, path, ziph):
        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d != "small"]
            for file in files:
                ziph.write(os.path.join(root, file), os.path.relpath(os.path.join(root, file), os.path.join(path, '..')))
    
    def zip_data(self, path):
        zipf = zipfile.ZipFile('output.zip', 'w', zipfile.ZIP_DEFLATED)
        self._zipdir(path, zipf)
        zipf.close()
    
    def minify_json(self, path):
        file_data = open(path, "r", encoding="utf-8").read()
        json_data = json.loads(file_data) 
        json_string = json.dumps(json_data, separators=(',', ":")) 
        path = str(path).replace(".json", "")
        new_path = "{0}_minify.json".format(path)
        open(new_path, "w+", encoding="utf-8").write(json_string) 

    def measure_runtime(self, func):
        start = time.time()
        func()
        end = time.time()
        print(end - start)

    def dump_dataset(self, data, path):
        storer = Storer(data)
        storer.store_graphs_in_file(path, "./")
    
    def dump_json(self, json_data, path):
        with open(path, 'w') as outfile:
            print("Writing to file...")
            json.dump(json_data, outfile, sort_keys=True, indent=4)
