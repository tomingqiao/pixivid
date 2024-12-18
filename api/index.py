# -*- coding: utf-8 -*-
import os
import threading
import json
import certifi
import pymongo
import requests
from datetime import datetime, timedelta
from flask import Flask, make_response, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

app = Flask(__name__)
app.config.update(  # Vercel部署时使用
    PIXIV_REFRESH_TOKEN=os.getenv('PIXIV_REFRESH_TOKEN'),
    PROXY_HOST=os.getenv('PROXY_HOST'),
    RATE_LIMIT=os.getenv('RATE_LIMIT', '30 per minute'),
    R18_LIMIT=json.loads(os.getenv('R18_LIMIT', 'False').lower()),
    PROXY=json.loads(os.getenv('PROXY', '{}'))
)
# app.config.update(  # 本地测试用
#     PIXIV_REFRESH_TOKEN='',
#     MONGO_URI="",
#     PROXY_HOST='',
#     RATE_LIMIT='30 per minute',
#     R18_LIMIT=False,
#     CACHE_EXPIRE_TIME=259200,
#     PROXY={'http': 'http://127.0.0.1:6667', 'https': 'http://127.0.0.1:6667'}
# )

limiter = Limiter(
    app,
    key_func=get_remote_address,
    default_limits=[app.config['RATE_LIMIT']],

)


R18_TEMPLATE = '''<!DOCTYPE html> <html lang="zh"> <head> <meta charset="UTF-8"> <meta name="viewport" 
content="width=device-width, initial-scale=1.0"> <title>该图片已被屏蔽</title> <head> <body> <h1>该图片已被屏蔽</h1> 
<p>该图片可能涉及r18内容，恰独食了，不给你看(ノω<。)ノ))☆.。</p> <p>您可点击下方地址继续访问</p> <p><a href="{url}" target="_blank">{url}</a></p> 
<p><img src="https://i0.hdslb.com/bfs/album/703118c9b166f1f70d45d983f38eb5756752c1f7.jpg" alt="不可以色色" 
referrerPolicy="no-referrer" height="300" width="300"></p> <h2>更多信息</h2> {info} </body> </html> '''


@app.route('/<image_id>')
def main(image_id):
    access_token = {}
    illust = {}
    pixiv_path = os.path.splitext(image_id)[0]  # 分割提取pid和序号
    pixiv_path_spilt = pixiv_path.split('-', 1)  # 从-分开形成列表，前者为pixiv_id，后者为索引
    try:
        pixiv_id = int(pixiv_path_spilt[0])
        if len(pixiv_path_spilt) != 1:
            illust_index = int(pixiv_path_spilt[1])
        else:
            illust_index = 1
    except ValueError:
        return "请求格式错误", 404  # 输入参数错误
    print('[Request_Args]', pixiv_id, illust_index)
    thread_get_pixiv_token = threading.Thread(target=get_pixiv_token, args=(access_token,))
    thread_get_pixiv_token.start()
    thread_get_pixiv_token.join()  # 剩下没有缓存的情况
    illust = get_illust(pixiv_id, access_token['value'])
    response = return_response(illust, illust_index)
    return response



def get_pixiv_token(access_token: dict):
    refresh_token = app.config['PIXIV_REFRESH_TOKEN']

    response = requests.post(  # 刷新token
            "https://oauth.secure.pixiv.net/auth/token",
            data={
                "client_id": "MOBrBDS8blbauoSck0ZfDbtuzpyT",
                "client_secret": "lsACyCD94FhDUtGTXi3QzcFE2uU1hqtDaKeqrdwj",
                "grant_type": "refresh_token",
                "include_policy": "true",
                "refresh_token": refresh_token,
            },
            headers={"User-Agent": "PixivAndroidApp/5.0.234 (Android 11; Pixel 5)"}, proxies=app.config['PROXY']
        )
    data = response.json()
    print('[Token_Refresh]', data)
    access_token.update({
            'value': data['access_token'],
            'expireAt': round(datetime.now().timestamp()) + 3600,
            'refresh': True
        })

def get_illust(pid: int, access_token: str):
    illust = {}
    url = 'https://app-api.pixiv.net/v1/illust/detail'
    headers = {
        'host': 'app-api.pixiv.net',
        'app-os': 'ios',
        'app-os-version': '14.6',
        'user-agent': 'PixivIOSApp/7.13.3 (iOS 14.6; iPhone13,2)',
        'Authorization': 'Bearer %s' % access_token,
        'accept-language': 'zh-cn'
    }
    params = {'illust_id': pid}
    data = requests.get(url=url, headers=headers, params=params, proxies=app.config['PROXY']).json()
    print('[Illust_Get]', data)
    try:
        page_count = data['illust']['page_count']
        images_url = []
        if page_count == 1:  # 单张图
            image_url = data['illust']['meta_single_page']['original_image_url']
            images_url.append(image_url)
        else:  # 多张图
            meta_pages = data['illust']['meta_pages']
            for meta in meta_pages:
                image_url = meta['image_urls']['original']
                images_url.append(image_url)
        illust = {
            'cache': False,
            'pid': data['illust']['id'],
            'type': 0,
            'images_url': images_url,
            'sanity_level': data['illust']['sanity_level']
        }
        return illust
    except KeyError:  # 处理返回错误信息的情况
        user_message = data['error']['user_message']
        sys_message = data['error']['message']
        if user_message != '':  # 404的情况
            illust = {
                'pid': pid,
                'type': 404,
                'message': user_message,
                'cache': False
            }
        elif sys_message != '':  # Rate Limit的情况
            illust = {
                'type': 500,
                'message': sys_message,
                'cache': False
            }
        return illust

def return_response(illust, illust_index):
    if illust['type'] == 0:
        if len(illust['images_url']) >= illust_index:  # 如果索引在范围内
            img_url = illust['images_url'][illust_index - 1]
            sanity_level = illust['sanity_level']
            if app.config['R18_LIMIT'] is False or sanity_level <= 4 or request.cookies.get('bypass', 0,
                                                                                            type=int) == 1:  # 任意一个条件满足都可不进行屏蔽
                img_proxy_url = img_url.replace('i.pximg.net', app.config['PROXY_HOST'])
                cookie_domain = app.config['PROXY_HOST'].split('.')[-2] + '.' + app.config['PROXY_HOST'].split('.')[-1]
                headers = {'Location': img_proxy_url,
                           'Set-Cookie': 'access=1; Max-Age=15; Domain={0}; Secure; HttpOnly'.format(cookie_domain)}
                return make_response('<html></html>', 307, headers)
            else:
                img_proxy_url = img_url.replace('i.pximg.net', 'i.pixiv.re')
                info = json.dumps(illust)
                return make_response(R18_TEMPLATE.format(url=img_proxy_url, info=info), 403)
        else:  # 索引超出范围
            return make_response('超过该id图片数量上限', 404)
    elif illust['type'] == 404:
        return make_response('该图片不存在，或者缓存未刷新', 404)
    elif illust['type'] == 500:
        return make_response('当前请求过多，请稍后再试', 500)


if __name__ == '__main__':
    app.run(debug=True)
