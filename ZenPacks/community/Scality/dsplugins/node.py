import json
import logging
import base64

# Twisted Imports
from twisted.internet import reactor, ssl
from twisted.internet.defer import returnValue, inlineCallbacks
from twisted.web.client import Agent, readBody, BrowserLikePolicyForHTTPS
from twisted.web.http_headers import Headers
from twisted.web.iweb import IPolicyForHTTPS

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from zope.interface import implementer

# Setup logging
log = logging.getLogger('zen.ScalityRing')


# TODO: Move this factory in a library
@implementer(IPolicyForHTTPS)
class SkipCertifContextFactory(object):
    def __init__(self):
        self.default_policy = BrowserLikePolicyForHTTPS()

    def creatorForNetloc(self, hostname, port):
        return ssl.CertificateOptions(verify=False)


class Node(PythonDataSourcePlugin):
    proxy_attributes = (
        'zScalityUsername',
        'zScalityPassword',
        'zScalityUseSSL',
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
            'storenode_id': context.admin_endpoint,
            'component_title': context.title
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ScalityRing collect')

        ds0 = config.datasources[0]
        scheme = 'https' if ds0.zScalityUseSSL else 'http'
        url = '{}://{}/api/v0.1/storenodes/{}/'.format(scheme, config.id, ds0.params['storenode_id'])
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
        node_metrics = result['_items'][0]

        state_value = self.state_maps.get(node_metrics['state'], 3)
        data['values'][comp_id]['node_state'] = state_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': state_value,
            'eventKey': 'NodeStatus',
            'eventClassKey': 'NodeStatus',
            'summary': 'Node {} - State is {}'.format(comp_title, node_metrics['state']),
            'message': 'Node {} - State is {}'.format(comp_title, node_metrics['state']),
            'eventClass': '/Status/Scality/Node',
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
            'eventClass': '/Status/Scality/Node',
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
            'eventClass': '/Status/Scality/Node',
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
            'eventClass': '/Status/Scality/Node',
        })

        data['values'][comp_id]['node_nb_chunks'] = node_metrics['nb_chunks']
        data['values'][comp_id]['node_nb_tasks'] = node_metrics['nb_tasks']

        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
