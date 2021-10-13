# time-agnostic-builder

Time-Agnostic Builder is a Python &ge;3.7 software to build an RDF dataset starting from the ISSN of a journal present on Crossref. The output dataset is compliant with the [OCDM v2.0.1](https://figshare.com/articles/Metadata_for_the_OpenCitations_Corpus/3443876) specification. It is agnostic about time because changes and provenance are tracked adopting the same data model: any past version can be read and retrieved along with its metadata.
