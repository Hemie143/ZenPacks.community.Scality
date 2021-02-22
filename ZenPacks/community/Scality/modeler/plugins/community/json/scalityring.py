"""
Collect Scality components using API calls
"""

# stdlib Imports
import json
import base64
from datetime import datetime
from bs4 import BeautifulSoup

# Twisted Imports
from twisted.internet.defer import inlineCallbacks, returnValue
from twisted.web.client import Agent, readBody, BrowserLikePolicyForHTTPS
from twisted.internet import reactor, ssl
from twisted.web.http_headers import Headers
from twisted.web.iweb import IPolicyForHTTPS

# Zenoss Imports
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin
from Products.DataCollector.plugins.DataMaps import ObjectMap, RelationshipMap
from zope.interface import implementer

from ZenPacks.community.Scality.lib.aws4_sign import sign_request

@implementer(IPolicyForHTTPS)
class SkipCertifContextFactory(object):
    def __init__(self):
        self.default_policy = BrowserLikePolicyForHTTPS()

    def creatorForNetloc(self, hostname, port):
        return ssl.CertificateOptions(verify=False)

class scalityring(PythonPlugin):

    requiredProperties = (
        'zScalityUsername',
        'zScalityPassword',
        'zScalityUseSSL',
        'zScalityS3BucketHost',
        'zScalityS3AccessKeys',
        'zScalityS3SecretKeys',
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
        scheme = 'https' if zScalityUseSSL else 'http'

        results = {}
        agent = Agent(reactor, contextFactory=SkipCertifContextFactory())
        headers = {
                   "Accept": ['application/json'],
                   "Authorization": [authHeader],
                   }

        # Supervisor only
        try:
            url = '{}://{}/api/v0.1/status/'.format(scheme, device.id)
            response = yield agent.request('GET', url, Headers(headers))
            response_body = yield readBody(response)
            response_body = json.loads(response_body)
            results['supervisor'] = response_body
        except Exception, e:
            log.error('%s: %s', device.id, e)
            returnValue(None)

        queries = {
            's3clusters': '{}://{}/api/v0.1/s3_clusters/?offset={}&limit={}',
            'servers': '{}://{}/api/v0.1/servers/?offset={}&limit={}',
            'volumes': '{}://{}/api/v0.1/volumes/?offset={}&limit={}',
            'rings': '{}://{}/api/v0.1/rings/?offset={}&limit={}',
            'disks': '{}://{}/api/v0.1/disks/?offset={}&limit={}',
            'nodes': '{}://{}/api/v0.1/storenodes/?offset={}&limit={}',
            'connectors': '{}://{}/api/v0.1/volume_connectors/?offset={}&limit={}',
        }

        # queries = {}

        for item, base_url in queries.items():
            try:
                data = []
                offset = 0
                limit = 20
                while True:
                    url = base_url.format(scheme, device.id, offset, limit)
                    response = yield agent.request('GET', url, Headers(headers))
                    response_body = yield readBody(response)
                    response_body = json.loads(response_body)
                    data.extend(response_body['_items'])
                    offset += limit
                    if len(data) >= response_body['_meta']['count'] or offset > response_body['_meta']['count']:
                        break
                results[item] = data
            except Exception, e:
                log.error('%s: %s', device.id, e)

        zScalityS3BucketHost = getattr(device, 'zScalityS3BucketHost', None)
        zScalityS3AccessKeys = getattr(device, 'zScalityS3AccessKeys', None)
        log.debug('zScalityS3AccessKeys: {}'.format(zScalityS3AccessKeys))
        log.debug('zScalityS3AccessKeys: {}'.format(type(zScalityS3AccessKeys)))
        zScalityS3SecretKeys = getattr(device, 'zScalityS3SecretKeys', None)
        log.debug('zScalityS3SecretKeys: {}'.format(zScalityS3SecretKeys))
        num_keypairs = min(len(zScalityS3AccessKeys), len(zScalityS3SecretKeys))
        if zScalityS3BucketHost and zScalityS3AccessKeys and zScalityS3SecretKeys:
            results['s3buckets'] = []
            for i in range(num_keypairs):
                url = 'https://{}'.format(zScalityS3BucketHost)
                headers = sign_request(url, zScalityS3AccessKeys[i], zScalityS3SecretKeys[i])
                log.debug('headers: {}'.format(headers))
                try:
                    response = yield agent.request('GET', url, Headers(headers))
                    response_body = yield readBody(response)
                    log.debug('response: {}'.format(response))
                    log.debug('response_body: {}'.format(response_body))
                    results['s3buckets'].append(response_body)
                except Exception, e:
                    log.error('%s: %s', device.id, e)
        returnValue(results)

    def process(self, device, results, log):
        # log.debug('results: {}'.format(results))
        rm = []

        if 'supervisor' in results:
            rm.append(self.model_supervisor(results['supervisor'], log))
            if 's3clusters' in results:
                rm.append(self.model_s3clusters(results['s3clusters'], log))
            if 'servers' in results:
                rm.append(self.model_servers(results['servers'], log))
            if 'volumes' in results:
                rm.append(self.model_volumes(results['volumes'], log))
            if 'rings' in results:
                rm.append(self.model_rings(results['rings'], log))
            if 'disks' in results:
                rm.extend(self.model_disks(results['disks'], results['servers'], log))
            if 'nodes' in results:
                rm.extend(self.model_nodes(results['nodes'], log))
            if 'connectors' in results:
                rm.extend(self.model_connectors(results['connectors'], log))
        if 's3buckets' in results:
            rm.extend(self.model_s3buckets(results['s3buckets'], log))

        return rm

    def model_supervisor(self, data, log):
        log.debug('model_supervisor data: {}'.format(data))
        om_sup = ObjectMap()
        om_sup.id = self.prepId('Supervisor')
        om_sup.title = 'Supervisor {}'.format(data['supapi_version'])
        om_sup.version = data['supapi_version']
        om_sup.complete_version = data['supapi_complete_version']
        return RelationshipMap(compname='',
                               relname='scalitySupervisors',
                               modname='ZenPacks.community.Scality.ScalitySupervisor',
                               objmaps=[om_sup])

    def model_s3clusters(self, s3clusters, log):
        log.debug('model_s3clusters data: {}'.format(s3clusters))
        s3cluster_maps = []
        for s3cluster in s3clusters:
            s3cluster_name = s3cluster['name']
            om_s3cluster = ObjectMap()
            om_s3cluster.id = self.prepId(s3cluster_name)
            om_s3cluster.title = s3cluster_name
            om_s3cluster.cluster_id = s3cluster['id']
            s3cluster_maps.append(om_s3cluster)

        return RelationshipMap(compname='scalitySupervisors/Supervisor',
                               relname='scalityS3Clusters',
                               modname='ZenPacks.community.Scality.ScalityS3Cluster',
                               objmaps=s3cluster_maps)

    def model_s3buckets(self, s3buckets, log):
        log.debug('model_s3buckets data: {}'.format(s3buckets))

        rm = []
        rm_owner = []
        rm_bucket = []
        for entry in s3buckets:
            soup = BeautifulSoup(entry, 'xml')
            log.debug('AAA soup: {}'.format(soup))

            om_owner = ObjectMap()
            id = 'bucketaccount_{}'.format(soup.find("Owner").find("ID").text)
            om_owner.id = self.prepId(id)
            om_owner.title = soup.find("Owner").find("DisplayName").text
            rm_owner.append(om_owner)
            log.debug('AAA om_owner: {}'.format(om_owner))
            comp_id = 'scalityS3BucketAccounts/{}'.format(om_owner.id)

            s3bucket_maps = []
            buckets_list = soup.find_all(name="Bucket")
            log.debug('buckets: {}'.format(buckets_list))
            for s3bucket in buckets_list:
                bucket_name = s3bucket.Name.text
                log.debug('bucket_name: {}'.format(bucket_name))
                om_s3bucket = ObjectMap()
                id = 'bucket_{}_{}'.format(om_owner.title, bucket_name)
                om_s3bucket.id = self.prepId(id)
                om_s3bucket.title = bucket_name
                om_s3bucket.creation_date = s3bucket.CreationDate.text
                s3bucket_maps.append(om_s3bucket)

            rm_bucket.append(RelationshipMap(compname=comp_id,
                                             relname='scalityS3Buckets',
                                             modname='ZenPacks.community.Scality.ScalityS3Bucket',
                                             objmaps=s3bucket_maps))
        # log.debug('rm_owner: {}'.format(rm_owner))
        # log.debug('rm_bucket: {}'.format(rm_bucket))
        rm.append(RelationshipMap(relname='scalityS3BucketAccounts',
                                  modname='ZenPacks.community.Scality.ScalityS3BucketAccount',
                                  compname='',
                                  objmaps=rm_owner))

        # rm.extend(rm_owner)
        rm.extend(rm_bucket)

        log.debug('rm: {}'.format(rm))
        return rm

    def model_servers(self, servers, log):
        log.debug('model_servers data: {}'.format(servers))
        server_maps = []
        for server in servers:
            server_name = server['name']
            server_ip = server['management_ip_address']
            om_server = ObjectMap()
            # TODO: Use something else than IP address to ID the server
            om_server.id = self.prepId(server_ip)
            om_server.title = server_name
            om_server.server_type = server['server_type']
            om_server.ip_address = server_ip
            om_server.zone = server['zone']
            # TODO: check usage of id in datasource
            om_server.server_id = server['id']
            # TODO: BUG since 8.x : TypeError: string indices must be integers
            log.debug('XXX server: {}'.format(server))
            rings = server['rings']

            if rings:
                log.debug('*** rings: {}'.format(isinstance(rings[0], dict)))
                return
                # Supervisor 7.4.6.1
                om_server.rings = ', '.join(sorted([r['name'] for r in server['rings']]))
            else:
                # Supervisor 8.3.0.5
                om_server.rings = ', '.join(sorted(server['rings']))
            om_server.roles = ', '.join(sorted(server['roles']))
            om_server.disks = ', '.join(server['disks'])
            server_maps.append(om_server)

        return RelationshipMap(compname='scalitySupervisors/Supervisor',
                               relname='scalityServers',
                               modname='ZenPacks.community.Scality.ScalityServer',
                               objmaps=server_maps)

    def model_volumes(self, volumes, log):
        log.debug('model_volumes data: {}'.format(volumes))
        volume_maps = []
        for volume in volumes:
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

        return RelationshipMap(compname='scalitySupervisors/Supervisor',
                               relname='scalityVolumes',
                               modname='ZenPacks.community.Scality.ScalityVolume',
                               objmaps=volume_maps)

    def model_rings(self, rings, log):
        log.debug('model_rings data: {}'.format(rings))
        ring_maps = []
        for ring in rings:
            ring_name = ring['name']
            om_ring = ObjectMap()
            om_ring.id = self.prepId(ring_name)
            om_ring.title = ring_name
            om_ring.type = ring['type']
            om_ring.planning_period = ring['planning_used_capacity_age']
            ring_maps.append(om_ring)

        return RelationshipMap(compname='scalitySupervisors/Supervisor',
                               relname='scalityRings',
                               modname='ZenPacks.community.Scality.ScalityRing',
                               objmaps=ring_maps)

    def model_disks(self, results, servers_data, log):
        log.debug('model_disks data: {}'.format(results))

        servers = {}
        for entry in results:
            host_ip = entry['host']
            if host_ip not in servers:
                servers[host_ip] = []
            servers[host_ip].append(entry)

        rm = []
        for ip_address, disks in servers.items():
            compname = 'scalitySupervisors/Supervisor/scalityServers/{}'.format(ip_address)
            disk_maps = []
            for disk in disks:
                disk_id = disk['id']
                om_disk = ObjectMap()
                om_disk.id = self.prepId(disk_id)
                server_id = disk['server']
                for server in servers_data:
                    if server['_links']['self'].endswith('/{}/'.format(server_id)):
                        server_name = server['name']
                        break
                om_disk.title = '{} ({})'.format(disk['name'], server_name)
                om_disk.disk_id = disk_id
                om_disk.host = disk['host']
                om_disk.server_id = server_id
                om_disk.server_name = server_name
                om_disk.server_ip = ip_address
                om_disk.fs_id = disk['fsid']
                om_disk.rings = ', '.join(disk['rings'])
                disk_maps.append(om_disk)

            rm.append(RelationshipMap(compname=compname,
                                      relname='scalityDisks',
                                      modname='ZenPacks.community.Scality.ScalityDisk',
                                      objmaps=disk_maps))
        return rm

    def model_nodes(self, results, log):
        log.debug('model_nodes data: {}'.format(results))
        rings = {}
        for entry in results:
            ring_name = entry['ring']
            if ring_name not in rings:
                rings[ring_name] = []
            rings[ring_name].append(entry)

        rm = []
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
        return rm

    def model_connectors(self, results, log):
        log.debug('model_connectors data: {}'.format(results))
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

        return rm
