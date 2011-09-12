"""Data and message handling"""

import re

import redis
from twisted.internet import protocol

from bot.client import PlankIRCProtocol

RDB = redis.Redis()

Nick_re = re.compile(r"(.*?\w+)([:+]*)")

class IRCProtocol(PlankIRCProtocol):
    nickname = 'plank'

    def _store_names(self, nicklist, channel):
        nicks = [x.strip("@") for x in nicklist if x != self.nickname]
        RDB.hset("plank:%s" % channel, "_nicks", nicks)

    def handle_message(self, user, channel, nick, host, message):
        incr = None
        if message.endswith("++"):
            incr = 1
        elif message.endswith("--"):
            incr = -1
        if incr is not None:
            check = Nick_re.search(nick)
            if check:
                nick = check.groups()[0]
            count = RDB.hincrby("plank:%s" % channel, nick, incr)
            self.msg(channel, "%s your ranking is now %s" % (nick, count))

    def command_help(self, nick, channel, rest):
        msgs = [
            "nick++ : give a point to nick",
            "nick-- : remove a point from a nick",
            "!myrank: find out your ranking",
            "!rank nick: show the rank for this nick",
            "!ranks: show all ranking for this channel",
            "!players: list the players with points",
        ]
        for msg in msgs:
            self.msg(channel, msg)
        return False

    def command_myrank(self, nick, channel, rest):
        count = RDB.hget("plank:%s" % channel, nick)
        self.msg(channel, "%s your ranking is %s" % (nick, count or 0))
        return False

    def command_rank(self, nick, channel, rest):
        other_nick = rest.rstrip(":")
        data = RDB.hget("plank:%s" % channel, other_nick)
        self.msg(channel, "Rank: %s %s" % (other_nick, data))
        return False

    def command_ranks(self, nick, channel, rest):
        data = RDB.hgetall("plank:%s" % channel)
        data.pop("_nicks")
        data = sorted(data.items(), key=lambda nick: int(nick[1]) , reverse=1)
        for nick, value in data:
            self.msg(channel, "%s: %s" % (nick, value))
        return False

    def command_players(self, nick, channel, rest):
       data = RDB.hgetall("plank:%s" % channel)
       return ", ".join(key for key,value in data.items() if value and key != "_nicks")

class Factory(protocol.ReconnectingClientFactory):
    protocol = IRCProtocol
    channels = []

    def __init__(self, trigger="!", channels=None):
        self.channels = channels or []
        self.trigger = "!"

