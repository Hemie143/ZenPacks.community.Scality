# stdlib Imports
import json
import urllib
import base64

# Twisted Imports
from twisted.internet.defer import inlineCallbacks, returnValue, DeferredList
from twisted.web.client import Agent, readBody
from twisted.internet import reactor
from twisted.web.http_headers import Headers

# Zenoss Imports
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap


class scalitys3cluster(PythonPlugin):

    requiredProperties = (
        'zScalityUsername',
        'zScalityPassword',
        'zScalityUseSSL',
    )

    deviceProperties = PythonPlugin.deviceProperties + requiredProperties

    @inlineCallbacks
    def collect(self, device, log):
        """Asynchronously collect data from device. Return a deferred/"""
        log.info('%s: collecting data', device.id)

        zScalityUsername = getattr(device, 'zScalityUsername', None)
        zScalityPassword = getattr(device, 'zScalityPassword', None)
        zScalityUseSSL = getattr(device, 'zScalityUseSSL', None)
        if not zScalityUsername:
            log.error('%s: %s not set.', device.id, 'zScalityUsername')
            returnValue(None)
        basicAuth = base64.encodestring('{}:{}'.format(zScalityUsername, zScalityPassword))
        authHeader = "Basic " + basicAuth.strip()

        agent = Agent(reactor)
        headers = {
                   "Accept": ['application/json'],
                   "Authorization": [authHeader],
                   }

        s3clusters = []
        offset = 0
        limit = 20
        try:
            while True:
                # TODO: check valid HTTP code and presence of _items in output
                scheme = 'https' if zScalityUseSSL else 'http'
                url = '{}://{}/api/v0.1/s3_clusters/?offset={}&limit={}'.format(scheme, device.id, offset, limit)
                response = yield agent.request('GET', url, Headers(headers))
                response_body = yield readBody(response)
                response_body = json.loads(response_body)
                s3clusters.extend(response_body['_items'])
                offset += limit
                if len(s3clusters) >= response_body['_meta']['count'] or offset > response_body['_meta']['count']:
                    break
        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)

        returnValue(s3clusters)

    def process(self, device, results, log):
        log.debug('results: {}'.format(results))

        rm = []
        s3cluster_maps = []
        for s3cluster in results:
            s3cluster_name = s3cluster['name']
            om_s3cluster = ObjectMap()
            om_s3cluster.id = self.prepId(s3cluster_name)
            om_s3cluster.title = s3cluster_name
            om_s3cluster.cluster_id = s3cluster['id']
            s3cluster_maps.append(om_s3cluster)

        rm.append(RelationshipMap(compname='',
                                  relname='scalityS3Clusters',
                                  modname='ZenPacks.community.Scality.ScalityS3Cluster',
                                  objmaps=s3cluster_maps))

        return rm
