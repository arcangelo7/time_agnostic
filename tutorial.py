from dataset_builder import DatasetBuilder
from support import Support
from dataset_auto_enhancer import DatasetAutoEnhancer
from oc_ocdm.graph.graph_entity import GraphEntity

BASE_URI = "https://github.com/opencitations/time-agnostic-library/"
RESP_AGENT = "https://orcid.org/0000-0002-8420-0696"
INFO_DIR_GRAPH = "./db/info_dir/graph/"
INFO_DIR_PROV = "./db/info_dir/prov/"
TRIPLESTORE_DATA = "http://localhost:9999/blazegraph/sparql"
TRIPLESTORE_PROV = "http://localhost:19999/blazegraph/sparql"
JOURNAL_ISSN = "0138-9130"
EMAIL = "arcangelo.massari@studio.unibo.it"
DATA_PATH = "./data/scientometrics.json"

# GET DATA
DatasetBuilder.get_journal_data_from_crossref(journal_issn=JOURNAL_ISSN, your_email=EMAIL, path=DATA_PATH, logs=True)

# CREATE
dataset_builder = DatasetBuilder(base_uri=BASE_URI, resp_agent=RESP_AGENT, info_dir=INFO_DIR_GRAPH)
scientometrics = dataset_builder.generate_graph(journal_data_path=DATA_PATH)
scientometrics_prov = Support.generate_provenance(graphset=scientometrics, base_iri=BASE_URI, info_dir=INFO_DIR_PROV)
Support.upload_dataset(data=scientometrics, ts_url=TRIPLESTORE_DATA)
Support.upload_dataset(data=scientometrics_prov,ts_url=TRIPLESTORE_PROV)

enhancer = DatasetAutoEnhancer(base_uri=BASE_URI, resp_agent=RESP_AGENT, info_dir=INFO_DIR_GRAPH)

# COCI
scientometrics_plus_coci = enhancer.add_coci_data(journal_issn="0138-9130")
scientometrics_plus_coci_prov = Support.generate_provenance(graphset=scientometrics_plus_coci, base_iri="https://github.com/arcangelo7/time_agnostic/", info_dir="./db/final2_prov/info_dir/")
Support.upload_dataset(data=scientometrics_plus_coci, ts_url=TRIPLESTORE_DATA)
Support.upload_dataset(data=scientometrics_plus_coci_prov, ts_url=TRIPLESTORE_PROV)

# CROSSREF REFERENCE DATA
crossref_reference_data = enhancer.add_crossref_reference_data()
crossref_reference_data_prov = Support.generate_provenance(graphset=crossref_reference_data, base_iri="https://github.com/arcangelo7/time_agnostic/", info_dir="./db/final2_prov/info_dir/")
Support.upload_dataset(data=crossref_reference_data, ts_url=TRIPLESTORE_DATA)
Support.upload_dataset(data=crossref_reference_data_prov, ts_url=TRIPLESTORE_PROV)

# HEURISTIC
heuristic = enhancer.add_reference_data_without_doi(journal_data_path="data/scientometrics.json")
heuristic_prov = Support.generate_provenance(graphset=heuristic, base_iri="https://github.com/arcangelo7/time_agnostic/", info_dir="./db/final2_prov/info_dir/")
Support.upload_dataset(data=heuristic, ts_url=TRIPLESTORE_DATA)
Support.upload_dataset(data=heuristic_prov, ts_url=TRIPLESTORE_PROV)

# MERGE
scientometrics_merged = enhancer.merge_by_id(type_and_identifier_scheme={
    str(GraphEntity.iri_agent): str(GraphEntity.iri_orcid),
    str(GraphEntity.iri_expression): str(GraphEntity.iri_doi)
}, available_ram=25)
scientometrics_merged_prov = Support.generate_provenance(graphset=scientometrics_merged, base_iri=BASE_URI, info_dir=INFO_DIR_PROV)
Support.upload_dataset(data=scientometrics_merged, ts_url=TRIPLESTORE_DATA)
Support.upload_dataset(data=scientometrics_merged_prov, ts_url=TRIPLESTORE_PROV)