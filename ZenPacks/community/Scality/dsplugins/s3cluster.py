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
log = logging.getLogger('zen.ScalityS3Cluster')


class S3Cluster(PythonDataSourcePlugin):
    proxy_attributes = (
        'zScalityUsername',
        'zScalityPassword',
        'zScalityUseSSL',
    )

    health_value_maps = {
        'NOMINAL': 0,
        'UNAVAILABLE': 1,
        'DEGRADED': 2,
        'ERROR': 3,
    }

    health_severity_maps = {
        'NOMINAL': 0,
        'UNAVAILABLE': 3,
        'DEGRADED': 3,
        'ERROR': 4,
    }

    @classmethod
    def config_key(cls, datasource, context):
        log.info('In config_key {} {} {} {}'.format(context.device().id,
                                                 datasource.getCycleTime(context),
                                                 context.id,
                                                 'ScalityS3Cluster'))

        return (context.device().id,
                datasource.getCycleTime(context),
                context.id,
                'ScalityS3Cluster'
        )

    @classmethod
    def params(cls, datasource, context):
        return {
            'cluster_id': context.cluster_id,
            'component_title': context.title
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting S3Cluster collect')

        ds0 = config.datasources[0]
        scheme = 'https' if ds0.zScalityUseSSL else 'http'
        url = '{}://{}/api/v0.1/s3_clusters/{}/'.format(scheme, config.id, ds0.params['cluster_id'])
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
        cluster_metrics = result['_items'][0]

        cluster_health = cluster_metrics['cluster_health']
        health_value = self.health_value_maps.get(cluster_health, 2)
        health_severity = self.health_severity_maps.get(cluster_health, 3)

        msg = 'S3 Cluster {} - Health is {}'.format(comp_title, cluster_health)
        data['values'][comp_id]['s3cluster_health'] = health_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': health_severity,
            'eventKey': 'S3ClusterHealth',
            'eventClassKey': 'S3ClusterHealth',
            'summary': msg,
            'message': msg,
            'eventClass': '/Status/Scality/S3Cluster',
        })

        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
