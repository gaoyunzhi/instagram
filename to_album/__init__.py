#!/usr/bin/env python3
# -*- coding: utf-8 -*-

name = 'instagram_to_album'

from telegram_util import AlbumResult as Result

def getImgs(content):
	for node in content['edges']:
		yield node['node']['images']['standard_resolution']['url']

def get(content):
    result = Result()
    result.url = content['link']
    result.cap_html_v2 = content['caption']['text']
    result.imgs = list(getImgs(content['edge_sidecar_to_children']))
    return result