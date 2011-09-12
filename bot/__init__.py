"""Data and message handling"""

import re

import redis
from twisted.internet import protocol

from bot.client import PlankIRCProtocol

RDB = redis.Redis()

Nick_point_re = re.compile(r"(.*?\w+)([,:\s]*[+-]{2})$")
URL_re = re.compile("http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")

BAD_WORDS = ["lol", "lmfao"]
DEGRADED = re.compile( "|".join(r"\b%s\b" % w for w in BAD_WORDS) )

class IRCProtocol(PlankIRCProtocol):
    nickname = 'plank'

    def _store_names(self, nicklist, channel):
        nicks = [x.strip("@") for x in nicklist if x != self.nickname]
        RDB.hset("plank:%s" % channel, "_nicks", nicks)

    def afterSignOn(self):
        global BAD_WORDS, DEGRADED
        if self.factory.badwords:
            BAD_WORDS = self.factory.badwords
            DEGRADED  = re.compile( "|".join(r"\b%s\b" % w for w in BAD_WORDS) )

    def handle_message(self, user, channel, nick, host, message):
        print "hanlde message", user, channel, nick, host, message
        incr = None
        check = Nick_point_re.search(message)
        if check:
            incr = 1 if message.endswith("++") else -1
            nick = check.groups()[0]
            if nick.rstrip("_") == self.nickname:
                self.msg(channel, "thanks but I don't need any stinking points. I once punch Chuck Norris!")
                return
            count = RDB.hincrby("plank:%s" % channel, nick, incr)
            self.msg(channel, "%s your ranking is now %s" % (nick, count))
        elif URL_re.search(message):
            url = URL_re.search(message).group()
            incr = 1
            if "reddit.com" in url:
                incr += 1
            count = RDB.hincrby("plank:%s" % channel, nick, incr)
            self.msg(channel, "%s got %s poinst(s)for sharing their internet awesomeness" % (nick, incr))
        elif DEGRADED.search(message):
            print "decgraded word found", channel, nick
            count = RDB.hincrby("plank:%s" % channel, nick, -1)
            self.msg(channel, "%s lost a point for saying %s" % (nick, DEGRADED.search(message).group()))

    def command_help(self, nick, channel, rest):
        msgs = [
            "nick++ : give a point to nick",
            "nick-- : remove a point from a nick",
            "!badwords: lose a point when you say these words",
            "!myrank: find out your ranking",
            "!rank nick: show the rank for this nick",
            "!ranks: show all ranking for this channel",
            "!players: list the players with points",
            "Extra points:",
            "   Get a point for every url posted",
        ]
        for msg in msgs:
            self.msg(channel, msg)
        return False

    def command_badwords(self, nick, channel, rest):
        self.msg(channel, ", ".join(BAD_WORDS))
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

    def __init__(self, trigger="!", channels=None, bad=None):
        self.channels = channels or []
        self.trigger = "!"
        self.badwords = bad or []

