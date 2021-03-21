from dataset_builder import DatasetBuilder, DatasetEnhancer, Support

# Build
# scientometrics = DatasetBuilder("https://github.com/arcangelo7/time_agnostic/", "https://orcid.org/0000-0002-8420-0696")
# scientometrics.get_journal_data_from_crossref("0138-9130", "arcangelo.massari@studio.unibo.it", "data/scientometrics.json")
# scientometrics_graphset = scientometrics.generate_graph("data/small/scientometrics.json")
# scientometrics_provenance = scientometrics.generate_provenance(scientometrics_graphset)
# scientometrics.dump_dataset(scientometrics_graphset, "data/small/graph.json")
# scientometrics.dump_dataset(scientometrics_provenance, "data/prov.json")
# scientometrics_dataset = scientometrics.create_dataset("Scientometrics", "Dataset about the Scientometrics journal compliant with the Open Citation Data Model")
# scientometrics.dump_dataset(scientometrics_dataset, "data/dataset.json")
# scientometrics.zip_data("./data/")

# Enhance
# Support().minify_json("./data/small/graph.json")
dataset = DatasetEnhancer("https://github.com/arcangelo7/time_agnostic/", "https://orcid.org/0000-0002-8420-0696", "arcangelo.massari@studio.unibo.it")
dataset = dataset.get_dataset("./data/small/graph_minify.json")
dataset.get_be()





