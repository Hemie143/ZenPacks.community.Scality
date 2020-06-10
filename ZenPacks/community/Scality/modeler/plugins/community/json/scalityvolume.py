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


class scalityvolume(PythonPlugin):

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

        ip_address = device.manageIp
        if not ip_address:
            log.error("%s: IP Address cannot be empty", device.id)
            returnValue(None)

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

        volumes = []
        offset = 0
        limit = 20
        try:
            while True:
                # TODO: check valid HTTP code and presence of _items in output
                scheme = 'https' if zScalityUseSSL else 'http'
                url = '{}://{}/api/v0.1/volumes/?offset={}&limit={}'.format(scheme, device.id, offset, limit)
                response = yield agent.request('GET', url, Headers(headers))
                response_body = yield readBody(response)
                response_body = json.loads(response_body)
                volumes.extend(response_body['_items'])
                offset += limit
                if len(volumes) >= response_body['_meta']['count'] or offset > response_body['_meta']['count']:
                    break
        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)

        returnValue(volumes)

    def process(self, device, results, log):
        # log.debug('results: {}'.format(results))

        rm = []
        volume_maps = []
        for volume in results:
            volume_id = volume['id']
            om_volume = ObjectMap()
            om_volume.id = self.prepId(volume_id)
            om_volume.title = volume['name']
            om_volume.volume_id = volume_id
            om_volume.device_id = volume['device_id']
            om_volume.supv2_id = volume['supv2_id']
            om_volume.data_ring = volume['data_ring']
            om_volume.meta_ring = volume['metadata_ring']
            volume_maps.append(om_volume)

        rm.append(RelationshipMap(compname='scalitySupervisors/Supervisor',
                                  relname='scalityVolumes',
                                  modname='ZenPacks.community.Scality.ScalityVolume',
                                  objmaps=volume_maps))

        return rm
