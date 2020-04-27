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

        nodes = []
        offset = 0
        limit = 20
        try:
            while True:
                # TODO: check valid HTTP code and presence of _items in output
                url = 'https://{}/api/v0.1/storenodes/?offset={}&limit={}'.format(device.id, offset, limit)
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
        # log.debug('results: {}'.format(results))

        rm = []
        node_maps = []
        for node in results:
            node_name = node['name']
            om_node = ObjectMap()
            om_node.id = self.prepId(node_name)
            om_node.title = node_name
            om_node.ring = node['ring']
            # TODO: not safe
            om_node.admin_endpoint = '{}:{}'.format(node['admin_address'], node['admin_port'])
            om_node.chord_endpoint = '{}:{}'.format(node['chord_address'], node['chord_port'])
            om_node.server_endpoint = node['server']
            node_maps.append(om_node)

        rm.append(RelationshipMap(compname='',
                                  relname='scalityNodes',
                                  modname='ZenPacks.community.Scality.ScalityNode',
                                  objmaps=node_maps))

        return rm
