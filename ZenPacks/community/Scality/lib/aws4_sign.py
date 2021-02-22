import sys
import os
import base64
import datetime
import hashlib
import hmac
from urlparse import urlparse

# References
# https://docs.aws.amazon.com/general/latest/gr/sigv4-create-canonical-request.html
# https://docs.aws.amazon.com/AmazonS3/latest/API/sig-v4-header-based-auth.html

# Key derivation functions. See:
# http://docs.aws.amazon.com/general/latest/gr/signature-v4-examples.html#signature-v4-examples-python
def sign(key, msg):
    return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()


def getSignatureKey(key, dateStamp, regionName, serviceName):
    kDate = sign(('AWS4' + key).encode('utf-8'), dateStamp)
    kRegion = sign(kDate, regionName)
    kService = sign(kRegion, serviceName)
    kSigning = sign(kService, 'aws4_request')
    return kSigning


def get_sign():
    return


def sign_request(url, access_key, secret_key, method='GET', payload='', region='us-east-1', service='s3'):
    """
    This function implements the Signature version 4, and is currently only valid for the S3 service
    :param url:
    :param method:
    :param payload:
    :param region:
    :param service:
    :return:
    """
    url_comp = urlparse(url)

    t = datetime.datetime.utcnow()
    amzdate = t.strftime('%Y%m%dT%H%M%SZ')
    datestamp = t.strftime('%Y%m%d')

    host = url_comp.netloc
    if ':' in host:
        host = host.split(':')[0]
    payload_hash = hashlib.sha256((payload).encode('utf-8')).hexdigest()

    # Create a canonical request
    canonical_headers = 'host:' + host + '\n' + \
                        'x-amz-content-sha256:' + payload_hash + '\n' + \
                        'x-amz-date:' + amzdate + '\n'
    signed_headers = 'host;x-amz-content-sha256;x-amz-date'

    canonical_uri = url_comp.path if url_comp.path else '/'
    canonical_querystring = url_comp.query
    canonical_request = '{0}\n{1}\n{2}\n{3}\n{4}\n{5}'.format(method, canonical_uri, canonical_querystring,
                                                              canonical_headers, signed_headers, payload_hash)

    canonical_hash = hashlib.sha256((canonical_request).encode('utf-8')).hexdigest()

    # Create a string to sign
    algorithm = 'AWS4-HMAC-SHA256'
    credential_scope = datestamp + '/' + region + '/' + service + '/' + 'aws4_request'
    string_to_sign = algorithm + '\n' + amzdate + '\n' + credential_scope + '\n' + canonical_hash
    string_to_sign = '{0}\n{1}\n{2}\n{3}'.format(algorithm, amzdate, credential_scope, canonical_hash)

    # Calculate the signature
    signing_key = getSignatureKey(secret_key, datestamp, region, service)
    signature = hmac.new(signing_key, (string_to_sign).encode('utf-8'), hashlib.sha256).hexdigest()

    # Build the headers
    authorization_header = algorithm + ' ' + \
                           'Credential=' + access_key + '/' + credential_scope + ', ' + \
                           'SignedHeaders=' + signed_headers + ', ' + \
                           'Signature=' + signature

    headers = {'x-amz-date': [amzdate],
               'Authorization': [authorization_header],
               'x-amz-content-sha256': ['e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855'],
               }
    return headers
