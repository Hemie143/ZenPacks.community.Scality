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


class S3Cluster(PythonDataSourcePlugin):
    proxy_attributes = (
        'zScalityUsername',
        'zScalityPassword',
        'zScalityUseSSL',
    )

    health_maps = {
        'NOMINAL': 0,
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
            'cluster_id': context.cluster_id
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ScalityRing collect')

        ds0 = config.datasources[0]
        scheme = 'https' if ds0.zScalityUseSSL else 'http'
        url = '{}://{}/api/v0.1/s3_clusters/{}/'.format(scheme, config.id, ds0.params['cluster_id'])
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
        cluster_metrics = result['_items'][0]

        health_value = self.health_maps.get(cluster_metrics['cluster_health'], 3)
        data['values'][comp_id]['s3cluster_health'] = health_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': health_value,
            'eventKey': 'S3ClusterStatus',
            'eventClassKey': 'S3ClusterStatus',
            'summary': 'S3 Cluster {} - Health is {}'.format(comp_id, cluster_metrics['cluster_health']),
            'message': 'S3 Cluster {} - Health is {}'.format(comp_id, cluster_metrics['cluster_health']),
            'eventClass': '/Status',
        })

        log.debug('AAA Node {} data: {}'.format(comp_id, data))

        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
