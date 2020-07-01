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


class scalityconnector(PythonPlugin):

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

        connectors = []
        offset = 0
        limit = 20
        try:
            while True:
                # TODO: check valid HTTP code and presence of _items in output
                scheme = 'https' if zScalityUseSSL else 'http'
                url = '{}://{}/api/v0.1/volume_connectors/?offset={}&limit={}'.format(scheme, device.id, offset, limit)
                response = yield agent.request('GET', url, Headers(headers))
                response_body = yield readBody(response)
                response_body = json.loads(response_body)
                connectors.extend(response_body['_items'])
                offset += limit
                if len(connectors) >= response_body['_meta']['count'] or offset > response_body['_meta']['count']:
                    break
        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)

        returnValue(connectors)

    def process(self, device, results, log):

        rings = {}
        for entry in results:
            ring = entry['ring']
            if ring not in rings:
                rings[ring] = []
            rings[ring].append(entry)

        rm = []
        for ring, connectors in rings.items():
            compname = 'scalitySupervisors/Supervisor/scalityRings/{}'.format(ring)
            connector_maps = []

            for connector in connectors:
                volume_id = connector['id']
                om_connector = ObjectMap()
                om_connector.id = self.prepId(volume_id)
                om_connector.title = connector['name']
                om_connector.connector_id = volume_id
                om_connector.protocol = connector['protocol']
                om_connector.detached = connector['detached']
                om_connector.address = connector['address']
                om_connector.ring = connector['ring']
                connector_maps.append(om_connector)

            rm.append(RelationshipMap(compname=compname,
                                      relname='scalityConnectors',
                                      modname='ZenPacks.community.Scality.ScalityConnector',
                                      objmaps=connector_maps))

        log.debug('Connector rm: {}'.format(rm))
        log.debug('AAAA Connector')
        return rm
