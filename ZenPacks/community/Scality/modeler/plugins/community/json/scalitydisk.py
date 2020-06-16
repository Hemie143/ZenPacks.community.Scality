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

        disks = []
        offset = 0
        limit = 20
        try:
            while True:
                # TODO: check valid HTTP code and presence of _items in output
                scheme = 'https' if zScalityUseSSL else 'http'
                url = '{}://{}/api/v0.1/disks/?offset={}&limit={}'.format(scheme, device.id, offset, limit)
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
        servers = {}
        for entry in results:
            host_ip = entry['host']
            if host_ip not in servers:
                servers[host_ip] = []
            servers[host_ip].append(entry)

        rm = []
        for server, disks in servers.items():
            compname = 'scalitySupervisors/Supervisor/scalityServers/{}'.format(server)
            disk_maps = []

            for disk in disks:
                disk_id = disk['id']
                om_disk = ObjectMap()
                om_disk.id = self.prepId(disk_id)
                om_disk.title = '{} ({})'.format(disk['name'], server)
                om_disk.disk_id = disk_id
                om_disk.host = disk['host']
                om_disk.server_id = disk['server']
                om_disk.fs_id = disk['fsid']
                om_disk.rings = ', '.join(disk['rings'])
                disk_maps.append(om_disk)

            rm.append(RelationshipMap(compname=compname,
                                      relname='scalityDisks',
                                      modname='ZenPacks.community.Scality.ScalityDisk',
                                      objmaps=disk_maps))

        return rm
