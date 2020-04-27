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


class Node(PythonDataSourcePlugin):
    proxy_attributes = (
        'zScalityUsername',
        'zScalityPassword',
    )

    state_maps = {
        'RUN': 0,
    }

    @classmethod
    def config_key(cls, datasource, context):
        log.info('In config_key {} {} {} {}'.format(context.device().id,
                                                 datasource.getCycleTime(context),
                                                 context.id,
                                                 'ScalityNode'))

        return (context.device().id,
                datasource.getCycleTime(context),
                context.id,
                'ScalityNode'
        )

    @classmethod
    def params(cls, datasource, context):
        return {
            'storenode_id': context.admin_endpoint
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ScalityRing collect')

        ds0 = config.datasources[0]
        url = 'https://{}/api/v0.1/storenodes/{}/'.format(config.id, ds0.params['storenode_id'])
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
        node_metrics = result['_items'][0]

        state_value = self.state_maps.get(node_metrics['state'], 3)
        data['values'][comp_id]['node_state'] = state_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': state_value,
            'eventKey': 'NodeStatus',
            'eventClassKey': 'NodeStatus',
            'summary': 'Node {} - State is {}'.format(comp_id, node_metrics['state']),
            'message': 'Node {} - State is {}'.format(comp_id, node_metrics['state']),
            'eventClass': '/Status',
        })

        reachable = node_metrics['reachable']
        reachable_value = 0 if reachable else 5
        data['values'][comp_id]['node_reachable'] = reachable_value
        msg = 'Node {} is{}reachable'.format(comp_id, " " if reachable else " NOT ")
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': reachable_value,
            'eventKey': 'NodeStatus',
            'eventClassKey': 'NodeStatus',
            'summary': msg,
            'message': msg,
            'eventClass': '/Status',
        })

        conf_ok = not node_metrics['conf_mismatch']
        conf_ok_value = 0 if conf_ok else 5
        data['values'][comp_id]['node_conf_mismatch'] = conf_ok_value
        msg = 'Node {} - Configuration is {}'.format(comp_id, "OK" if conf_ok else "WRONG")
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': conf_ok_value,
            'eventKey': 'NodeStatus',
            'eventClassKey': 'NodeStatus',
            'summary': msg,
            'message': msg,
            'eventClass': '/Status',
        })

        tasks_ok = not node_metrics['tasks_blocked']
        tasks_ok_value = 0 if tasks_ok else 5
        data['values'][comp_id]['node_tasks_blocked'] = tasks_ok_value
        msg = 'Node {} - {}'.format(comp_id, "No stuck task" if tasks_ok else "Some tasks are stuck")
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': tasks_ok_value,
            'eventKey': 'NodeStatus',
            'eventClassKey': 'NodeStatus',
            'summary': msg,
            'message': msg,
            'eventClass': '/Status',
        })

        data['values'][comp_id]['node_nb_chunks'] = node_metrics['nb_chunks']
        data['values'][comp_id]['node_nb_tasks'] = node_metrics['nb_tasks']

        log.debug('AAA Node {} data: {}'.format(comp_id, data))

        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
