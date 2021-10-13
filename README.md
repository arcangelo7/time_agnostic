# time-agnostic-builder

Time-Agnostic Builder is a Python &ge;3.7 software to build an RDF dataset starting from the ISSN of a journal present on Crossref. The output dataset is compliant with the [OCDM v2.0.1](https://figshare.com/articles/Metadata_for_the_OpenCitations_Corpus/3443876) specification. It is agnostic about time because changes and provenance are tracked adopting the same data model: any past version can be read and retrieved along with its metadata.

## Getting started
Before starting, you need to make sure you have Python3.x installed on your computer, in addition, in order to correctly execute the Python-based scripts indicated in the methodology, you must install the required libraries defined in requirements.txt. Please follow the official Python guidelines at https://wiki.python.org/moin/BeginnersGuide/ to check and eventually install Python and the required libraries locally on your machine.


The tutorial.py file in the repository's root directory contains usage examples of all available methods, accompanied by explanatory comments.
