"""Data and message handling"""

import re
import cPickle as pickle
from random import choice

from lxml import html
import redis
from twisted.internet import reactor, protocol
from twisted.web import client
from twisted.web.client import HTTPClientFactory, _parse
from bot.client import PlankIRCProtocol

RDB = redis.Redis()

Nick_point_re = re.compile(r"([^\s]+?)([,:\s]*[+-]{2})")

URL_re = re.compile("http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+")
BAD_WORDS = ["lol", "lmfao"]
DEGRADED = re.compile( "|".join(r"\b%s\b" % w for w in BAD_WORDS) )

def cleanNick(nick):
    nick =  nick.strip("@")
    if nick.lower().endswith("afk"):
        nick = nick[:-3]
    return nick

def getPage(url, contextFactory=None, *args, **kwargs):
    scheme, host, port, path = _parse(url)
    factory = HTTPClientFactory(url, *args, **kwargs)
    reactor.connectTCP(host, port, factory)
    return factory

PORNWORDS = ['fuck',
             'pussy',
             'tits',
             'anal',
             'porn',
             'xxx',
             'viagra',
             'sex',
             'cams',
             'blowjob',
             'handjob',
             'threesome',
             'dildo',
             'cock',
             'cum',
             'lemonparty',
             'nudity',
             '100% free',
             'adult video',
             '18+',
             'adult oriented',
             'completely free',
             'cute girls',
             'nsfw',
             'butt',
             'boobs',
             'shemale',
             'dick',
             'ass',
]
PORN_re = re.compile("|".join(r"\b%s\b" % w for w in PORNWORDS), re.I)


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
        count = RDB.hincrby("plank:%s" % channel, nick, 1)
        self.me(channel, "gives %s a point for coming out to play" % (nick))

    def handle_kick(self, op, channel, nick, msg):
        count = RDB.hincrby("plank:%s" % channel, cleanNick(op), -1)
        self.me(channel, "takes a point from %s, and tells them to go sit in the corner. " % op)

    def handle_nick_change(self, oldnick, newnick):
        nick = cleanNick(newnick)
        for channel in self.factory.channels:
            RDB.sadd(self.nicklist_key % channel, nick)

    def afterSignOn(self):
        global BAD_WORDS, DEGRADED
        if self.factory.badwords:
            BAD_WORDS = self.factory.badwords
            DEGRADED  = re.compile( "|".join(r"\b%s\b" % w for w in BAD_WORDS) )

    def url_callback(self, data, factory, url, nick, channel):
        url_type = "something awesome"
        incr = 1
        ct = factory.response_headers['content-type']
        parse_html = False
        extra = ""
        if ct:
            if "image" in ct[0]:
                incr += 1
                url_type = "an image with the class"
            elif "html" in ct[0]:
                parse_html = True
                url_type = "a web page"

        if "reddit.com" in url:
            incr += 1
            url_type = "some reddit words of wisdom"

        prob = 1
        if parse_html:
            words = PORN_re.findall(html.fromstring(data).text_content())
            total = len(words)
            if total <= 2:
                prob = 1
            elif 2 < total < 5:
                prob = 10
            elif 5 >= total < 15:
                prob = 40
            elif total > 15:
                prob = 90
        RDB.hset("plank:urls", url,
                        pickle.dumps({'prob': prob, 'url_type':url_type}))
        self.url_points(nick, channel, incr, prob, url_type)

    def url_points(self, nick, channel, incr, prob, url_type):
        if prob == 10:
            incr += 1
        if prob == 40:
            incr += 2
        if prob == 90:
            incr += 4
        extra = ""
        if url_type == "a web page":
            extra = "[ %s%% chance of porn ]" % prob
        count = RDB.hincrby("plank:%s" % channel, nick, incr)
        self.me(channel, "gives %s %s point%s for sharing %s %s" % (nick, incr, "s" if incr > 1 else "", url_type, extra))

    def handle_message(self, user, channel, nick, host, message):
        print "handle message", user, channel, nick, host, message
        incr = None
        check = Nick_point_re.search(message)
        author = cleanNick(nick)
        if check:
            incr = 1 if message.endswith("++") else -1
            nick = cleanNick(check.groups()[0])
            if nick == author:
                return False
            if nick.rstrip("_") == self.nickname:
                if incr < 0:
                    count = RDB.hincrby("plank:%s" % channel, author, -1)
                    self.me(channel, "takes a point from %s for trying to take points from a bot! *shakes head*" % author)
                else:
                    reasons = [
                               "I once punched Chuck Norris!",
                               "I was created to be better then you.",
                               " .... 42",
                               "your ugly",
                               "I had a threesome with your mom and grandma",
                               "your mom liked it too much last night",
                               "of rule 34",
                               "I am a robot and your not, so play safe",
                               "you like to look at granny porn",
                               "your argument is invalid",
                               "you like goats",
                               ]
                    self.msg(channel, "I don't accept points from you because %s" % choice(reasons))
                return
            channel_nicks = RDB.smembers(self.nicklist_key % channel)
            if nick not in channel_nicks:
                print "unknown nick"
                return
            count = RDB.hincrby("plank:%s" % channel, nick, incr)
            self.msg(channel, "%s your ranking is now %s" % (nick, count))
        elif URL_re.search(message):
            url = URL_re.search(message).group()
            prob = RDB.hget("plank:urls", url)
            if not prob:
                d = getPage(url)
                d.deferred.addCallback(self.url_callback, d, url, nick, channel)
            else:
                url = pickle.loads(prob)
                self.url_points(nick, channel, 1, url['prob'], url['url_type'])
        elif DEGRADED.search(message):
            words = DEGRADED.findall(message)
            total = len(words) * -1
            count = RDB.hincrby("plank:%s" % channel, nick, total)
            self.msg(channel, "%s lost %s point%s for saying %s" % (nick, total , "s" if total > 1 else "", ", ".join(words) ))

    def command_help(self, nick, channel, rest):
        msgs = [
            "nick++ : give a point to nick",
            "nick-- : remove a point from a nick",
            "!badwords: lose a point when you say these words",
            "!myrank: find out your ranking",
            "!rank nick: show the rank for this nick",
            "!ranks: show all ranking for this channel",
            "!ranklist: show a list of ranks for the channel ",
            "!joke: grab random joke from store",
            "!joketotal: return the number of jokes stored",
            "!players: list the players with points",
            "Extra points:",
            "   Get points for urls posted",
        ]
        return msgs

    def command_badwords(self, nick, channel, rest):
        return ", ".join(BAD_WORDS)

    def command_joketotal(self, nick, channel, rest):
        return RDB.scard("jokes")

    def command_joke(self, nick, channel, rest):
        joke = RDB.srandmember("jokes")
        if joke:
            return joke
        else:
            return "Sorry, I am boring and don't know any good jokes"

    def command_addjoke(self, nick, channel, rest):
        if RDB.sadd("jokes", rest):
            return "added"
        return "error"

    def command_deljoke(self, nick, channel, rest):
        if RDB.srem("jokes", rest):
            return "gone"
        return "error"

    def command_myrank(self, nick, channel, rest):
        if rest:
            rest = rest.split(" ")[0].strip()
        count = RDB.hget("plank:%s" % (rest or channel), nick)

        msg = "your ranking is %s" % (count or 0)
        if rest:
            msg += " in %s" % rest
        return msg

    def command_rank(self, nick, channel, rest):
        other_nick = rest.rstrip(":")
        if not other_nick:
            other_nick = nick
        data = RDB.hget("plank:%s" % channel, other_nick)
        if not data:
            return "unknown nick %s" % other_nick
        else:
            return "Rank: %s %s" % (other_nick if other_nick != nick else "", data)


    def command_ranks(self, nick, channel, rest):
        if rest:
            channel = rest.split(" ")[0].strip()
        data = RDB.hgetall("plank:%s" % channel)
        if "_nicks" in data:
            data.pop("_nicks")
        print data
        data = sorted(data.items(), key=lambda nick: int(nick[1]) , reverse=1)
        msgs = []
        for nick, value in data:
            msgs.append("%s: %s" % (nick, value))
        return msgs

    def command_ranklist(self, nick, channel, rest):
        msgs = self.command_ranks(nick, channel, rest)
        return "; ".join(msgs)

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
        self.trigger = trigger
        self.badwords = bad or []

