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
log = logging.getLogger('zen.ScalityConnector')


class Connector(PythonDataSourcePlugin):
    proxy_attributes = (
        'zScalityUsername',
        'zScalityPassword',
    )

    status_maps = {
        'OK': 0,
        'WARNING': 3,
        'CRITICAL': 5,
    }

    state_maps = {
        'OK': 0,
    }

    @classmethod
    def config_key(cls, datasource, context):
        log.info('In config_key {} {} {} {}'.format(context.device().id,
                                                 datasource.getCycleTime(context),
                                                 context.id,
                                                 'ScalityConnector'))

        return (context.device().id,
                datasource.getCycleTime(context),
                context.id,
                'ScalityConnector'
        )

    @classmethod
    def params(cls, datasource, context):
        return {
            'connector_id': context.connector_id
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ScalityConnector collect')

        ds0 = config.datasources[0]
        url = 'https://{}/api/v0.1/volume_connectors/{}/'.format(config.id, ds0.params['connector_id'])
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
        connector_metrics = result['_items'][0]

        status_value = self.status_maps.get(connector_metrics['status'], 3)
        data['values'][comp_id]['connector_status'] = status_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': status_value,
            'eventKey': 'ConnectorStatus',
            'eventClassKey': 'ConnectorStatus',
            'summary': 'Connector {} - Status is {}'.format(comp_id, connector_metrics['status']),
            'message': 'Connector {} - Status is {}'.format(comp_id, connector_metrics['status']),
            'eventClass': '/Status',
        })

        state_value = 0
        for v in connector_metrics['status']:
            state_value = max(state_value, get(v, 3))
        data['values'][comp_id]['connector_status'] = status_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': state_value,
            'eventKey': 'ConnectorStatus',
            'eventClassKey': 'ConnectorStatus',
            'summary': 'Connector {} - State is {}'.format(comp_id, connector_metrics['state']),
            'message': 'Connector {} - State is {}'.format(comp_id, connector_metrics['state']),
            'eventClass': '/Status',
        })

        log.debug('AAA Node {} data: {}'.format(comp_id, data))

        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
