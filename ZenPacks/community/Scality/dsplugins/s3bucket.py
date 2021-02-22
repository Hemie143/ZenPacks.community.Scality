import json
import logging
import base64
import time
from bs4 import BeautifulSoup
from urllib import quote

# Twisted Imports
from twisted.internet import reactor, ssl
from twisted.internet.defer import returnValue, inlineCallbacks
from twisted.web.client import Agent, readBody, BrowserLikePolicyForHTTPS
from twisted.web.http_headers import Headers
from twisted.web.iweb import IPolicyForHTTPS

# Zenoss imports
from ZenPacks.zenoss.PythonCollector.datasources.PythonDataSource import PythonDataSourcePlugin
from zope.interface import implementer

from ZenPacks.community.Scality.lib.aws4_sign import sign_request

# Setup logging
log = logging.getLogger('zen.ScalityS3Bucket')


# TODO: Move this factory in a library
@implementer(IPolicyForHTTPS)
class SkipCertifContextFactory(object):
    def __init__(self):
        self.default_policy = BrowserLikePolicyForHTTPS()

    def creatorForNetloc(self, hostname, port):
        return ssl.CertificateOptions(verify=False)


class S3Bucket(PythonDataSourcePlugin):
    proxy_attributes = (
        'zScalityS3BucketHost',
        'zScalityS3AccessKey',
        'zScalityS3SecretKey',
    )

    @classmethod
    def config_key(cls, datasource, context):
        log.info('In config_key {} {} {} {}'.format(context.device().id,
                                                 datasource.getCycleTime(context),
                                                 context.id,
                                                 'ScalityS3Bucket'))

        return (context.device().id,
                datasource.getCycleTime(context),
                context.id,
                'ScalityS3Bucket'
        )

    @classmethod
    def params(cls, datasource, context):
        params = {}
        params['bucket_name'] = context.title
        return params


    @inlineCallbacks
    def collect(self, config):
        log.debug('Starting Scality S3Bucket collect')

        ds0 = config.datasources[0]
        zScalityS3BucketHost = ds0.zScalityS3BucketHost
        zScalityS3AccessKey = ds0.zScalityS3AccessKey
        zScalityS3SecretKey = ds0.zScalityS3SecretKey
        result = {'data': []}
        if zScalityS3BucketHost and zScalityS3AccessKey and zScalityS3SecretKey:
            ds0 = config.datasources[0]
            component = ds0.component
            bucket_name = ds0.params['bucket_name']
            agent = Agent(reactor, contextFactory=SkipCertifContextFactory())
            key = ''
            num_objects = 0
            start_time = time.time()
            while True:
                url = 'https://{}/{}/?marker={}'.format(zScalityS3BucketHost, bucket_name, key)
                log.debug('AAA url: {}'.format(url))
                headers = sign_request(url, zScalityS3AccessKey, zScalityS3SecretKey)
                try:
                    response = yield agent.request('GET', url, Headers(headers))
                    response_body = yield readBody(response)

                    soup = BeautifulSoup(response_body, 'xml')
                    contents = soup('Contents')
                    result['data'].extend([int(c.Size.text) for c in contents])
                    page_len = len(contents)
                    num_objects += page_len
                    log.debug('AAA num_objects: {}'.format(num_objects))

                    maxkeys = int(soup.find('MaxKeys').text)
                    if page_len < maxkeys:
                        break
                    last_content = contents[-1]
                    key = quote(last_content.Key.text, safe='-_.~')
                except Exception as e:
                    log.exception('{}: failed to get server data for {}'.format(config.id, ds0))
                    log.exception('{}: Exception: {}'.format(config.id, e))
            result['time'] = time.time() - start_time
            result['num_objects'] = num_objects
        returnValue(result)

    def onSuccess(self, result, config):
        log.debug('Success job - result is {}'.format(result))
        data = self.new_data()

        datasource = config.datasources[0]
        comp_id = datasource.component
        data['values'][comp_id]['s3bucket_num_objects'] = result['num_objects']
        data['values'][comp_id]['s3bucket_response_time'] = result['time']
        log.debug('onSuccess len: {}'.format(len(result['data'])))
        data['values'][comp_id]['s3bucket_bucket_size'] = sum(result['data'])

        log.debug('onSuccess data: {}'.format(data))

        return data

    def onError(self, result, config):
        log.error('Error - result is {}'.format(result))
        # TODO: send event of collection failure
        return {}
