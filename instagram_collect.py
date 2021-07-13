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

# TODO: if I log in, I will need to compute instagram link myself
# https://medium.com/stirtingale/how-to-convert-an-instagram-id-to-a-url-in-php-cbe77ed7aa00
# let's see if skip login could fix this, test after 11:00am Jul 11

def writeSettings(settings_file):
    # web_api = MyClient(auto_patch=True, drop_incompat_keys=False)
    web_api = MyClient(username=credential["user"], password=credential["pwd"], auto_patch=True, drop_incompat_keys=False)
    result = dict(web_api.settings)
    del result['rhx_gis']
    pickle.dump(result, open(settings_file,"wb"))

def readSettings(settings_file):
    return pickle.load(open(settings_file,"rb"))

if not os.path.exists("settingObj"):
    writeSettings("settingObj")

cache_settings = readSettings("settingObj")
# web_api = MyClient(settings=cache_settings, auto_patch=True, drop_incompat_keys=False)
web_api = MyClient(username=credential["user"], password=credential["pwd"], 
    settings=cache_settings, auto_patch=True, drop_incompat_keys=False)

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
    if time.time() - schedules[-1][0] < 30 * 60:
        return
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
            refer_item = item[1:].strip(',').strip('.')
            refer(refer_item)

@log_on_fail(debug_group)
def run():
    schedule = getSchedule()
    if not schedule:
        print('facebook skip, min_interval: 30 minutes')
        return
    channel, page, detail = schedule
    try:
        user_feed_info = web_api.user_feed(str(page), count=10)
    except Exception as e:
        message = 'instagram fetch failed for %s %s: %s' % (detail.get('name'), page, e)
        print(message)
        debug_group.send_message(message)
        return
    with open('tmp_user_feed_info', 'w') as f:
        f.write(str(user_feed_info))
    for post in user_feed_info:
        with open('tmp_post', 'w') as f:
            f.write(str(post))
        post = post['node']
        url = post['link']
        if not detail.get('no_refer'):
            getReferer((post.get('caption') or {}).get('text', ''))
        if existing.contain(url):
            continue
        if post['likes']['count'] < detail.get('likes', 100):
            continue
        if post['is_video']:
            with open('tmp_video_post', 'w') as f:
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