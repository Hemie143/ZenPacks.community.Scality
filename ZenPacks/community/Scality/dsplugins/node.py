import json
import logging
import base64

# Twisted Imports
from twisted.internet import reactor, ssl
from twisted.internet.defer import returnValue, inlineCallbacks
from twisted.web.client import Agent, readBody, BrowserLikePolicyForHTTPS
from twisted.web.http_headers import Headers
# from twisted.web.iweb import IPolicyForHTTPS

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
# from zope.interface import implementer

from ZenPacks.community.Scality.lib.utils import SkipCertifContextFactory

# Setup logging
log = logging.getLogger('zen.ScalityNode')


class Node(PythonDataSourcePlugin):
    proxy_attributes = (
        'zScalityUsername',
        'zScalityPassword',
        'zScalityUseSSL',
    )

    state_value_maps = {
        'RUN': 0,
        'AVAILABLE': 1,
        'NEW': 2,
        'TASKS_BLOCKED': 3,
        'LOOP': 4,
        'LOADING': 5,
        'LEAVING': 6,
        'DSO CHANGING': 7,
        'SPLIT': 8,
        'CONF_MISMATCH': 9,
        'ARC_REBUILD_NOK': 10,
        'BAL(SRC)': 11,
        'BAL(DST)': 12,
        'OUT_OF_SERVICE': 13,
        'NEED_RELOAD': 14,
        'DISKERR': 15,
        'DISKOFFLINE': 16,
        'DISKWARN': 17,
        'OFFLINE': 18,
        'DUPKEY': 19,
        'DISKFULL': 20,
    }

    state_severity_maps = {
        'RUN': 0,
        'AVAILABLE': 0,
        'NEW': 0,
        'TASKS_BLOCKED': 2,
        'LOOP': 2,
        'LOADING': 2,
        'LEAVING': 2,
        'DSO CHANGING': 2,
        'SPLIT': 2,
        'CONF_MISMATCH': 4,
        'ARC_REBUILD_NOK': 4,
        'BAL(SRC)': 4,
        'BAL(DST)': 4,
        'OUT_OF_SERVICE': 4,
        'NEED_RELOAD': 4,
        'DISKERR': 4,
        'DISKOFFLINE': 4,
        'DISKWARN': 4,
        'OFFLINE': 5,
        'DUPKEY': 5,
        'DISKFULL': 5,
    }

    @classmethod
    def config_key(cls, datasource, context):
        log.info('In config_key {} {} {}'.format(context.device().id,
                                                 datasource.getCycleTime(context),
                                                 'ScalityNode'))

        return (context.device().id,
                datasource.getCycleTime(context),
                'ScalityNode'
        )

    @classmethod
    def params(cls, datasource, context):
        return {
            'storenode_id': context.admin_endpoint,
            'component_title': context.title
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ScalityNode collect')

        ds0 = config.datasources[0]
        scheme = 'https' if ds0.zScalityUseSSL else 'http'
        # url = '{}://{}/api/v0.1/storenodes/{}/'.format(scheme, config.id, ds0.params['storenode_id'])
        url = '{}://{}/api/v0.1/storenodes/'.format(scheme, config.id)
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
        for datasource in config.datasources:

            comp_id = datasource.component
            comp_title = datasource.params['component_title']
            node_metrics = result['_items'][0]

            state_value = self.state_value_maps.get(node_metrics['state'], -1)
            state_severity = self.state_severity_maps.get(node_metrics['state'], 3)
            data['values'][comp_id]['node_state'] = state_value
            data['events'].append({
                'device': config.id,
                'component': comp_id,
                'severity': state_severity,
                'eventKey': 'NodeState',
                'eventClassKey': 'NodeState',
                'summary': 'Node {} - State is {}'.format(comp_title, node_metrics['state']),
                'message': 'Node {} - State is {}'.format(comp_title, node_metrics['state']),
                'eventClass': '/Status/Scality/Node',
            })

            reachable = node_metrics['reachable']
            reachable_value = 0 if reachable else 5
            data['values'][comp_id]['node_reachable'] = reachable_value
            msg = 'Node {} is{}reachable'.format(comp_title, " " if reachable else " NOT ")
            data['events'].append({
                'device': config.id,
                'component': comp_id,
                'severity': reachable_value,
                'eventKey': 'NodeReachable',
                'eventClassKey': 'NodeReachable',
                'summary': msg,
                'message': msg,
                'eventClass': '/Status/Scality/Node',
            })

            conf_ok = not node_metrics['conf_mismatch']
            conf_ok_value = 0 if conf_ok else 5
            data['values'][comp_id]['node_conf_mismatch'] = conf_ok_value
            msg = 'Node {} - Configuration is {}'.format(comp_title, "OK" if conf_ok else "WRONG")
            data['events'].append({
                'device': config.id,
                'component': comp_id,
                'severity': conf_ok_value,
                'eventKey': 'NodeConfig',
                'eventClassKey': 'NodeConfig',
                'summary': msg,
                'message': msg,
                'eventClass': '/Status/Scality/Node',
            })

            tasks_ok = not node_metrics['tasks_blocked']
            tasks_ok_value = 0 if tasks_ok else 5
            data['values'][comp_id]['node_tasks_blocked'] = tasks_ok_value
            msg = 'Node {} - {}'.format(comp_title, "No stuck task" if tasks_ok else "Some tasks are stuck")
            data['events'].append({
                'device': config.id,
                'component': comp_id,
                'severity': tasks_ok_value,
                'eventKey': 'NodeTasksBlocked',
                'eventClassKey': 'NodeTasksBlocked',
                'summary': msg,
                'message': msg,
                'eventClass': '/Status/Scality/Node',
            })

            data['values'][comp_id]['node_nb_chunks'] = node_metrics['nb_chunks']
            data['values'][comp_id]['node_nb_tasks'] = node_metrics['nb_tasks']

        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
