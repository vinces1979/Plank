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

def cleanNick(nick):
    nick =  nick.strip("@")
    if nick.lower().endswith("afk"):
        nick = nick[:-3]
    return nick

class IRCProtocol(PlankIRCProtocol):
    nickname = 'plank'
    nicklist_key = "plank:%s:nicks"

    def handle_nicklist(self, nicklist, channel):
        print "storing>>", nicklist, channel
        key = self.nicklist_key % channel
        for nick in nicklist:
            if nick != self.nickname:
                RDB.sadd(key, cleanNick(nick))

    def handle_nick_join(self, nick, channel):
        nick = cleanNick(nick)
        RDB.sadd(self.nicklist_key % channel, nick)

    def afterSignOn(self):
        global BAD_WORDS, DEGRADED
        if self.factory.badwords:
            BAD_WORDS = self.factory.badwords
            DEGRADED  = re.compile( "|".join(r"\b%s\b" % w for w in BAD_WORDS) )

    def handle_message(self, user, channel, nick, host, message):
        print "handle message", user, channel, nick, host, message
        incr = None
        check = Nick_point_re.search(message)
        if check:
            incr = 1 if message.endswith("++") else -1
            nick = cleanNick(check.groups()[0])
            if nick.rstrip("_") == self.nickname:
                self.msg(channel, "thanks but I don't need any stinking points. I once punched Chuck Norris!")
                return
            channel_nicks = RDB.smembers(self.nicklist_key % channel)
            if nick not in channel_nicks:
                print "unknown nick"
                return
            count = RDB.hincrby("plank:%s" % channel, nick, incr)
            self.msg(channel, "%s your ranking is now %s" % (nick, count))
        elif URL_re.search(message):
            url = URL_re.search(message).group()
            incr = 1
            if "reddit.com" in url:
                incr += 1
            count = RDB.hincrby("plank:%s" % channel, nick, incr)
            self.msg(channel, "%s got %s point(s)for sharing their internet awesomeness" % (nick, incr))
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
            "!joke: grab random joke from store",
            "!joketotal: return the number of jokes stored",
            "!players: list the players with points",
            "Extra points:",
            "   Get points for urls posted",
        ]
        for msg in msgs:
            self.msg(channel, msg)
        return False

    def command_badwords(self, nick, channel, rest):
        self.msg(channel, ", ".join(BAD_WORDS))
        return False

    def command_joketotal(self, nick, channel, rest):
        return RDB.scard("jokes")

    def command_joke(self, nick, channel, rest):
        joke = RDB.srandmember("jokes")
        if joke:
            self.msg(channel, joke)
        else:
            self.msg(channel, "Sorry, I am boring and don't know any good jokes")
        return False

    def command_addjoke(self, nick, channel, rest):
        if RDB.sadd("jokes", rest):
            self.msg(channel, "added")
        return False

    def command_deljoke(self, nick, channel, rest):
        if RDB.srem("jokes", rest):
            self.msg(channel, "gone")
        return False

    def command_myrank(self, nick, channel, rest):
        count = RDB.hget("plank:%s" % channel, nick)
        self.msg(channel, "%s your ranking is %s" % (nick, count or 0))
        return False

    def command_rank(self, nick, channel, rest):
        other_nick = rest.rstrip(":")
        data = RDB.hget("plank:%s" % channel, other_nick)
        if not data:
            self.msg(channel, "unknown nick %s" % other_nick)
        else:
            self.msg(channel, "Rank: %s %s" % (other_nick, data))
        return False

    def command_ranks(self, nick, channel, rest):
        print channel
        data = RDB.hgetall("plank:%s" % channel)
        if "_nicks" in data:
            data.pop("_nicks")
        print data
        data = sorted(data.items(), key=lambda nick: int(nick[1]) , reverse=1)
        for nick, value in data:
            self.msg(channel, "%s: %s" % (nick, value))
        return False

    def command_nicklist(self, nick, channel, rest):
       key = "plank:%s:nicks" % channel
       return ", ".join(RDB.smembers(key))

    def command_players(self, nick, channel, rest):
       data = RDB.hgetall("plank:%s" % channel)
       return ", ".join(key for key,value in data.items())

class Factory(protocol.ReconnectingClientFactory):
    protocol = IRCProtocol
    channels = []

    def __init__(self, trigger="!", channels=None, bad=None):
        self.channels = channels or []
        self.trigger = "!"
        self.badwords = bad or []

