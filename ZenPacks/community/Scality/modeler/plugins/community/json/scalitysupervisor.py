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


class scalitysupervisor(PythonPlugin):

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
            # TODO: check valid HTTP code and presence of _items in output
            url = 'https://{}/api/v0.1/status/'.format(ip_address)
            response = yield agent.request('GET', url, Headers(headers))
            response_body = yield readBody(response)
            response_body = json.loads(response_body)

        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)
        returnValue(response_body)

    def process(self, device, results, log):
        log.debug('results: {}'.format(results))

        rm = []
        sup_maps = []

        om_sup = ObjectMap()
        om_sup.id = self.prepId('Supervisor')
        om_sup.title = 'Supervisor {}'.format(results['supapi_version'])
        om_sup.version = results['supapi_version']
        om_sup.complete_version = results['supapi_complete_version']
        sup_maps.append(om_sup)

        rm.append(RelationshipMap(compname='',
                                  relname='scalitySupervisors',
                                  modname='ZenPacks.community.Scality.ScalitySupervisor',
                                  objmaps=sup_maps))
        return rm
