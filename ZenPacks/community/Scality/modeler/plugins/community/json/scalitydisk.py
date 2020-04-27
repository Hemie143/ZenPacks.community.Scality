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


class scalitydisk(PythonPlugin):

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

        disks = []
        offset = 0
        limit = 20
        try:
            while True:
                # TODO: check valid HTTP code and presence of _items in output
                url = 'https://{}/api/v0.1/disks/?offset={}&limit={}'.format(device.id, offset, limit)
                response = yield agent.request('GET', url, Headers(headers))
                response_body = yield readBody(response)
                response_body = json.loads(response_body)
                disks.extend(response_body['_items'])
                offset += limit
                if len(disks) >= response_body['_meta']['count'] or offset > response_body['_meta']['count']:
                    break
        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)

        returnValue(disks)

    def process(self, device, results, log):
        # log.debug('results: {}'.format(results))

        rm = []
        disk_maps = []
        for disk in results:
            disk_id = disk['id']
            om_disk = ObjectMap()
            om_disk.id = self.prepId(disk_id)
            om_disk.title = disk_id
            om_disk.disk_id = disk_id
            om_disk.host = disk['host']
            om_disk.server_id = disk['server']
            om_disk.fs_id = disk['fsid']
            om_disk.rings = ', '.join(disk['rings'])
            disk_maps.append(om_disk)

        rm.append(RelationshipMap(compname='',
                                  relname='scalityDisks',
                                  modname='ZenPacks.community.Scality.ScalityDisk',
                                  objmaps=disk_maps))

        return rm
