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
    )

    deviceProperties = PythonPlugin.deviceProperties + requiredProperties

    @inlineCallbacks
    def collect(self, device, log):
        """Asynchronously collect data from device. Return a deferred/"""
        log.info('%s: collecting data', device.id)

        ip_address = device.manageIp
        if not ip_address:
            log.error("%s: IP Address cannot be empty", device.id)
            returnValue(None)

        zScalityUsername = getattr(device, 'zScalityUsername', None)
        zScalityPassword = getattr(device, 'zScalityPassword', None)
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
            url = 'https://{}/api/v0.1/rings/'.format(ip_address)
            response = yield agent.request('GET', url, Headers(headers))
            response_body = yield readBody(response)
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

        rm.append(RelationshipMap(compname='',
                                  relname='scalityRings',
                                  modname='ZenPacks.community.Scality.ScalityRing',
                                  objmaps=ring_maps))
        return rm
