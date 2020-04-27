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


class scalityserver(PythonPlugin):

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
            # TODO: if more servers than the limit (20)
            # TODO: check valid HTTP code and presence of _items in output
            url = 'https://{}/api/v0.1/servers/'.format(ip_address)
            response = yield agent.request('GET', url, Headers(headers))
            response_body = yield readBody(response)
            response_body = json.loads(response_body)
        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)
        returnValue(response_body)

    def process(self, device, results, log):
        log.debug('results: {}'.format(results))

        servers = results['_items']
        rm = []
        server_maps = []
        for server in servers:
            server_name = server['name']
            om_server = ObjectMap()
            om_server.id = self.prepId(server_name)
            om_server.title = server_name
            om_server.server_type = server['server_type']
            om_server.ip_address = server['management_ip_address']
            om_server.zone = server['zone']
            # TODO: check usage of id in datasource
            om_server.server_id = server['id']
            om_server.rings = ', '.join(sorted([r['name'] for r in server['rings']]))
            om_server.roles = ', '.join(sorted(server['roles']))
            om_server.disks = ', '.join(server['disks'])

            server_maps.append(om_server)

        rm.append(RelationshipMap(compname='',
                                  relname='scalityServers',
                                  modname='ZenPacks.community.Scality.ScalityServer',
                                  objmaps=server_maps))

        return rm
