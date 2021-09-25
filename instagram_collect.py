#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import yaml
from telegram_util import log_on_fail, isCN
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
stale = plain_db.loadKeyOnlyDB('stale')
referer_detail = plain_db.load('referer_detail', isIntValue = False)
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
# web_api = MyClient(username=credential["user"], password=credential["pwd"], 
#     settings=cache_settings, auto_patch=True, drop_incompat_keys=False)

with open('db/setting') as f:
    setting = yaml.load(f, Loader=yaml.FullLoader)

existing = plain_db.loadKeyOnlyDB('existing')
tele = Updater(credential['bot_token'], use_context=True)
debug_group = tele.bot.get_chat(credential['debug_group'])
translate_channel = tele.bot.get_chat(credential['translate_channel'])

GAP_HOUR = 1.5

def getSchedule():
    schedules = []
    include_stale = random.random() < 0.1
    for channel_id, pages in setting.items():
        for page, detail in pages.items():
            if page in stale.items() and not include_stale:
                continue
            schedules.append((fetchtime.get(page, 0), channel_id, page, detail))
    schedules.sort()
    if time.time() - schedules[-1][0] < GAP_HOUR * 60 * 60:
        return
    _, channel_id, page, detail = schedules[0]
    fetchtime.update(page, int(time.time()))
    return tele.bot.get_chat(channel_id), page, detail

def refer(item, detail):
    if not referer_detail.get(item):
        referer_detail.update(item, detail)
    if referer_detail.get(item) == detail:
        return
    if not referer.add(item):
        return
    debug_group.send_message('Suggest: https://www.instagram.com/' + item)

@log_on_fail(debug_group)
def getReferer(text, detail):
    if not text:
        return
    for item in text.split():
        if item.startswith('@'):
            refer_item = item[1:].strip(',').strip('.')
            refer(refer_item, detail)

@log_on_fail(debug_group)
def run():
    schedule = getSchedule()
    if not schedule:
        print('instagram skip, min_interval: %s hours' % GAP_HOUR)
        return
    channel, page, detail = schedule
    web_api = MyClient(username=credential["user"], password=credential["pwd"], 
        settings=cache_settings, auto_patch=True, drop_incompat_keys=False)
    try:
        user_feed_info = web_api.user_feed(str(page), count=10)
    except Exception as e:
        message = 'instagram fetch failed for %s %s: %s' % (detail.get('name'), page, e)
        print(message)
        debug_group.send_message(message)
        return
    with open('tmp_user_feed_info', 'w') as f:
        f.write(str(user_feed_info))
    latest_create_at = 0
    for post in user_feed_info:
        with open('tmp_post', 'w') as f:
            f.write(str(post))
        post = post['node']
        url = post['link']
        if not detail.get('no_refer'):
            getReferer((post.get('caption') or {}).get('text', ''), url)
        latest_create_at = max(int(post['created_time']), latest_create_at)
        if existing.contain(url):
            continue
        if post['likes']['count'] < detail.get('likes', 100):
            continue
        if post['is_video']:
            with open('tmp_video_post', 'w') as f:
                f.write(str(post))
        album = to_album.get(post)
        if isCN(album.cap_html_v2):
            backup_channel = debug_group
        elif channel.id == -1001216837149:
            backup_channel = translate_channel
        else:
            backup_channel = None
        try:
            album_sender.send_v2(channel, album)
            if backup_channel:
                album_sender.send_v2(backup_channel, album.toPlain())
        except Exception as e:
            with open('tmp_failed_post', 'w') as f:
                f.write(str(post))
            print('instagram sending fail', url, e)
            continue
        existing.add(url)
    if latest_create_at != 0:
        if time.time() - latest_create_at > 60 * 24 * 60 * 60:
            stale.add(page)
        else:
            stale.remove(page)
        
if __name__ == '__main__':
    run()