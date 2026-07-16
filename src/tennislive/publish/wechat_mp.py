"""微信公众号发文：上传素材 → 新建草稿 →（可选）直接发布.

要求：
- 已认证的公众号（订阅号/服务号均可使用草稿箱与发布接口；未认证号无此权限）
- 公众号后台「基本配置」中把调用方 IP 加入白名单。
  GitHub Actions 的出口 IP 不固定，两种解法：
  1. 设置 WECHAT_API_PROXY 指向一个固定出口 IP 的 HTTP 代理，并把该代理 IP 加白名单；
  2. 不自动发布，只生成内容文件，人工粘贴（默认行为）。

环境变量 / GitHub Secrets：
    WECHAT_APPID        公众号 AppID
    WECHAT_APPSECRET    公众号 AppSecret
    WECHAT_API_PROXY    （可选）固定出口 IP 的代理，如 http://user:pass@1.2.3.4:8080
    WECHAT_AUTHOR       （可选）文章作者名
"""

from __future__ import annotations

import logging
import os
import re
import tempfile
from pathlib import Path

import requests

logger = logging.getLogger(__name__)

API = "https://api.weixin.qq.com/cgi-bin"


class WeChatError(RuntimeError):
    pass


def _explain(errcode: int, errmsg: str) -> str:
    hints = {
        40164: "调用方 IP 不在公众号后台的 IP 白名单中。GitHub Actions 出口 IP 不固定，"
               "需要配置固定 IP 代理（WECHAT_API_PROXY）并把代理 IP 加入白名单。",
        40001: "AppSecret 错误或 access_token 失效，请检查 WECHAT_APPSECRET。",
        48001: "该公众号没有此接口权限（草稿/发布接口需要已认证的公众号）。",
        45009: "接口调用次数超过限额，明天再试或在公众号后台清空配额。",
    }
    hint = hints.get(errcode, "")
    return f"微信接口错误 errcode={errcode} errmsg={errmsg}。{hint}"


class WeChatPublisher:
    def __init__(
        self,
        appid: str | None = None,
        secret: str | None = None,
        proxy: str | None = None,
        timeout: int = 30,
    ):
        self.appid = appid or os.environ.get("WECHAT_APPID", "")
        self.secret = secret or os.environ.get("WECHAT_APPSECRET", "")
        proxy = proxy or os.environ.get("WECHAT_API_PROXY", "")
        if not self.appid or not self.secret:
            raise WeChatError(
                "缺少 WECHAT_APPID / WECHAT_APPSECRET（请在环境变量或 GitHub Secrets 中配置）"
            )
        self.timeout = timeout
        self.session = requests.Session()
        if proxy:
            self.session.proxies = {"https": proxy, "http": proxy}
        self._token: str | None = None

    # ---- 基础 ----

    def _check(self, data: dict) -> dict:
        if isinstance(data, dict) and data.get("errcode") not in (None, 0):
            raise WeChatError(_explain(data["errcode"], data.get("errmsg", "")))
        return data

    def access_token(self) -> str:
        if self._token:
            return self._token
        resp = self.session.get(
            f"{API}/token",
            params={
                "grant_type": "client_credential",
                "appid": self.appid,
                "secret": self.secret,
            },
            timeout=self.timeout,
        )
        data = self._check(resp.json())
        token = data.get("access_token")
        if not token:
            raise WeChatError(f"获取 access_token 失败: {data}")
        self._token = token
        return token

    # ---- 素材 ----

    def upload_thumb(self, image_path: str | Path) -> str:
        """上传封面图为永久素材，返回 thumb_media_id."""
        with open(image_path, "rb") as f:
            resp = self.session.post(
                f"{API}/material/add_material",
                params={"access_token": self.access_token(), "type": "image"},
                files={"media": (Path(image_path).name, f, "image/png")},
                timeout=self.timeout,
            )
        data = self._check(resp.json())
        media_id = data.get("media_id")
        if not media_id:
            raise WeChatError(f"上传封面素材失败: {data}")
        return media_id

    def upload_content_image(self, image_path: str | Path) -> str:
        """上传正文图片（不占素材库配额），返回可嵌入正文的 URL."""
        with open(image_path, "rb") as f:
            resp = self.session.post(
                f"{API}/media/uploadimg",
                params={"access_token": self.access_token()},
                files={"media": (Path(image_path).name, f, "image/png")},
                timeout=self.timeout,
            )
        data = self._check(resp.json())
        url = data.get("url")
        if not url:
            raise WeChatError(f"上传正文图片失败: {data}")
        return url

    # ---- 草稿与发布 ----

    def add_draft(
        self,
        title: str,
        html_content: str,
        thumb_media_id: str,
        digest: str = "",
        author: str | None = None,
    ) -> str:
        """新建草稿，返回草稿 media_id."""
        article = {
            "title": title[:64],
            "author": (author or os.environ.get("WECHAT_AUTHOR", ""))[:8],
            "digest": digest[:120],
            "content": html_content,
            "thumb_media_id": thumb_media_id,
            "need_open_comment": 1,
            "only_fans_can_comment": 0,
        }
        resp = self.session.post(
            f"{API}/draft/add",
            params={"access_token": self.access_token()},
            json={"articles": [article]},
            timeout=self.timeout,
        )
        # requests 的 json= 会把中文转成 \uXXXX，微信接口兼容；但保险起见手动编码
        data = self._check(resp.json())
        media_id = data.get("media_id")
        if not media_id:
            raise WeChatError(f"新建草稿失败: {data}")
        logger.info("公众号草稿创建成功 media_id=%s", media_id)
        return media_id

    def add_image_draft(
        self,
        title: str,
        content: str,
        image_media_ids: list[str],
    ) -> str:
        """新建「图片消息」草稿（小红书式：竖版图片轮播 + 文字），返回 media_id.

        content 为纯文本（支持换行与 emoji），第一张图自动作为封面。
        """
        article = {
            "article_type": "newspic",
            "title": title[:64],
            "content": content[:1000],
            "need_open_comment": 1,
            "only_fans_can_comment": 0,
            "image_info": {
                "image_list": [
                    {"image_media_id": mid} for mid in image_media_ids[:20]
                ]
            },
        }
        resp = self.session.post(
            f"{API}/draft/add",
            params={"access_token": self.access_token()},
            json={"articles": [article]},
            timeout=self.timeout,
        )
        data = self._check(resp.json())
        media_id = data.get("media_id")
        if not media_id:
            raise WeChatError(f"新建图片消息草稿失败: {data}")
        logger.info("公众号图片消息草稿创建成功 media_id=%s", media_id)
        return media_id

    def publish_draft(self, media_id: str) -> str:
        """把草稿提交发布（异步），返回 publish_id."""
        resp = self.session.post(
            f"{API}/freepublish/submit",
            params={"access_token": self.access_token()},
            json={"media_id": media_id},
            timeout=self.timeout,
        )
        data = self._check(resp.json())
        publish_id = data.get("publish_id")
        if not publish_id:
            raise WeChatError(f"提交发布失败: {data}")
        logger.info("公众号发布任务已提交 publish_id=%s", publish_id)
        return str(publish_id)


