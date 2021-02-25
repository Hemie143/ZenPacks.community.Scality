import json
import logging
import base64

# Twisted Imports
from twisted.internet import reactor, ssl
from twisted.internet.defer import returnValue, inlineCallbacks
from twisted.web.client import Agent, readBody, BrowserLikePolicyForHTTPS
from twisted.web.http_headers import Headers
from twisted.web.iweb import IPolicyForHTTPS

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from zope.interface import implementer

from ZenPacks.community.Scality.lib.utils import SkipCertifContextFactory

# Setup logging
log = logging.getLogger('zen.ScalityDisk')


class Disk(PythonDataSourcePlugin):
    proxy_attributes = (
        'zScalityUsername',
        'zScalityPassword',
        'zScalityUseSSL',
    )

    status_maps = {
        'OK': 0,
        'WARNING': 3,
        'CRITICAL': 5,
    }

    state_value_maps = {
        'OK': 0,
        'CONNERR': 1,
        'OOS_SYS': 2,
        'CONNTIMEOUT': 3,
        'STOREERR': 4,
        'OFFLINE': 5,
        'OOS_PERM': 6,
        'OOS_TEMP': 7,
        'DISKFULL': 8,
    }

    state_severity_maps = {
        'OK': 0,
        'CONNERR': 3,
        'OOS_SYS': 3,
        'CONNTIMEOUT': 4,
        'STOREERR': 4,
        'OFFLINE': 4,
        'OOS_PERM': 4,
        'OOS_TEMP': 4,
        'DISKFULL': 5,
    }

    @classmethod
    def config_key(cls, datasource, context):
        log.info('In config_key {} {} {} {}'.format(context.device().id,
                                                 datasource.getCycleTime(context),
                                                 context.id,
                                                 'ScalityDisk'))

        return (context.device().id,
                datasource.getCycleTime(context),
                context.id,
                'ScalityDisk'
        )

    @classmethod
    def params(cls, datasource, context):
        return {
            'disk_id': context.disk_id,
            'component_title': context.title
        }

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting ScalityRing collect')

        ds0 = config.datasources[0]
        scheme = 'https' if ds0.zScalityUseSSL else 'http'
        url = '{}://{}/api/v0.1/disks/{}/'.format(scheme, config.id, ds0.params['disk_id'])
        basicAuth = base64.encodestring('{}:{}'.format(ds0.zScalityUsername, ds0.zScalityPassword))
        authHeader = "Basic " + basicAuth.strip()

        agent = Agent(reactor, contextFactory=SkipCertifContextFactory())
        headers = {
            "Accept": ['application/json'],
            "Authorization": [authHeader],
        }
        try:
            response = yield agent.request('GET', url, Headers(headers))
            response_body = yield readBody(response)
            response_body = json.loads(response_body)
            returnValue(response_body)
        except Exception as e:
            log.exception('{}: failed to get server data for {}'.format(config.id, ds0))
            log.exception('{}: Exception: {}'.format(config.id, e))
        returnValue()

    def onSuccess(self, result, config):
        log.debug('Success job - result is {}'.format(result))
        data = self.new_data()

        datasource = config.datasources[0]
        comp_id = datasource.component
        comp_title = datasource.params['component_title']
        disk_metrics = result['_items'][0]

        status_value = self.status_maps.get(disk_metrics['status'], 3)
        data['values'][comp_id]['disk_status'] = status_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': status_value,
            'eventKey': 'DiskStatus',
            'eventClassKey': 'DiskStatus',
            'summary': 'Disk {} - Status is {}'.format(comp_title, disk_metrics['status']),
            'message': 'Disk {} - Status is {}'.format(comp_title, disk_metrics['status']),
            'eventClass': '/Status/Scality/Disk',
        })

        disk_state = disk_metrics['state']
        state_value = max([self.state_value_maps.get(s, -1) for s in disk_state])
        state_severity = max([self.state_severity_maps.get(s, 3) for s in disk_state])
        msg = 'Disk {} - State is {}'.format(comp_title, ', '.join(disk_state))
        data['values'][comp_id]['disk_state'] = state_value
        data['events'].append({
            'device': config.id,
            'component': comp_id,
            'severity': state_severity,
            'eventKey': 'DiskState',
            'eventClassKey': 'DiskState',
            'summary': msg,
            'message': msg,
            'eventClass': '/Status/Scality/Disk',
        })

        data['values'][comp_id]['disk_number_inodes'] = disk_metrics['number_inodes']
        data['values'][comp_id]['disk_diskspace_total'] = disk_metrics['diskspace_total']
        data['values'][comp_id]['disk_diskspace_used'] = disk_metrics['diskspace_used']
        data['values'][comp_id]['disk_diskspace_stored'] = disk_metrics['diskspace_stored']
        if disk_metrics['diskspace_total'] != 0:
            perc_used = round(100.0 * disk_metrics['diskspace_used'] / disk_metrics['diskspace_total'], 2)
            data['values'][comp_id]['disk_diskspace_used_perc'] = perc_used

        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
