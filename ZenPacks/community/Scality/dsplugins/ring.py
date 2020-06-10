import json
import logging
import base64
import re

# Twisted Imports
from twisted.internet import reactor
from twisted.internet.defer import returnValue, DeferredSemaphore, DeferredList, inlineCallbacks
from twisted.web.client import getPage, Agent, readBody
from twisted.web.http_headers import Headers
from twisted.internet.error import TimeoutError

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from Products.ZenUtils.Utils import prepId

# Setup logging
log = logging.getLogger('zen.ScalityRing')


class Ring(PythonDataSourcePlugin):
    proxy_attributes = (
        'zScalityUsername',
        'zScalityPassword',
        'zScalityUseSSL',
    )

    status_maps = {
        'OK': 0,
        'WARNING': 3,
        'CRITICAL': 5,
    }

    state_maps = {
        'RUN': 0,                       # OK
        'BALANCING': 1,                 # WARNING
        'CONFIG MISMATCH': 2,
        'OFFLINE': 3,
        'DISK USAGE WARNING': 4,
        'LOW STORAGE': 5,
        'ARC_REBUILD_NOK': 6,           # WARNING / CRITICAL
        'MISSING NODE': 7,              # CRITICAL
        'INCOMPLETE': 8,
        'NOT STABILIZED': 9,
        'OUT OF SERVICE': 10,
        'DUPLICATE KEY': 11,
        'DISK FULL': 12,
        'SPLIT': 13,
        'LOOP': 14,
    }

    @classmethod
    def config_key(cls, datasource, context):
        log.info('In config_key {} {} {} {}'.format(context.device().id,
                                                 datasource.getCycleTime(context),
                                                 context.id,
                                                 'ScalityRing'))

        return (context.device().id,
                datasource.getCycleTime(context),
                context.id,
                'ScalityRing'
        )

    @classmethod
    def params(cls, datasource, context):
        return {
            'ring_name': context.title
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ScalityRing collect')

        ds0 = config.datasources[0]
        scheme = 'https' if ds0.zScalityUseSSL else 'http'
        url = '{}://{}/api/v0.1/rings/{}/'.format(scheme, config.id, ds0.params['ring_name'])
        # log.debug('AAA : url : {}'.format(url))
        basicAuth = base64.encodestring('{}:{}'.format(ds0.zScalityUsername, ds0.zScalityPassword))
        authHeader = "Basic " + basicAuth.strip()

        agent = Agent(reactor)
        headers = {
            "Accept": ['application/json'],
            "Authorization": [authHeader],
        }
        try:
            response = yield agent.request('GET', url, Headers(headers))
            response_body = yield readBody(response)
            response_body = json.loads(response_body)
        except Exception as e:
            log.exception('{}: failed to get ring data for {}'.format(config.id, ds0))
            log.exception('{}: Exception: {}'.format(config.id, e))

        returnValue(response_body)

    def onSuccess(self, result, config):
        log.debug('Success job - result is {}'.format(result))
        data = self.new_data()

        datasource = config.datasources[0]
        comp_id = datasource.component
        ring_metrics = result['_items'][0]

        for dp_id, dp_name in [(x.id, x.dpName) for x in datasource.points]:
            if dp_id in ['status', 'state', 'planning_growth_month']:
                continue
            data['values'][comp_id][dp_name] = (ring_metrics[dp_id], 'N')

        # Forecast
        data['values'][comp_id]['ring_planning_growth_month'] = ring_metrics['planning_usage_growth'] / \
                                                                ring_metrics['planning_used_capacity_age'] * 30

        # Status
        status_value = self.status_maps.get(ring_metrics['status'], 3)
        data['values'][comp_id]['ring_status'] = status_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': status_value,
            'eventKey': 'RingStatus',
            'eventClassKey': 'RingStatus',
            'summary': 'Ring {} - Status is {}'.format(comp_id, ring_metrics['status']),
            'message': 'Ring {} - Status is {}'.format(comp_id, ring_metrics['status']),
            'eventClass': '/Status/Scality/Ring',
        })

        # State
        # log.debug('AAA : state: {}'.format(ring_metrics['state']))
        # log.debug('AAA : state: {}'.format(type(ring_metrics['state'])))
        if ring_metrics['state'] == ["RUN"]:
            state_severity_value = 0
        else:
            state_severity_value = 3
        state_value = max([self.state_maps.get(s, -1) for s in ring_metrics['state']])
        data['values'][comp_id]['ring_state'] = state_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': state_severity_value,
            'eventKey': 'RingState',
            'eventClassKey': 'RingState',
            'summary': 'Ring {} - State is {}'.format(comp_id, ', '.join(ring_metrics['state'])),
            'message': 'Ring {} - State is {}'.format(comp_id, ', '.join(ring_metrics['state'])),
            'eventClass': '/Status/Scality/Ring',
        })
        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
