# Copyright 2016 - Nokia
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

from collections import namedtuple

from oslo_log import log
from pyzabbix import ZabbixAPI

from vitrage.common.constants import DatasourceProperties as DSProps
from vitrage.common.constants import SyncMode
from vitrage.common import file_utils
from vitrage.datasources.alarm_driver_base import AlarmDriverBase
from vitrage.datasources.zabbix.properties import ZabbixProperties as ZProps
from vitrage.datasources.zabbix.properties import ZabbixTriggerStatus \
    as TriggerStatus
from vitrage.datasources.zabbix.properties import ZabbixTriggerValue \
    as TriggerValue
from vitrage.datasources.zabbix import ZABBIX_DATASOURCE

LOG = log.getLogger(__name__)


class ZabbixDriver(AlarmDriverBase):
    ServiceKey = namedtuple('ServiceKey', ['host_name', 'service'])
    conf_map = None

    def __init__(self, conf):
        super(ZabbixDriver, self).__init__()
        self.conf = conf
        if ZabbixDriver.conf_map is None:
            ZabbixDriver.conf_map =\
                ZabbixDriver._configuration_mapping(conf)
        self.client = None

    def _sync_type(self):
        return ZABBIX_DATASOURCE

    def _alarm_key(self, alarm):
        return self.ServiceKey(host_name=alarm[ZProps.RESOURCE_NAME],
                               service=alarm[ZProps.DESCRIPTION])

    def _get_alarms(self):
        zabbix_user = self.conf.zabbix.user
        zabbix_password = self.conf.zabbix.password
        zabbix_url = self.conf.zabbix.url

        if not zabbix_user:
            LOG.warning('Zabbix user is not defined')
            return []

        if not zabbix_password:
            LOG.warning('Zabbix password is not defined')
            return []

        if not zabbix_url:
            LOG.warning('Zabbix url is not defined')
            return []

        if not self.client:
            self.client = ZabbixAPI(zabbix_url)
            self.client.login(zabbix_user, zabbix_password)

        alarms = []
        valid_hosts = (host for host in
                       self.client.host.get(output=[ZProps.HOST])
                       if host[ZProps.HOST] in ZabbixDriver.conf_map)
        for host in valid_hosts:
            self._get_triggers_per_host(host, alarms)

        return alarms

    def _get_triggers_per_host(self, host, alarms):

        host_id = host[ZProps.HOST_ID]
        triggers = self.client.trigger.get(hostids=host_id,
                                           expandDescription=True)

        triggers_rawtexts = self._get_triggers_rawtexts(host_id)

        for trigger in triggers:
            trigger[ZProps.ZABBIX_RESOURCE_NAME] = host[ZProps.HOST]

            trigger_id = trigger[ZProps.TRIGGER_ID]
            trigger[ZProps.RAWTEXT] = triggers_rawtexts[trigger_id]
            alarms.append(trigger)

    def _get_triggers_rawtexts(self, host_id):

        output = [ZProps.TRIGGER_ID, ZProps.DESCRIPTION]
        triggers = self.client.trigger.get(hostids=host_id, output=output)

        return {trigger[ZProps.TRIGGER_ID]: trigger[ZProps.DESCRIPTION]
                for trigger in triggers}

    def _enrich_alarms(self, alarms):
        """Enrich zabbix alarm using zabbix configuration file

        converting Zabbix host name to Vitrage resource type and name

        :param alarms: Zabbix alarm
        :return: enriched alarm
        """

        for alarm in alarms:
            alarm[ZProps.VALUE] = self._get_value(alarm)

            zabbix_host = alarm[ZProps.ZABBIX_RESOURCE_NAME]
            vitrage_host = ZabbixDriver.conf_map[zabbix_host]
            alarm[ZProps.RESOURCE_TYPE] = vitrage_host[ZProps.RESOURCE_TYPE]

            vitrage_host_name = vitrage_host[ZProps.RESOURCE_NAME]
            alarm[ZProps.RESOURCE_NAME] = vitrage_host[ZProps.RESOURCE_NAME]
            alarm[ZProps.DESCRIPTION] = alarm[ZProps.DESCRIPTION].replace(
                zabbix_host,
                vitrage_host_name)

    def _is_erroneous(self, alarm):
        return alarm and \
            alarm[ZProps.VALUE] == TriggerValue.PROBLEM

    def _status_changed(self, new_alarm, old_alarm):

        if not (new_alarm and old_alarm):
            return False

        if new_alarm[ZProps.VALUE] != old_alarm[ZProps.VALUE]:
            return True

        if new_alarm[ZProps.VALUE] == TriggerValue.PROBLEM:
            return new_alarm[ZProps.PRIORITY] != old_alarm[ZProps.PRIORITY]

    def _is_valid(self, alarm):
        return alarm[ZProps.RESOURCE_TYPE] is not None and \
            alarm[ZProps.RESOURCE_NAME] is not None

    @staticmethod
    def _get_value(alarm):
        if alarm[ZProps.STATUS] == TriggerStatus.DISABLED:
            return TriggerValue.OK
        return alarm[ZProps.VALUE]

    @staticmethod
    def _configuration_mapping(conf):
        try:
            zabbix_config_file = conf.zabbix['config_file']
            zabbix_config = file_utils.load_yaml_file(zabbix_config_file)
            zabbix_config_elements = zabbix_config['zabbix']

            mappings = {}
            for element_config in zabbix_config_elements:
                mappings[element_config['zabbix_host']] = {
                    ZProps.RESOURCE_TYPE: element_config['type'],
                    ZProps.RESOURCE_NAME: element_config['name']
                }

            return mappings
        except Exception as e:
            LOG.exception('failed in init %s ', e)
            return {}

    @staticmethod
    def enrich_event(event, event_type):
        event[DSProps.EVENT_TYPE] = event_type

        if ZabbixDriver.conf_map:
            zabbix_host = event[ZProps.HOST]
            v_resource = ZabbixDriver.conf_map[zabbix_host]
            event[ZProps.RESOURCE_NAME] = v_resource[ZProps.RESOURCE_NAME]
            event[ZProps.RESOURCE_TYPE] = v_resource[ZProps.RESOURCE_TYPE]

        return ZabbixDriver.make_pickleable([event], ZABBIX_DATASOURCE,
                                            SyncMode.UPDATE)[0]

    @staticmethod
    def get_event_types(conf):
        return ['zabbix.alarm.ok', 'zabbix.alarm.problem']

    @staticmethod
    def get_update_method(conf):
        return conf[ZABBIX_DATASOURCE].update_method