def _rehost_external_flags(pub: "WeChatPublisher", html: str) -> str:
    """把正文里的外链旗帜小图（flagcdn.com）转存为微信图片 URL.

    微信会过滤非微信域名的正文图片；每面旗帜只上传一次。
    """
    urls = sorted(set(re.findall(r'https://flagcdn\.com/[^"]+\.png', html)))
    for url in urls:
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
                f.write(resp.content)
                tmp = f.name
            wx_url = pub.upload_content_image(tmp)
            html = html.replace(url, wx_url)
            os.unlink(tmp)
        except Exception as e:  # 单面旗帜失败不阻塞发文
            logger.warning("旗帜图转存失败 %s: %s", url, e)
    return html


def publish_article(
    title: str,
    html_content: str,
    cover_image: str | Path,
    content_images: list[Path] | None = None,
    digest: str = "",
    do_publish: bool = False,
) -> dict:
    """一站式：上传封面/正文图 → 建草稿 →（可选）发布.

    正文中若引用本地图片，会先上传并把 <img src> 替换为微信 URL：
    在 html_content 里用占位符 {{IMAGE:文件名}} 引用 content_images 中的图片。
    """
    pub = WeChatPublisher()
    thumb_id = pub.upload_thumb(cover_image)
    html_content = _rehost_external_flags(pub, html_content)

    for img in content_images or []:
        placeholder = f"{{{{IMAGE:{img.name}}}}}"
        if placeholder in html_content:
            url = pub.upload_content_image(img)
            html_content = html_content.replace(
                placeholder,
                f'<img src="{url}" style="width:100%;display:block;margin:12px 0;" />',
            )

    media_id = pub.add_draft(title, html_content, thumb_id, digest=digest)
    result = {"draft_media_id": media_id}
    if do_publish:
        result["publish_id"] = pub.publish_draft(media_id)
    return result


def publish_image_post(
    title: str,
    content: str,
    images: list[Path],
    do_publish: bool = False,
) -> dict:
    """小红书式图片消息：上传卡片图为素材 → 建图片消息草稿 →（可选）发布."""
    if not images:
        raise WeChatError("图片消息至少需要一张图片")
    pub = WeChatPublisher()
    media_ids = [pub.upload_thumb(p) for p in images[:20]]
    media_id = pub.add_image_draft(title, content, media_ids)
    result = {"draft_media_id": media_id}
    if do_publish:
        result["publish_id"] = pub.publish_draft(media_id)
    return result
