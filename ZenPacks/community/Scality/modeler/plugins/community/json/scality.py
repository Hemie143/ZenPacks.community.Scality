# stdlib Imports
import json
import urllib

# Twisted Imports
from twisted.internet.defer import inlineCallbacks, returnValue, DeferredList
from twisted.web.client import Agent, readBody
from twisted.internet import reactor
from twisted.web.http_headers import Headers

# Zenoss Imports
from Products.DataCollector.plugins.CollectorPlugin import PythonPlugin


class scality(PythonPlugin):

    relname = 'scalityRings'
    modname = 'ZenPacks.community.scality.ScalityRing'

    requiredProperties = (
        'zScalityUsername',
        'zScalityPassword',
    )

    deviceProperties = PythonPlugin.deviceProperties + requiredProperties

    @inlineCallbacks
    def collect(self, device, log):
        """Asynchronously collect data from device. Return a deferred/"""
        log.info('%s: collecting data', device.id)

        zScalityUsername = getattr(device, 'zScalityUsername', None)
        zScalityPassword = getattr(device, 'zScalityPassword', None)

        if not zScalityUsername:
            log.error('%s: %s not set.', device.id, 'zScalityUsername')
            returnValue(None)

        deferreds = []
        responses = []

        agent = Agent(reactor)
        headers = {"User-Agent": ["Mozilla/3.0Gold"],
                   }

        '''
        for NwsState in NwsStates:
            if NwsState:
                try:
                    url = 'https://api.weather.gov/stations?state={query}'.format(query=urllib.quote(NwsState))
                    response = yield agent.request('GET', url, Headers(headers))
                    response_body = yield readBody(response)
                    response_body = json.loads(response_body)
                    responses.append(response_body)
                except Exception, e:
                    log.error('%s: %s', device.id, e)
                    returnValue(None)
                for feature in response_body.get('features'):
                    url = 'https://api.weather.gov/stations/{query}'.format(
                        query=urllib.quote(feature['properties']['stationIdentifier']))
                    d = agent.request('GET', url, Headers(headers))
                    d.addCallback(readBody)
                    deferreds.append(d)
        results = yield DeferredList(deferreds, consumeErrors=True)
        '''
        returnValue((responses, results))

    def process(self, device, results, log):
        rm = self.relMap()

        return rm