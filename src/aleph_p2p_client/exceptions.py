class P2PClientException(Exception):
    ...

class InternalServiceException(P2PClientException):
    ...

class DialWrongPeerException(P2PClientException):
    ...

class DialFailedException(P2PClientException):
    ...
