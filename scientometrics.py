from dataset_builder import DatasetBuilder
from oc_ocdm.graph import GraphSet


scientometrics = DatasetBuilder("1588-2861", "arcangelo.massari@studio.unibo.it")
# scientometrics.dump_data('data/scientometrics.json')
scientometrics_graphset = scientometrics.create_graph_from_crossref_data("https://orcid.org/0000-0002-8420-0696")
scientometrics.dump_dataset(scientometrics_graphset, "data/graph.json")


