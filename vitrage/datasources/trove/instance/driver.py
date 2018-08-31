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

from oslo_log import log

from vitrage.datasources.trove.instance import TROVE_INSTANCE_DATASOURCE
from vitrage.datasources.trove import TroveDriverBase

LOG = log.getLogger(__name__)


class TroveInstanceDriver(TroveDriverBase):

    @staticmethod
    def get_event_types():
        return []

    def get_all(self, datasource_action):
        return self.make_pickleable(self._get_all_entities(),
                                    TROVE_INSTANCE_DATASOURCE,
                                    datasource_action,
                                    *self.properties_to_filter_out())

    def _get_all_entities(self):
        # TODO(bzurkowski): Add all_tenants option to Trove client
        # TODO(bzurkowski): Add detailed index endpoint to Trove API
        return self.client.instances.list(
            include_clustered=True, search_opts={'all_tenants': 1})
