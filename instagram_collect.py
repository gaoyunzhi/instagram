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
from instagram_web_api import Client, ClientCompatPatch, ClientError, ClientLoginError

class MyClient(Client):
    @staticmethod
    def _extract_rhx_gis(html):
        options = string.ascii_lowercase + string.digits
        text = ''.join([random.choice(options) for _ in range(8)])
        return hashlib.md5(text.encode())

web_api = MyClient(auto_patch=True, drop_incompat_keys=False)

with open('credential') as f:
    credential = yaml.load(f, Loader=yaml.FullLoader)

with open('db/setting') as f:
    setting = yaml.load(f, Loader=yaml.FullLoader)

existing = plain_db.loadKeyOnlyDB('existing')
tele = Updater(credential['bot_token'], use_context=True)
debug_group = tele.bot.get_chat(credential['debug_group'])

@log_on_fail(debug_group)
def run():
    sent = False
    for channel_id, pages in setting.items():
        channel = tele.bot.get_chat(channel_id)
        schedule = list(pages.items())
        random.shuffle(schedule)
        for page, detail in schedule[:1]:
            try:
                user_feed_info = web_api.user_feed(page, count=10)
            except Exception as e:
                print('instagram fetch failed', page, str(e))
                

            for post in user_feed_info:
                post = post['node']
                url = post['link']
                if existing.contain(url):
                    continue
                if post['likes']['count'] < detail.get('likes', 100):
                    continue
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