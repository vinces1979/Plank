#!/usr/bin/env python

__author__ = "Vince Spicer (vinces1979@gmail.com)"

import sys

from twisted.internet import reactor
from twisted.python  import log

from bot import Factory

HOST, PORT = 'irc.freenode.net', 6667
TRIGGER = "!"
CHANNELS = ["##plankbot"]

if __name__ == '__main__':
    reactor.connectTCP(HOST, PORT, Factory(TRIGGER, CHANNELS))
    log.startLogging(sys.stdout)
    reactor.run()

