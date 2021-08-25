#!/usr/bin/env python3
# -*- coding: utf-8 -*-

name = 'instagram_to_album'

from telegram_util import AlbumResult as Result
import hanzidentifier
from telegram_util import isCN
from opencc import OpenCC

cc = OpenCC('tw2sp')

def shouldSimplify(text):
    for c in text:
        if isCN(c) and not hanzidentifier.is_simplified(c):
            return True
    return False

def simplify(text):
    if shouldSimplify(text):
        return cc.convert(text)
    return text

def getImgs(content):
    for node in content['edges']:
        yield node['node']['images']['standard_resolution']['url']

def get(content):
    result = Result()
    result.url = content['link']
    result.cap_html_v2 = simplify((content.get('caption') or {}).get('text') or '')
    if 'video_url' in content:
        result.video = content['video_url']
        return result
    if 'edge_sidecar_to_children' in content:
        result.imgs = list(getImgs(content['edge_sidecar_to_children']))
    else:
        result.imgs = [content['images']['standard_resolution']['url']]
    return result