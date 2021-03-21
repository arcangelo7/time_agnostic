import re
from support import Support
from tqdm import tqdm
from rdflib import URIRef
from oc_ocdm.support.query_utils import get_update_query
from datetime import datetime

class DatasetAutoEnhancer(object):
    def __init__(self, dataset, prov_graph, resp_agent):
        self.dataset = dataset
        self.prov_graph = prov_graph 
        self.resp_agent = resp_agent
    
    def _generate_snaphot(self, entity):
        se = self.prov_graph.add_se(entity)
        timestamp = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        se.has_generation_time(timestamp)
        se.is_snapshot_of(entity)
        update_query = get_update_query(entity)
        se.has_update_action(update_query[0])
        se.has_resp_agent(URIRef(self.resp_agent))
        se.has_primary_source(URIRef("http://api.crossref.org"))
        # Invalidate previous spanshot
        cur_se_number = re.search("\/se\/\d$", se.res).group(0)
        cur_se_number = int(re.search("\d", cur_se_number).group(0))
        prev_se_uri = se.res.replace(f"/se/{cur_se_number}", f"/se/{cur_se_number-1}")
        prev_se = self.prov_graph.get_entity(URIRef(prev_se_uri))
        prev_se.has_invalidation_time(timestamp)
        se.derives_from(prev_se)

    def merge_by_id(self, entities_set):
        switcher = {
                "br": self.dataset.get_br,
                "ra": self.dataset.get_ra
        }
        for entity in entities_set:
            entities = switcher[entity]()
            ids_found = dict()
            pbar = tqdm(total=len(entities_set))
            for entity_obj in entities:
                entity_ids = entity_obj.get_identifiers()
                if len(entity_ids) > 0:
                    entity_id = entity_ids[0]
                else:
                    pbar.update(1)
                    continue
                entity_id_literal = entity_id.get_literal_value()
                if entity_id_literal in ids_found:
                    prev_entity = self.dataset.get_entity(URIRef(ids_found[entity_id_literal].res))
                    try:
                        prev_entity.merge(entity_obj)
                    except TypeError:
                        print(prev_entity, entity_obj)
                        pass
                    self._generate_snaphot(entity_obj)
                    self._generate_snaphot(prev_entity)
                ids_found[entity_id_literal] = entity_obj
                pbar.update(1)
            self.dataset.commit_changes()
            pbar.close()
        return self.dataset, self.prov_graph




    