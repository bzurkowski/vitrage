# Copyright 2018 - Trove team
#
# Licensed under the Apache License, Version 2.0 (the "License"); you may
# not use this file except in compliance with the License. You may obtain
# a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
# WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
# License for the specific language governing permissions and limitations
# under the License.

from oslo_log import log as logging

from vitrage.common.constants import DatasourceProperties as DSProps
from vitrage.common.constants import EdgeLabel
from vitrage.common.constants import EntityCategory
from vitrage.common.constants import VertexProperties as VProps
from vitrage.datasources.nova.instance import NOVA_INSTANCE_DATASOURCE
from vitrage.datasources.resource_transformer_base import \
    ResourceTransformerBase
from vitrage.datasources import transformer_base as tbase
from vitrage.datasources.trove.instance import TROVE_INSTANCE_DATASOURCE
from vitrage.datasources.trove.properties import \
    TroveInstanceProperties as TProps
import vitrage.graph.utils as graph_utils

LOG = logging.getLogger(__name__)


class TroveInstanceTransformer(ResourceTransformerBase):

    def _create_snapshot_entity_vertex(self, entity_event):
        entity_id = entity_event[TProps.ID]
        name = entity_event[TProps.NAME]
        state = entity_event[TProps.STATUS]
        timestamp = entity_event[TProps.UPDATE_TIMESTAMP]
        project_id = entity_event[TProps.PROJECT_ID]
        return self._create_vertex(entity_event, entity_id, name, state,
                                   timestamp, project_id)

    def _create_update_entity_vertex(self, entity_event):
        LOG.warning('Push updates are not supported yet for Trove Instances.')

    def _create_snapshot_neighbors(self, entity_event):
        return self._create_trove_neighbors(entity_event)

    def _create_update_neighbors(self, entity_event):
        return self._create_trove_neighbors(entity_event)

    def _create_entity_key(self, entity_event):
        entity_id = self._get_entity_id(entity_event)
        key_fields = self._key_values(TROVE_INSTANCE_DATASOURCE, entity_id)
        return tbase.build_key(key_fields)

    def _get_entity_id(self, entity_event):
        if tbase.is_update_event(entity_event):
            return entity_event['instance_id']
        return entity_event['id']

    def _create_vertex(self, entity_event, entity_id, name, state,
                       update_timestamp, project_id):
        metadata = {
            VProps.NAME: name,
            VProps.PROJECT_ID: project_id
        }
        sample_timestamp = entity_event[DSProps.SAMPLE_DATE]
        return graph_utils.create_vertex(
            self._create_entity_key(entity_event),
            vitrage_category=EntityCategory.RESOURCE,
            vitrage_type=TROVE_INSTANCE_DATASOURCE,
            vitrage_sample_timestamp=sample_timestamp,
            entity_id=entity_id,
            update_timestamp=update_timestamp,
            entity_state=state,
            metadata=metadata)

    def _create_trove_neighbors(self, entity_event):
        server_instance_id = entity_event['server_id']
        neighbours = [self._create_neighbor(entity_event,
                                            server_instance_id,
                                            NOVA_INSTANCE_DATASOURCE,
                                            EdgeLabel.CONTAINS,
                                            is_entity_source=True)]
        return neighbours

    @staticmethod
    def get_vitrage_type():
        return TROVE_INSTANCE_DATASOURCE
