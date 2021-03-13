from dataset_builder import DatasetBuilder
from oc_ocdm.graph import GraphSet


scientometrics = DatasetBuilder()
# scientometrics.get_journal_data_from_crossref("0138-9130", "arcangelo.massari@studio.unibo.it", "./data/small/scientometrics.json", True)
# scientometrics.get_citation_data_from_coci("data/small/scientometrics.json", "data/small/references.json")
scientometrics_graphset = scientometrics.create_graph("data/small/scientometrics.json", "data/small/references.json", "https://orcid.org/0000-0002-8420-0696")
scientometrics.dump_dataset(scientometrics_graphset, "data/small/graph.json")


