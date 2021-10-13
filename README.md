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

### Automatic enhancements

All the features to automatically improve the dataset use the `DatasetAutoEnhancer` class. To instantiate it, specity the base URI, your ORCID (`resp_agent`), and the path where the entity counter was previously saved (`info_dir`). 
```python
BASE_URI = "https://github.com/opencitations/time-agnostic-library/"
RESP_AGENT = "https://orcid.org/0000-0002-8420-0696"
INFO_DIR_GRAPH = "./info_dir/graph/"

enhancer = DatasetAutoEnhancer(base_uri=BASE_URI, resp_agent=RESP_AGENT, info_dir=INFO_DIR_GRAPH)
```

#### Add citations from COCI
This step adds to the dataset the references present in COCI and not in the graph of level zero derived from Crossref in the [previous step](build-the-dataset). 
[COCI](https://opencitations.net/index/coci) is the OpenCitations Index Of Crossref Open DOI To DOI Citations, an RDF dataset containing metadata on all the citations to DOI-identified works on Crossref. One might wonder why COCI includes additional citations if it is derived from Crossref. The reason is that COCI issues limited references that Crossref makes available only in the paid version. In fact, since 1 January 2018, limited references have been distributed by Crossref without a license, and they are in the public domain ([https://www.crossref.org/documentation/content-registration/descriptive-metadata/references/](https://www.crossref.org/documentation/content-registration/descriptive-metadata/references/)). At any rate, COCI does not index Crossref references that are closed.

For this purpose, after instantiating the `DatasetAutoEnhancer` class (see [Automatic enhancements](#automatic-enhancements)), run the `add_coci_data` method on that instance, specifying the journal ISSN.

```python
JOURNAL_ISSN = "0138-9130"

scientometrics_plus_coci = enhancer.add_coci_data(journal_issn=JOURNAL_ISSN)
```

### Add Crossref data about cited entities

It is possible to enrich the DOI-identified resources extracted from the reference list of the works published by the journal considered. This step adds information regarding their publisher, typology, title, subtitle, publication date, authors, volume, issue, and resource embodiment. These details are obtained from Crossref.

To this end, after instantiating the `DatasetAutoEnhancer` class (see [Automatic enhancements](#automatic-enhancements)), run the `add_crossref_reference_data` method on that instance.

```python
crossref_reference_data = enhancer.add_crossref_reference_data()
```

### Add references reported by Crossref without a DOI by heuristically retrieving those DOI names

Many items in the Crossref reference lists are reported without a DOI, making it difficult to identify them uniquely. This phase aims to recover those DOI names and reintegrate the related entities into the dataset. Such shortcomings occur because reference records are not double-checked by Crossref and are directly provided by publishers. They may be incomplete or even contain errors. The procedure adopted is based on a heuristic borrowed from chapter 3.2 and especially from the appendix of the article *Large-scale comparison of bibliographic data sources: Scopus, Web of Science, Dimensions, Crossref, and Microsoft Academic* ([Visser, van Eck, and Waltman 2021](https://doi.org/10.1162/qss_a_00112)). 

In order to add those missed references to the dataset, after instantiating the `DatasetAutoEnhancer` class (see [Automatic enhancements](#automatic-enhancements)), run the `add_reference_data_without_doi` method on that instance, specifying the journal data path.

```python
DATA_PATH = "./data/scientometrics.json"

heuristic = enhancer.add_reference_data_without_doi(journal_data_path=DATA_PATH)
```

### Merge

This step involves merging resources associated with identifiers having the same literal value. It may be the case for two publishers with identical ISSN, two authors with the same ORCID, or two bibliographical resources with the same DOI name. 

For this purpose, after instantiating the `DatasetAutoEnhancer` class (see [Automatic enhancements](#automatic-enhancements)), run the `merge_by_id` method on that instance. Also, specify in a dictionary which types of entities you want to merge and based on which identifiers (`type_and_identifier_scheme`).
> :warning: Depending on the number of duplicates, this operation may require a considerable amount of RAM. Specify in the `available_ram` field how much RAM you have available in GB. Once the process has filled that amount of RAM, it will return the partial output, which can be uploaded to a triplestore or saved to a file (see [Store the dataset and its provenance](#store-the-dataset-and-its-provenance)). After that, you can relaunch the function, which will work on the new dataset state.

```python
scientometrics_merged = enhancer.merge_by_id(type_and_identifier_scheme={
    "http://xmlns.com/foaf/0.1/Agent": "http://purl.org/spar/datacite/orcid",
    "http://purl.org/spar/fabio/Expression": "http://purl.org/spar/datacite/doi",
}, available_ram=8)
```

### Generate provenance and track changes

### Store the dataset and its provenance
