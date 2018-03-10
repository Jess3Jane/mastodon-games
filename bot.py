from mastodon import Mastodon, CallbackStreamListener
from getpass import getpass
from bs4 import BeautifulSoup
from os import path
import subprocess
import hashlib
import binascii
import os
import os.path

api_base_url = "https://botsin.space"

if not path.exists("clientcred.secret"):
    print("No clientcred.secret, registering application")
    Mastodon.create_app("ebooks", api_base_url=api_base_url, to_file="clientcred.secret")

if not path.exists("usercred.secret"):
    print("No usercred.secret, registering application")
    email = input("Email: ")
    password = getpass("Password: ")
    client = Mastodon(client_id="clientcred.secret", api_base_url=api_base_url)
    client.log_in(email, password, to_file="usercred.secret")

def parse_toot(toot):

    soup = BeautifulSoup(toot.content, "html.parser")
    
    # pull the mentions out
    # for mention in soup.select("span.h-card"):
    #     mention.unwrap()

    # for mention in soup.select("a.u-url.mention"):
    #     mention.unwrap()

    # we will destroy the mentions until we're ready to use them
    # someday turbocat, you will talk to your sibilings
    for mention in soup.select("span.h-card"):
        mention.decompose()
    
    # make all linebreaks actual linebreaks
    for lb in soup.select("br"):
        lb.insert_after("\n")
        lb.decompose()

    # make each p element its own line because sometimes they decide not to be
    for p in soup.select("p"):
        p.insert_after("\n")
        p.unwrap()
    
    # strip hashtags
    for ht in soup.select("a.hashtag"):
        ht.decompose()

    # remove links
    for link in soup.select("a"):
        link.decompose()

    mentions = [toot.account]
    mentions += filter(lambda a: a.acct != "letsplay", toot.mentions)
    mentions = list(map(lambda a: "@" + a.acct, mentions))

    lines = list(filter(lambda a: len(a) != 0, map(lambda a: a.strip(), soup.get_text().split("\n"))))

    return (mentions, lines)

def post(text, ident, visibility):
    return client.status_post(text, in_reply_to_id=ident, visibility=visibility)

def post_lots(to, text, m):
    ident = m.status.id
    at_block = " ".join(to) + "\n"
    block_len = 490 - len(at_block)
    sections = text.split("\n")
    current = ""
    for s in sections:
        if len(current) + len(s) > block_len:
            ident = post(at_block + current, ident, m.status.visibility)
            current = ""
        current += s + "\n"
    post(at_block + current, ident, m.status.visibility)

def do_thing(m):
    gamefile = "zork1.z5"
    gamedir = "zork1"

    if m.type != "mention": return 
    mentions, lines = parse_toot(m.status)
    if mentions[0] != "@catinthewired@cybre.space": return

    md5 = hashlib.md5()
    md5.update(mentions[0].encode("utf-8"))
    savefile = "{}.sav".format(binascii.hexlify(md5.digest()).decode("utf-8"))

    newsave = not os.path.isfile("./{}/{}".format(gamedir, savefile))

    for command in lines:
        if "save" in command: return
        if "load" in command: return
        for c in command:
            if c.lower() not in "abcdefghijklmnopqrstuvwxyz 0123456789": return

    command = "\n".join(lines)
    restore = "restore\n{}\n".format(savefile) if not newsave else ""
    c = "{}{}\nsave\n{}\ny\n".format(restore,command,savefile)

    cwd = os.getcwd()
    os.chdir("./{}".format(gamedir))
    p = subprocess.Popen(["dfrotz", gamefile],stdin=subprocess.PIPE,stdout=subprocess.PIPE)
    s = p.communicate(input=c.encode("utf-8"))[0].decode("utf-8")
    os.chdir(cwd)

    pr = False 
    text = []
    for l in s.split("\n"):
        if len(l) == 0: continue
        if "Ok." == l: continue
        if "filename" in l: pr = not pr 
        if l[0] != ">" and pr:
            text += [l]
        if l.startswith(">I"):
            text += [l]
        if "Serial number" in l and newsave:
            pr = True 

    post_lots(mentions, "\n".join(text), m)
    client.notifications_dismiss(m.id)

client = Mastodon(
        client_id="clientcred.secret", 
        access_token="usercred.secret", 
        api_base_url=api_base_url)

notifs = client.notifications()
while len(notifs) > 0:
    for m in notifs:
        do_thing(m)
    notifs = client.fetch_next(notifs)

client.stream_user(CallbackStreamListener(notification_handler=do_thing))
