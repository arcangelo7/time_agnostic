# time-agnostic-builder

Time-Agnostic Builder is a Python &ge;3.7 software to build an RDF dataset starting from the ISSN of a journal present on Crossref. The output dataset is compliant with the [OCDM v2.0.1](https://figshare.com/articles/Metadata_for_the_OpenCitations_Corpus/3443876) specification. It is agnostic about time because changes and provenance are tracked adopting the same data model: any past version can be read and retrieved along with its metadata.

## Getting started
Before starting, you need to make sure you have Python3.x installed on your computer, in addition, in order to correctly execute the Python-based scripts indicated in the methodology, you must install the required libraries defined in [requirements.txt](https://github.com/arcangelo7/time_agnostic/blob/main/requirements.txt). Please follow the official Python guidelines at https://wiki.python.org/moin/BeginnersGuide/ to check and eventually install Python and the required libraries locally on your machine.

The [tutorial.py](https://github.com/arcangelo7/time_agnostic/blob/main/tutorial.py) file in the repository's root directory contains usage examples of all the available methods. 

### Get data

Before building the dataset, you need to download the data from Crossref. To do this, use the `DatasetBuilder.get_journal_data_from_crossref` method, indicating the journal’s ISSN, an email, the path to save the data, and if you want to save logs on any running or network errors. For more information on why to indicate the email, see the [Crossref REST API etiquette](https://github.com/CrossRef/rest-api-doc/#etiquette). 
```python
JOURNAL_ISSN = "0138-9130"
EMAIL = "arcangelo.massari@studio.unibo.it"
DATA_PATH = "./data/scientometrics.json"

DatasetBuilder.get_journal_data_from_crossref(journal_issn=JOURNAL_ISSN, your_email=EMAIL, path=DATA_PATH, logs=True)
```

### Build the dataset
To build the dataset, instance the `DatasetBuilder` class, indicating the base URI, your ORCID in the `resp_agent` field, and the path to save the generated entities counters (`info_dir`). For more information about what an ORCID is and how to create one, consult [https://orcid.org/](https://orcid.org/).

Then, run `generate_graph`, specifying where the data obtained in the [previous step](#get-data) were saved.

To produce the provenance related to the dataset creation, use the `Support.generate_provenance` method, indicating the newly generated dataset (`graphset`), the base URI and the path to save the snapshot counters (`info_dir`).

```python
BASE_URI = "https://github.com/opencitations/time-agnostic-library/"
RESP_AGENT = "https://orcid.org/0000-0002-8420-0696"
INFO_DIR_GRAPH = "./info_dir/graph/"
INFO_DIR_PROV = "./info_dir/prov/"
DATA_PATH = "./data/scientometrics.json"

dataset_builder = DatasetBuilder(base_uri=BASE_URI, resp_agent=RESP_AGENT, info_dir=INFO_DIR_GRAPH)
scientometrics = dataset_builder.generate_graph(journal_data_path=DATA_PATH)
scientometrics_prov = Support.generate_provenance(graphset=scientometrics, base_iri=BASE_URI, info_dir=INFO_DIR_PROV)
```
