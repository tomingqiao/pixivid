# pixiv

pixiv图片代理，参考<https://pixiv.cat>

## 使用

在链接后输入pid，如

```
https://h.pixiv.ddns-ip.net/34844544
```

或在pid后指定序号，如

```
https://h.pixiv.ddns-ip.net/34844544-1
```

## 工作原理

用户发出请求后，通过环境变量中的refresh_token请求pixiv的api刷新access_token。

使用access_token请求pixiv的api获取图片数据，返回给用户。

## 部署方法

1. 准备好pixiv的`refresh_token`
    - 使用[该脚本](https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362)获取`refresh_token`
2. 搭建图片反向代理
    - 有能力者可以自建反向代理服务器，反向代理`i.pximg.net`
    - 若无法自建反向代理服务器，可以使用Cloudflare的服务
        - 若有域名，可将域名通过NS/CDN方式接入Cloudflare，记录类型选择`CNAME`，名称根据你的需要填入，内容填入`i.pximg.net`，并开启代理。然后在`规则->转换规则`处，创建`修改请求头`规则，如下图设置![7vdVLq.jpg](https://s4.ax1x.com/2022/01/28/7vdVLq.jpg)
        - 若无域名，则使用Cloudflare Workers搭建反向代理，每日100,000次请求，参考代码来自[pixiv.cat](https://pixiv.re/reverseproxy.html)

            ```javascript
            addEventListener("fetch", event => {
            let url = new URL(event.request.url);
            url.hostname = "i.pximg.net";

            let request = new Request(url, event.request);
            event.respondWith(
                fetch(request, {
                headers: {
                    'Referer': 'https://www.pixiv.net/',
                    'User-Agent': 'Cloudflare Workers'
                }
                })
              );
            });
            ```

            不过由于workers自己生成的域名被墙，无法访问，还是需要域名路由。
3. 部署到[Vercel](https://vercel.com)
    1. 点击按钮[![Vercel](https://vercel.com/button)](https://vercel.com/import/project?template=https://github.com/tomingqiao/pixivid)
    2. 在部署时配置环境变量
    `PIXIV_REFRESH_TOKEN`为步骤1获取的`refresh_token`，`PROXY_HOST`为步骤2配置的反向代理服务器host，注意不要有`http/https`的协议头。
    同样由于Vercel自己生成的域名被墙，无法访问，需要自定义域名，或类似上面的方式代理Vercel自己生成的域名。

## 感谢

[lrhtony/pixiv](https://github.com/lrhtony/pixiv)

[upbit/pixivpy](https://github.com/upbit/pixivpy)

[ZipFile](https://gist.github.com/ZipFile/c9ebedb224406f4f11845ab700124362)

[alisaifee/flask-limiter](https://github.com/alisaifee/flask-limiter)
