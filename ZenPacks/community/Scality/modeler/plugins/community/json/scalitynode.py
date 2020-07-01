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


class scalitynode(PythonPlugin):

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

        nodes = []
        offset = 0
        limit = 20
        try:
            while True:
                # TODO: check valid HTTP code and presence of _items in output
                scheme = 'https' if zScalityUseSSL else 'http'
                url = '{}://{}/api/v0.1/storenodes/?offset={}&limit={}'.format(scheme, device.id, offset, limit)
                response = yield agent.request('GET', url, Headers(headers))
                response_body = yield readBody(response)
                response_body = json.loads(response_body)
                nodes.extend(response_body['_items'])
                offset += limit
                if len(nodes) >= response_body['_meta']['count'] or offset > response_body['_meta']['count']:
                    break
        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)

        returnValue(nodes)

    def process(self, device, results, log):

        rm = []
        rings = {}
        for entry in results:
            ring_name = entry['ring']
            if ring_name not in rings:
                rings[ring_name] = []
            rings[ring_name].append(entry)

        for ring, nodes in rings.items():
            compname = 'scalitySupervisors/Supervisor/scalityRings/{}'.format(ring)
            node_maps = []
            for node in nodes:
                om_node = ObjectMap()
                node_name = node['name']
                om_node.id = self.prepId('{}_{}'.format(ring, node_name))
                om_node.title = node_name
                om_node.ring = ring
                # TODO: not safe
                om_node.admin_endpoint = '{}:{}'.format(node['admin_address'], node['admin_port'])
                om_node.chord_endpoint = '{}:{}'.format(node['chord_address'], node['chord_port'])
                om_node.server_endpoint = node['server']
                node_maps.append(om_node)
            rm.append(RelationshipMap(compname=compname,
                                      relname='scalityNodes',
                                      modname='ZenPacks.community.Scality.ScalityNode',
                                      objmaps=node_maps))
        log.debug('AAAA Node')
        return rm
