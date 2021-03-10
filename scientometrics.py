from dataset_builder import DatasetBuilder
from oc_ocdm.graph import GraphSet


scientometrics = DatasetBuilder("1588-2861", "arcangelo.massari@studio.unibo.it")
all_references = scientometrics.get_all_references_from_journal()
scientometrics_graphset = scientometrics.update_graph()
scientometrics.dump_data('data/scientometrics.json')
scientometrics.dump_data('data/references.json', all_references)
scientometrics.dump_dataset(scientometrics_graphset, "data/graph.json")


