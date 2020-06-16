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


class Volume(PythonDataSourcePlugin):
    proxy_attributes = (
        'zScalityUsername',
        'zScalityPassword',
        'zScalityUseSSL',
    )

    status_value_maps = {
        'OK': 0,
        'WARNING': 1,
        'NO CONNECTOR': 2,
        'CRITICAL': 3,
    }

    status_severity_maps = {
        'CRITICAL': 5,
        'WARNING': 3,
        'OK': 0,
        'NO CONNECTOR': 3,
    }

    @classmethod
    def config_key(cls, datasource, context):
        log.info('In config_key {} {} {} {}'.format(context.device().id,
                                                 datasource.getCycleTime(context),
                                                 context.id,
                                                 'ScalityVolume'))

        return (context.device().id,
                datasource.getCycleTime(context),
                context.id,
                'ScalityVolume'
        )

    @classmethod
    def params(cls, datasource, context):
        return {
            'volume_id': context.volume_id,
            'component_title': context.title
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ScalityRing collect')

        ds0 = config.datasources[0]
        scheme = 'https' if ds0.zScalityUseSSL else 'http'
        url = '{}://{}/api/v0.1/volumes/{}/'.format(scheme, config.id, ds0.params['volume_id'])
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
            log.exception('{}: failed to get server data for {}'.format(config.id, ds0))
            log.exception('{}: Exception: {}'.format(config.id, e))

        returnValue(response_body)

    def onSuccess(self, result, config):
        log.debug('Success job - result is {}'.format(result))
        data = self.new_data()

        datasource = config.datasources[0]
        comp_id = datasource.component
        comp_title = datasource.params['component_title']
        volume_metrics = result['_items'][0]

        status_value = self.status_value_maps.get(volume_metrics['status'], 3)
        status_severity = self.status_severity_maps.get(volume_metrics['status'], 3)
        data['values'][comp_id]['volume_status'] = status_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': status_severity,
            'eventKey': 'VolumeStatus',
            'eventClassKey': 'VolumeStatus',
            'summary': 'Volume {} - Status is {}'.format(comp_title, volume_metrics['status']),
            'message': 'Volume {} - Status is {}'.format(comp_title, volume_metrics['status']),
            'eventClass': '/Status/Scality/Volume',
        })

        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
