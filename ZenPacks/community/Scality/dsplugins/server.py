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


class Server(PythonDataSourcePlugin):
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
        'ONLINE': 0,
        'MISSING': 1,
        'OFFLINE': 2,
    }

    state_severity_maps = {
        'ONLINE': 0,
        'MISSING': 5,
        'OFFLINE': 5,
    }

    @classmethod
    def config_key(cls, datasource, context):
        log.info('In config_key {} {} {} {}'.format(context.device().id,
                                                 datasource.getCycleTime(context),
                                                 context.id,
                                                 'ScalityServer'))

        return (context.device().id,
                datasource.getCycleTime(context),
                context.id,
                'ScalityServer'
        )

    @classmethod
    def params(cls, datasource, context):
        return {
            'server_id': context.server_id
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ScalityServer collect')

        ds0 = config.datasources[0]
        scheme = 'https' if ds0.zScalityUseSSL else 'http'
        url = '{}://{}/api/v0.1/servers/{}/'.format(scheme, config.id, ds0.params['server_id'])
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
        server_metrics = result['_items'][0]

        status_value = self.status_maps.get(server_metrics['status'], 3)
        data['values'][comp_id]['server_status'] = status_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': status_value,
            'eventKey': 'ServerStatus',
            'eventClassKey': 'ServerStatus',
            'summary': 'Server {} - Status is {}'.format(comp_id, server_metrics['status']),
            'message': 'Server {} - Status is {}'.format(comp_id, server_metrics['status']),
            'eventClass': '/Status',
        })

        state_value = max([self.state_value_maps.get(s, 3) for s in server_metrics['state']])
        state_severity = max([self.state_severity_maps.get(s, 3) for s in server_metrics['state']])
        data['values'][comp_id]['server_state'] = state_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': state_severity,
            'eventKey': 'ServerStatus',
            'eventClassKey': 'ServerStatus',
            'summary': 'Server {} - State is {}'.format(comp_id, server_metrics['state']),
            'message': 'Server {} - State is {}'.format(comp_id, server_metrics['state']),
            'eventClass': '/Status',
        })

        disk_critical = server_metrics['diskcount_status_critical']
        disk_warning = server_metrics['diskcount_status_warning']
        disk_ok = server_metrics['diskcount_status_ok']
        msg = 'Server {} - {} disks critical, {} disks in warning, {} disks OK'.format(comp_id, disk_critical,
                                                                                     disk_warning, disk_ok)

        if disk_critical > 0:
            disk_value = 5
        elif disk_warning > 0:
            disk_value = 3
        else:
            disk_value = 0
        data['values'][comp_id]['server_diskstatus'] = disk_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': disk_value,
            'eventKey': 'ServerDiskStatus',
            'eventClassKey': 'ServerDiskStatus',
            'summary': msg,
            'message': msg,
            'eventClass': '/Status',
        })


        log.debug('AAA Server {} data: {}'.format(comp_id, data))

        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
