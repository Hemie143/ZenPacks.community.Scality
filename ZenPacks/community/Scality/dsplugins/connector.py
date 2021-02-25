import base64
import json
import logging

from ZenPacks.community.Scality.lib.utils import SkipCertifContextFactory
# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
# Twisted Imports
from twisted.internet import reactor
from twisted.internet.defer import returnValue, inlineCallbacks
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers

# Setup logging
log = logging.getLogger('zen.ScalityConnector')


class Connector(PythonDataSourcePlugin):
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

    state_value_maps = {
        'OK': 0,
        'NEED_RELOAD': 1,
        'CONFIG MISMATCH': 2,
        'CONFIG_MISMATCH': 2,
        'DOWN/OFFLINE': 3,
        'DOWN': 4,
        'OFFLINE': 5,
    }

    state_severity_maps = {
        'OK': 0,
        'NEED_RELOAD': 3,
        'CONFIG_MISMATCH': 3,
        'DOWN/OFFLINE': 5,
        'DOWN': 5,
        'OFFLINE': 5,
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
            'connector_id': context.connector_id,
            'component_title': context.title
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ScalityConnector collect')

        ds0 = config.datasources[0]
        scheme = 'https' if ds0.zScalityUseSSL else 'http'
        url = '{}://{}/api/v0.1/volume_connectors/{}/'.format(scheme, config.id, ds0.params['connector_id'])
        basicAuth = base64.encodestring('{}:{}'.format(ds0.zScalityUsername, ds0.zScalityPassword))
        authHeader = "Basic " + basicAuth.strip()

        agent = Agent(reactor, contextFactory=SkipCertifContextFactory())
        headers = {
            "Accept": ['application/json'],
            "Authorization": [authHeader],
        }
        try:
            response = yield agent.request('GET', url, Headers(headers))
            response_body = yield readBody(response)
            response_body = json.loads(response_body)
            returnValue(response_body)
        except Exception as e:
            log.exception('{}: failed to get server data for {}'.format(config.id, ds0))
            log.exception('{}: Exception: {}'.format(config.id, e))
        returnValue()

    def onSuccess(self, result, config):
        log.debug('Success job - result is {}'.format(result))
        data = self.new_data()

        datasource = config.datasources[0]
        comp_id = datasource.component
        comp_title = datasource.params['component_title']
        connector_metrics = result['_items'][0]

        status_value = self.status_maps.get(connector_metrics['status'], 3)
        data['values'][comp_id]['connector_status'] = status_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': status_value,
            'eventKey': 'ConnectorStatus',
            'eventClassKey': 'ConnectorStatus',
            'summary': 'Connector {} - Status is {}'.format(comp_title, connector_metrics['status']),
            'message': 'Connector {} - Status is {}'.format(comp_title, connector_metrics['status']),
            'eventClass': '/Status/Scality/Connector',
        })

        # State
        state_value = max([self.state_value_maps.get(s, -1) for s in connector_metrics['state']])
        state_severity = max([self.state_severity_maps.get(s, -1) for s in connector_metrics['state']])
        data['values'][comp_id]['connector_state'] = state_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': state_severity,
            'eventKey': 'ConnectorStatus',
            'eventClassKey': 'ConnectorStatus',
            'summary': 'Connector {} - State is {}'.format(comp_title, ','.join(s for s in connector_metrics['state'])),
            'message': 'Connector {} - State is {}'.format(comp_title, ','.join(s for s in connector_metrics['state'])),
            'eventClass': '/Status/Scality/Connector',
        })


        log.debug('data: {}'.format(data))

        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
