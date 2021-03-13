import requests, requests_cache, json, urllib
from oc_ocdm.graph import GraphSet
from oc_ocdm.storer import Storer
from oc_ocdm.support import create_date
from rdflib import URIRef
from tqdm import tqdm

class DatasetBuilder(object):
    def get_journal_data_from_crossref(self, journal_issn, your_email, path, small=False):
        requests_cache.install_cache('cache/crossref_cache')
        if small:
            journal_data = requests.get(url = f'http://api.crossref.org/journals/{{{journal_issn}}}/works?mailto={your_email}').json()
        else:
            journal_data = requests.get(url = f'http://api.crossref.org/journals/{{{journal_issn}}}/works?cursor=*&mailto={your_email}').json()
            next_cursor = journal_data["message"]["next-cursor"]
            total_results = journal_data["message"]["total-results"]
            pbar = tqdm(total=total_results)
            cursors = set()
            while next_cursor not in cursors:
                cursors.add(next_cursor)
                next_chunk = requests.get(url = f'http://api.crossref.org/journals/{{{journal_issn}}}/works?cursor={urllib.parse.quote(next_cursor)}&mailto={your_email}').json()
                next_cursor = next_chunk["message"]["next-cursor"]
                items_retrieved = next_chunk["message"]["items"]
                journal_data["message"]["items"].extend(items_retrieved)
                pbar.update(20)
            pbar.close()
        with open(path, 'w') as outfile:
            print("Writing to file...")
            json.dump(journal_data, outfile, sort_keys=True, indent=4)
    
    def get_citation_data_from_coci(self, journal_data_path, path):
        total_references = dict()
        requests_cache.install_cache('cache/coci_cache')
        with open(journal_data_path) as journal_data:
            journal_item = json.load(journal_data)["message"]["items"]
            pbar = tqdm(total=len(journal_item))
            for item in journal_item:
                references = requests.get(url = f'https://w3id.org/oc/index/coci/api/v1/references/{item["DOI"]}?format=json').json()
                references_with_metadata = list()
                for reference in references:
                    metadata = requests.get(url = f'https://w3id.org/oc/index/coci/api/v1/metadata/{reference["cited"]}?format=json').json()
                    reference["cited_metadata"] = metadata[0]
                    references_with_metadata.append(reference)
                total_references[item["DOI"]] = references_with_metadata
                pbar.update(1)
        pbar.close()
        with open(path, 'w') as outfile:
            print("Writing to file...")
            json.dump(total_references, outfile, sort_keys=True, indent=4)

    def _manage_citations(self, references, graphset, item, citing_entity, your_orcid):
        for reference in references[item["DOI"]]:
            # Identifier
            reference_id = graphset.add_id(your_orcid)
            reference_id.create_doi(reference["cited"])
            # BibliographicResource
            reference_br = graphset.add_br(your_orcid)
            reference_br.create_journal_article()
            reference_br.has_identifier(reference_id)
            reference_br.has_title(reference["cited_metadata"]["title"])
            if len(reference["cited_metadata"]["year"]) > 0:
                iso_date_string = create_date([int(reference["cited_metadata"]["year"])])
                reference_br.has_pub_date(iso_date_string)
            citing_entity.has_citation(reference_br)
            # ResourceEmbodiment
            reference_re = graphset.add_re(your_orcid)
            if len(reference["cited_metadata"]["page"]) > 0:
                reference_re.has_starting_page(reference["cited_metadata"]["page"].split("-")[0])
                reference_re.has_ending_page(reference["cited_metadata"]["page"].split("-")[1])
            if len(reference["cited_metadata"]["oa_link"]) > 0:
                reference_re.has_url(URIRef(reference["cited_metadata"]["oa_link"]))
            reference_br.has_format(reference_re)
            # Citation
            reference_ci = graphset.add_ci(your_orcid)
            if reference["author_sc"] == "yes":
                reference_ci.create_author_self_citation()
            if reference["journal_sc"] == "yes":
                reference_ci.create_journal_self_citation()
            if reference["author_sc"] == "no" and reference["journal_sc"] == "no":
                reference_ci.create_distant_citation()
            reference_ci.has_citing_entity(citing_entity)
            reference_ci.has_cited_entity(reference_br)
            reference_ci.has_citation_creation_date(reference["creation"])
            reference_ci.has_citation_time_span(reference["timespan"])
    
    def create_graph(self, journal_data_path, citation_data_path, your_orcid):
        journal_graphset = GraphSet("https://arcangelo7.github.io/time_agnostic/")
        with open(journal_data_path) as journal_data, open(citation_data_path) as citation_data:
            references = json.load(citation_data)
            journal_data_items = json.load(journal_data)["message"]["items"]
            journal_item = next((item for item in journal_data_items if item["type"] == "journal"), None)
            if journal_item is not None:
                journal_br = journal_graphset.add_br(your_orcid)
                journal_br.create_journal()
                journal_id = journal_graphset.add_id(your_orcid)
                journal_id.create_issn(journal_item["ISSN"][0])
                journal_br.has_identifier(journal_id)
                journal_br.has_title(journal_item["title"][0])
                journal_re = journal_graphset.add_re(your_orcid)
                journal_re.create_print_embodiment()
                journal_re.create_digital_embodiment()
                journal_re.has_url(URIRef(journal_item["URL"]))
                journal_br.has_format(journal_re)
            pbar = tqdm(total=len(journal_data_items))
            for item in journal_data_items:
                # Identifier
                item_id = journal_graphset.add_id(your_orcid)
                item_id.create_doi(item["DOI"])
                # BibliographicResource
                if item["type"] != "journal":
                    item_br = journal_graphset.add_br(your_orcid)  
                    item_br.create_journal_article()
                    item_br.has_identifier(item_id)
                    item_br.has_title(item["title"][0])
                    if "subtitle" in item:
                        item_br.has_subtitle(item["subtitle"][0])
                    # ResourceEmbodiment
                    item_re = journal_graphset.add_re(your_orcid)
                    if "published-online" in item:
                        pub_date = item["published-online"]["date-parts"][0][0]
                        item_re.create_digital_embodiment()
                    if "published-print" in item:
                        pub_date = item["published-print"]["date-parts"][0][0]
                        item_re.create_print_embodiment()
                    if "link" in item:
                        item_re.has_media_type(URIRef("https://www.iana.org/assignments/media-types/" + item["link"][0]["content-type"]))
                    if "page" in item:
                        item_re.has_starting_page(item["page"].split("-")[0])
                        item_re.has_ending_page(item["page"].split("-")[1])
                    item_re.has_url(URIRef(item["URL"]))
                    iso_date_string = create_date([pub_date])
                    item_br.has_pub_date(iso_date_string)
                    if journal_item is not None:
                        item_br.is_part_of(journal_br)
                    item_br.has_format(item_re)
                # ResponsibleAgent
                if "author" in item:
                    for author in item["author"]:
                        item_ra = journal_graphset.add_ra(your_orcid)
                        if "ORCID" in author:
                            author_id = journal_graphset.add_id(your_orcid)
                            author_id.create_orcid(author["ORCID"])
                            item_ra.has_identifier(author_id)
                        if "given" in author:
                            item_ra.has_given_name(author["given"])
                        if "family" in author:
                            item_ra.has_family_name(author["family"])
                        if "given" in author and "family" in author:
                            item_ra.has_name(author["given"] + " " + author["family"])
                        # AgentRole
                        author_ar = journal_graphset.add_ar(your_orcid)
                        author_ar.create_author()
                        author_ar.is_held_by(item_ra)
                        item_br.has_contributor(author_ar)
                self._manage_citations(references, journal_graphset, item, item_br, your_orcid)
                pbar.update(1)
        journal_graphset.commit_changes()
        pbar.close()
        return journal_graphset
    
    def dump_dataset(self, data, path):
        storer = Storer(data)
        storer.store_graphs_in_file(path, "./")
