import json
import logging
import base64
import time
import datetime
from collections import defaultdict
from bs4 import BeautifulSoup
from urllib import quote

# Twisted Imports
from twisted.internet import reactor
from twisted.internet.defer import returnValue, inlineCallbacks
from twisted.web.client import Agent, readBody
from twisted.web.http_headers import Headers
from twisted.web.iweb import IPolicyForHTTPS

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from zope.interface import implementer

from ZenPacks.community.Scality.lib.aws4_sign import sign_request
from ZenPacks.community.Scality.lib.utils import get_time_range, BytesProducer, SkipCertifContextFactory

# Setup logging
log = logging.getLogger('zen.ScalityS3Bucket')

0
class S3Bucket(PythonDataSourcePlugin):
    proxy_attributes = (
        'zScalityS3AccessKeys',
        'zScalityS3SecretKeys',
        'zScalityUTAPIHost',
        'zScalityUTAPIPort',
    )

    @classmethod
    def config_key(cls, datasource, context):
        log.info('In config_key {} {} {}'.format(context.device().id,
                                                 datasource.getCycleTime(context),
                                                 'ScalityS3Bucket'))

        return (context.device().id,
                datasource.getCycleTime(context),
                'ScalityS3Bucket'
        )

    @classmethod
    def params(cls, datasource, context):
        params = {}
        params['bucket_name'] = context.bucket_name
        params['key_index'] = context.key_index
        return params

    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting Scality S3Bucket collect')
        # Runs for all buckets
        bucket_config = defaultdict(list)
        for ds in config.datasources:
            bucket_config[ds.params['key_index']].append(ds.params['bucket_name'])

        ds0 = config.datasources[0]
        zScalityS3AccessKeys = ds0.zScalityS3AccessKeys
        zScalityS3SecretKeys = ds0.zScalityS3SecretKeys
        zScalityUTAPIHost = ds0.zScalityUTAPIHost
        zScalityUTAPIPort = ds0.zScalityUTAPIPort

        result = {}
        if zScalityUTAPIHost and zScalityS3AccessKeys and zScalityS3SecretKeys:
            agent = Agent(reactor, contextFactory=SkipCertifContextFactory())
            # Timeframe to fetch from UTAPI
            start_time, end_time = get_time_range(time.time() * 1000)
            for key_index, bucket_list in bucket_config.items():
                # URL
                url = 'http://{}:{}/buckets?Action=ListMetrics'.format(zScalityUTAPIHost, zScalityUTAPIPort)
                # Payload
                bucketListing = {
                    'buckets': bucket_list,
                    'timeRange': [start_time, end_time],
                }
                payload = json.dumps(bucketListing)
                # headers
                zScalityS3AccessKey = zScalityS3AccessKeys[key_index]
                zScalityS3SecretKey = zScalityS3SecretKeys[key_index]
                headers = sign_request(url,
                                       zScalityS3AccessKey,
                                       zScalityS3SecretKey,
                                       method='POST',
                                       payload=payload,
                                       )
                # body
                body = BytesProducer(payload)
                try:
                    response = yield agent.request('POST', url, Headers(headers), body)
                    response_body = yield readBody(response)
                    result[key_index] = response_body
                except Exception as e:
                    log.exception('{}: failed to get server data for {}'.format(config.id, ds0))
                    log.exception('{}: Exception: {}'.format(config.id, e))
        returnValue(result)

    def onSuccess(self, result, config):
        log.debug('Success job - result is {}'.format(result))
        data = self.new_data()

        for ds in config.datasources:
            bucket_name = ds.params['bucket_name']
            key_index = ds.params['key_index']
            for bucket_data in json.loads(result[key_index]):
                if bucket_data['bucketName'] == bucket_name:
                    break
            else:
                bucket_data = {}
            data['values'][ds.component]['s3bucket_num_objects'] = bucket_data['numberOfObjects'][1]
            data['values'][ds.component]['s3bucket_bucket_size'] = bucket_data['storageUtilized'][1]
            data['values'][ds.component]['s3bucket_incoming_bytes'] = bucket_data['incomingBytes']
            data['values'][ds.component]['s3bucket_outgoing_bytes'] = bucket_data['outgoingBytes']
        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
