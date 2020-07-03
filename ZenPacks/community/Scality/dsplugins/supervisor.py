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


class Supervisor(PythonDataSourcePlugin):
    proxy_attributes = (
        'zScalityUsername',
        'zScalityPassword',
        'zScalityUseSSL',
    )

    sup_status_values_maps = {
        'Unknown': 3,
        'Invalid BizstoreSup credentials': 2,
        'Unreachable': 1,
        'Running': 0,
    }

    sup_status_severity_maps = {
        'Unreachable': 5,
        'Unknown': 3,
        'Invalid BizstoreSup credentials': 3,
        'Running': 0,
    }

    @classmethod
    def config_key(cls, datasource, context):
        log.info('In config_key {} {} {} {}'.format(context.device().id,
                                                 datasource.getCycleTime(context),
                                                 context.id,
                                                 'ScalitySupervisor'))

        return (context.device().id,
                datasource.getCycleTime(context),
                context.id,
                'ScalitySupervisor'
        )

    @classmethod
    def params(cls, datasource, context):
        return {
            'component_title': context.title
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ScalityRing collect')

        ds0 = config.datasources[0]
        scheme = 'https' if ds0.zScalityUseSSL else 'http'
        url = '{}://{}/api/v0.1/status/'.format(scheme, config.id)
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

        status_value = self.sup_status_values_maps.get(result['supv2_status'], 3)
        severity_value = self.sup_status_severity_maps.get(result['supv2_status'], 3)
        data['values'][comp_id]['supervisor_status'] = status_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': severity_value,
            'eventKey': 'SupervisorStatus',
            'eventClassKey': 'SupervisorStatus',
            'summary': 'Supervisor - Status is {}'.format(comp_title, result['supv2_status']),
            'message': 'Supervisor - Status is {}'.format(comp_title, result['supv2_status']),
            'eventClass': '/Status/Scality/Supervisor',
        })

        status_value = self.sup_status_values_maps.get(result['bizstoresup_status'], 3)
        severity_value = self.sup_status_severity_maps.get(result['bizstoresup_status'], 3)
        data['values'][comp_id]['supervisor_bizstore_status'] = status_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': severity_value,
            'eventKey': 'BizStoreStatus',
            'eventClassKey': 'BizStoreStatus',
            'summary': 'Supervisor - Biz Store Status is {}'.format(comp_title, result['bizstoresup_status']),
            'message': 'Supervisor - Biz Store Status is {}'.format(comp_title, result['bizstoresup_status']),
            'eventClass': '/Status/Scality/Supervisor',
        })

        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
