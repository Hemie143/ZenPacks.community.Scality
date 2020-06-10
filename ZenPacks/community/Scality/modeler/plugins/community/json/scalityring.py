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


class scalityring(PythonPlugin):

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

        try:
            # TODO: if more rings than the limit (20)
            # TODO: check valid HTTP code and presence of _items in output
            scheme = 'https' if zScalityUseSSL else 'http'
            url = '{}://{}/api/v0.1/rings/'.format(scheme, device.id)
            log.debug('AAA - url: {}'.format(url))
            response = yield agent.request('GET', url, Headers(headers))
            log.debug('AAA - response: {}'.format(response))
            log.debug('AAA - response code: {}'.format(response.code))
            response_body = yield readBody(response)
            log.debug('AAA - response_body: {}'.format(response_body))
            response_body = json.loads(response_body)

        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)
        returnValue(response_body)

    def process(self, device, results, log):
        log.debug('results: {}'.format(results))

        rings = results['_items']
        rm = []
        ring_maps = []
        for ring in rings:
            ring_name = ring['name']
            om_ring = ObjectMap()
            om_ring.id = self.prepId(ring_name)
            om_ring.title = ring_name
            om_ring.type = ring['type']
            om_ring.planning_period = ring['planning_used_capacity_age']
            ring_maps.append(om_ring)

        rm.append(RelationshipMap(compname='scalitySupervisors/Supervisor',
                                  relname='scalityRings',
                                  modname='ZenPacks.community.Scality.ScalityRing',
                                  objmaps=ring_maps))
        return rm
