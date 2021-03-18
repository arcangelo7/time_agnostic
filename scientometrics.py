from dataset_builder import DatasetBuilder

scientometrics = DatasetBuilder("https://github.com/arcangelo7/time_agnostic/", "https://orcid.org/0000-0002-8420-0696")
# scientometrics.get_journal_data_from_crossref("0138-9130", "arcangelo.massari@studio.unibo.it", "data/scientometrics.json")
# scientometrics_graphset = scientometrics.create_graph("data/small/scientometrics.json")
# scientometrics.dump_dataset(scientometrics_graphset[0], "data/small/graph.json")
# scientometrics.dump_dataset(scientometrics_graphset[1], "data/prov.json")
# scientometrics_dataset = scientometrics.create_dataset("Scientometrics", "Dataset about the Scientometrics journal compliant with the Open Citation Data Model")
# scientometrics.dump_dataset(scientometrics_dataset, "data/dataset.json")
scientometrics.zip_data("./data/")





