""" Simple IRC ranking bot"""

from twisted.internet import task, defer, protocol
from twisted.words.protocols import irc

class PlankIRCProtocol(irc.IRCClient):
    nickname = '_bot_'

    def __init__(self, *args, **kwargs):
        self._namescallback = {}

    def names(self, channel):
        channel = channel.lower()
        d = defer.Deferred()
        if channel not in self._namescallback:
            self._namescallback[channel] = ([], [])
        self._namescallback[channel][0].append(d)
        self.sendLine("NAMES %s" % channel)
        return d

    def irc_RPL_NAMREPLY(self, prefix, params):
        channel = params[2].lower()
        nicklist = params[3].split(' ')
        if channel not in self._namescallback:
            return
        n = self._namescallback[channel][1]
        n += nicklist

    def irc_RPL_ENDOFNAMES(self, prefix, params):
        channel = params[1].lower()
        if channel not in self._namescallback:
            return
        callbacks, namelist = self._namescallback[channel]
        for cb in callbacks:
            cb.callback(namelist)
        del self._namescallback[channel]

    def irc_JOIN(self, prefix, params):
        """
        Called when a user joins a channel.
        """
        nick = prefix.split('!')[0]
        channel = params[-1]
        if nick == self.nickname:
            self.joined(channel)
        else:
            self.handle_nick_join(nick, channel)

    def signedOn(self):
        print "signed on"
        for channel in self.factory.channels:
            print "joining", channel
            self.join(channel)
        if hasattr(self, "afterSignOn"):
            self.afterSignOn()

    def get_names(self, channel):
        self.names(channel).addCallback(self.handle_nicklist, channel)

    def joined(self, channel):
        print "joined", channel
        self.get_names(channel)

    def action(self, user, channel, msg):
        user = user.split('!', 1)[0]
        print user, channel, msg

    def handle_message(self, user, channel, nick, host, message):
        pass

    def privmsg(self, user, channel, message):
        nick, _, host = user.partition('!')
        message = message.strip()
        print "privmsg",  nick, _, host, message
        self.handle_message(user, channel, nick, host, message)
        if not message.startswith(self.factory.trigger):
            return
        command, sep, rest = message.lstrip(self.factory.trigger).partition(' ')
        func = getattr(self, 'command_%s' % command, None)
        if func is None:
            return
        d = defer.maybeDeferred(func, nick, channel, rest)
        d.addErrback(self._show_error)
        if channel.rstrip("_") == self.nickname:
            d.addCallback(self._send_message, nick)
        else:
            d.addCallback(self._send_message, channel, nick)

    def _send_message(self, msg, target, nick=None):
        print "%r %r" % (msg, target)
        if msg is False:
            return
        if nick:
            msg = '%s: %s' % (nick, msg)
        self.msg(target, msg)

    def _show_error(self, failure):
        return failure.getErrorMessage()

    def command_join(self, nick, channel, rest):
        self.join(channel)

    def command_ping(self, nick, channel, rest):
        return 'Pong.'

