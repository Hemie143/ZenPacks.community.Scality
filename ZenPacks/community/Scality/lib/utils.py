import calendar

# Zope imports
from zope.interface import implementer

# Twisted imports
from twisted.internet import ssl
from twisted.internet.defer import succeed
from twisted.web.iweb import IBodyProducer, IPolicyForHTTPS
from twisted.web.client import BrowserLikePolicyForHTTPS

def get_time_range(t, duration=15):
    '''
    Timestamps must be one of the following intervals for any past day / hour (mm:ss:SS) - start must be one
    of [00:00:000, 15:00:000, 30:00:000, 45:00:000], end must be one of [14:59:999, 29:59:999, 44:59:999, 59:59:999].
    Start must not be greater than end.
    '''
    # TODO: validate duration
    # TODO: check how it works current previous quarter and current quarter ??
    q = int(t - t % 900000)       # 15 minutes * 60 seconds * 1000 milliseconds
    return q - duration * 60 * 1000, q - 1 + 900000


@implementer(IBodyProducer)
class BytesProducer(object):
    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass

@implementer(IPolicyForHTTPS)
class SkipCertifContextFactory(object):
    def __init__(self):
        self.default_policy = BrowserLikePolicyForHTTPS()

    def creatorForNetloc(self, hostname, port):
        return ssl.CertificateOptions(verify=False)