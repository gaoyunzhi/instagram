#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml
from telegram_util import log_on_fail
from telegram.ext import Updater
import plain_db
import cached_url
from bs4 import BeautifulSoup
import album_sender
import time
import to_album
import random
import hashlib
import string
import pickle
import os
from instagram_web_api import Client, ClientCompatPatch, ClientError, ClientLoginError

fetchtime = plain_db.load('fetchtime')
referer = plain_db.loadKeyOnlyDB('referer')
with open('credential') as f:
    credential = yaml.load(f, Loader=yaml.FullLoader)

class MyClient(Client):
    @staticmethod
    def _extract_rhx_gis(html):
        options = string.ascii_lowercase + string.digits
        text = ''.join([random.choice(options) for _ in range(8)])
        return hashlib.md5(text.encode())

def writeSettings(user, pwd, settings_file):
    web_api = MyClient(username=user, password=pwd, auto_patch=True, drop_incompat_keys=False)
    result = dict(web_api.settings)
    del result['rhx_gis']
    print(result)
    pickle.dump(result, open(settings_file,"wb"))

def readSettings(settings_file):
    return pickle.load(open(settings_file,"rb"))

if not os.path.exists("settingObj"):
    writeSettings(credential["user"], credential["pwd"], "settingObj")

cache_settings = readSettings("settingObj")
web_api = MyClient(username=credential["user"], password=credential["pwd"], settings=cache_settings)

with open('db/setting') as f:
    setting = yaml.load(f, Loader=yaml.FullLoader)

existing = plain_db.loadKeyOnlyDB('existing')
tele = Updater(credential['bot_token'], use_context=True)
debug_group = tele.bot.get_chat(credential['debug_group'])

def getSchedule():
    schedules = []
    for channel_id, pages in setting.items():
        for page, detail in pages.items():
            schedules.append((fetchtime.get(page, 0), channel_id, page, detail))
    schedules.sort()
    _, channel_id, page, detail = schedules[0]
    fetchtime.update(page, int(time.time()))
    return tele.bot.get_chat(channel_id), page, detail

def refer(item):
    if not referer.add(item):
        return
    debug_group.send_message('Suggest: https://www.instagram.com/' + item)

@log_on_fail(debug_group)
def getReferer(text):
    if not text:
        return
    for item in text.split():
        if item.startswith('@'):
            refer_item = item[1:].strip(',')
            refer(refer_item)

@log_on_fail(debug_group)
def run():
    channel, page, detail = getSchedule()
    try:
        user_feed_info = web_api.user_feed(str(page), count=10)
    except Exception as e:
        print('instagram fetch failed for %s %s: %s' % (detail.get('name'), page, e))
        return
    for post in user_feed_info:
        post = post['node']
        url = post['link']
        if existing.contain(url):
            continue
        getReferer((post.get('caption') or {}).get('text', ''))
        if post['likes']['count'] < detail.get('likes', 100):
            continue
        if post['is_video']:
            with open('tmp_video_post', 'w') as f:
                f.write(str(post))
        with open('tmp_post', 'w') as f:
            f.write(str(post))
        album = to_album.get(post)
        try:
            album_sender.send_v2(channel, album)
        except Exception as e:
            with open('tmp_failed_post', 'w') as f:
                f.write(str(post))
            print('instagram sending fail', url, e)
            continue
        existing.add(url)
        
if __name__ == '__main__':
    run()