from dataset_builder import DatasetBuilder
from oc_ocdm.graph import GraphSet


scientometrics = DatasetBuilder("1588-2861", "arcangelo.massari@studio.unibo.it")
# scientometrics_graphset = scientometrics.update_graph()
scientometrics.dump_data('data/scientometrics.json')
# scientometrics.dump_dataset(scientometrics_graphset, "data/graph.json")


