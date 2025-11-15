import os
import random
import asyncio
from typing import Optional
from urllib.parse import urlparse

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, StarTools
from astrbot.api import logger
from astrbot.api import AstrBotConfig

# 异步HTTP请求库
import aiohttp
from PIL import Image

# PHub库
from phub import Client

from phub.errors import (
    ClientAlreadyLogged,
    LoginFailed,
    URLError,
    ParsingError,
    MaxRetriesExceeded,
    NoResult,
    InvalidCategory,
    VideoError,
    RegionBlocked,
    PremiumVideo,
)


class PornHubPlugin(Star):
    def __init__(self, context: Context, config: AstrBotConfig):
        super().__init__(context)
        self.config = config
        data_dir = StarTools.get_data_dir("astrbot_plugin_pornhub")
        data_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir = str(data_dir / "temp")
        os.makedirs(self.temp_dir, exist_ok=True)
        self.http_client: Optional[aiohttp.ClientSession] = None
        self.phub_client: Optional[Client] = None

    async def initialize(self):
        """插件初始化方法"""
        try:
            # 初始化PHub客户端
            language = self.config.get("phub_language", "cn") if self.config else "cn"
            email = self.config.get("phub_login_email", "") if self.config else ""
            password = self.config.get("phub_login_password", "") if self.config else ""

            # 只有当邮箱和密码都提供时才登录
            login = bool(email and password)

            self.phub_client = Client(
                email=email or None,
                password=password or None,
                language=language,
                login=login,
            )

            # 如果提供了登录信息，尝试登录
            if login:
                try:
                    if self.phub_client.login():
                        logger.info("PHub登录成功")
                    else:
                        logger.warning("PHub登录失败")
                except LoginFailed as e:
                    logger.error(f"PHub登录失败: {e}")
                except ClientAlreadyLogged as e:
                    logger.info(f"PHub客户端已登录: {e}")
                except Exception as e:
                    logger.error(f"PHub登录异常: {e}")

            logger.info("PornHub插件初始化完成，PHub客户端已配置")
        except Exception as e:
            logger.error(f"插件初始化失败: {e}")

    async def initialize_async(self):
        """异步初始化HTTP客户端"""
        try:
            # 初始化HTTP客户端
            proxy = self.config.get("proxy", "") if self.config else ""
            timeout = self.config.get("timeout", 30) if self.config else 30

            connector = aiohttp.TCPConnector(limit=10)
            timeout_config = aiohttp.ClientTimeout(total=timeout)

            # 正确的代理配置方式
            if proxy:
                self.http_client = aiohttp.ClientSession(
                    connector=connector, timeout=timeout_config, proxy=proxy
                )
            else:
                self.http_client = aiohttp.ClientSession(
                    connector=connector, timeout=timeout_config
                )

            logger.info("HTTP客户端初始化完成")
        except Exception as e:
            logger.error(f"HTTP客户端初始化失败: {e}")

    async def terminate(self):
        """插件销毁方法，清理临时文件"""
        import shutil

        try:
            # 关闭HTTP客户端
            if self.http_client:
                await self.http_client.close()

            # 清理临时文件
            shutil.rmtree(self.temp_dir)
            logger.info("PornHub插件临时文件清理完成")
        except Exception as e:
            logger.error(f"清理临时文件失败: {e}")

    @filter.command("ph", alias={"pornhub", "视频封面"})
    async def get_pornhub_video(self, event: AstrMessageEvent):
        """获取PornHub随机视频封面并打码发送"""
        try:
            yield event.plain_result("正在获取PornHub视频封面，请稍候...")

            # 确保HTTP客户端已初始化
            if not self.http_client:
                await self.initialize_async()

            if not self.phub_client:
                yield event.plain_result("PHub客户端未初始化")
                return

            # 获取PornHub首页推荐视频
            try:
                # 首先尝试使用HubTraffic API
                try:
                    query = self.phub_client.search_hubtraffic("popular", sort="recent")
                    videos = list(query.sample(max=20))  # 获取最多20个视频
                except Exception as e:
                    logger.warning(f"HubTraffic API失败，尝试普通搜索: {e}")
                    # 如果HubTraffic失败，尝试普通搜索
                    search_terms = ["popular", "recommended", "trending", "featured"]
                    selected_term = random.choice(search_terms)
                    query = self.phub_client.search(selected_term, sort="recent")
                    videos = list(query.sample(max=20))  # 获取最多20个视频
            except (ParsingError, MaxRetriesExceeded) as e:
                logger.error(f"获取视频列表失败: {e}")
                yield event.plain_result("获取视频列表失败，请稍后再试")
                return
            except Exception as e:
                logger.error(f"获取视频列表异常: {e}")
                yield event.plain_result("获取视频列表异常，请稍后再试")
                return

            if not videos:
                yield event.plain_result("未找到视频，请稍后再试")
                return

            # 随机选择一个视频
            selected_video = random.choice(videos)

            # 下载图片
            image_path = await self.download_phub_image(selected_video.image)
            if not image_path:
                yield event.plain_result("下载图片失败，请稍后再试")
                return

            # 打码处理
            censored_image_path = await self.censor_image(image_path)
            if not censored_image_path:  # 如果打码失败，censored_image_path为空字符串
                yield event.plain_result("图片处理失败，为确保安全不发送图片")
                return

            # 发送图片
            yield event.image_result(censored_image_path)

            # 根据配置决定是否发送视频信息
            return_details = (
                self.config.get("return_details", True) if self.config else True
            )
            if return_details:
                try:
                    info_text = f"标题: {selected_video.title}\n时长: {selected_video.duration}\n观看次数: {selected_video.views}\n链接: {selected_video.url}"
                    yield event.plain_result(info_text)
                except Exception as e:
                    logger.error(f"获取视频信息失败: {e}")
                    yield event.plain_result("获取视频信息失败")

        except Exception as e:
            logger.error(f"获取PornHub视频封面失败: {e}")
            yield event.plain_result(f"处理失败: {str(e)}")

    @filter.command("ph_search", alias={"phs", "视频搜索"})
    async def search_pornhub_videos(self, event: AstrMessageEvent, query: str):
        """搜索PornHub视频"""
        try:
            yield event.plain_result(f"正在搜索PornHub视频: {query}，请稍候...")

            if not self.phub_client:
                yield event.plain_result("PHub客户端未初始化")
                return

            # 从配置获取搜索参数
            sort = (
                self.config.get("search_default_sort", "recent")
                if self.config
                else "recent"
            )
            period = (
                self.config.get("search_default_period", "all")
                if self.config
                else "all"
            )
            max_results = (
                self.config.get("max_search_results", 10) if self.config else 10
            )

            # 执行搜索
            try:
                # 首先尝试使用HubTraffic API
                try:
                    search_query = self.phub_client.search_hubtraffic(
                        query, sort=sort, period=period
                    )
                    videos = list(search_query.sample(max=max_results))
                except Exception as e:
                    logger.warning(f"HubTraffic API搜索失败，尝试普通搜索: {e}")
                    # 如果HubTraffic失败，尝试普通搜索
                    search_query = self.phub_client.search(
                        query, sort=sort, period=period
                    )
                    videos = list(search_query.sample(max=max_results))
            except (InvalidCategory, NoResult) as e:
                logger.error(f"搜索无结果: {e}")
                yield event.plain_result("未找到相关视频")
                return
            except (ParsingError, MaxRetriesExceeded) as e:
                logger.error(f"搜索失败: {e}")
                yield event.plain_result("搜索失败，请稍后再试")
                return
            except Exception as e:
                logger.error(f"搜索异常: {e}")
                yield event.plain_result("搜索异常，请稍后再试")
                return

            if not videos:
                yield event.plain_result("未找到相关视频")
                return

            # 随机选择一个视频
            selected_video = random.choice(videos)

            # 下载图片
            image_path = await self.download_phub_image(selected_video.image)
            if not image_path:
                yield event.plain_result("下载图片失败，请稍后再试")
                return

            # 打码处理
            censored_image_path = await self.censor_image(image_path)
            if not censored_image_path:  # 如果打码失败，censored_image_path为空字符串
                yield event.plain_result("图片处理失败，为确保安全不发送图片")
                return

            # 发送图片
            yield event.image_result(censored_image_path)

            # 根据配置决定是否发送视频信息
            return_details = (
                self.config.get("return_details", True) if self.config else True
            )
            if return_details:
                try:
                    info_text = f"标题: {selected_video.title}\n时长: {selected_video.duration}\n观看次数: {selected_video.views}\n链接: {selected_video.url}"
                    yield event.plain_result(info_text)
                except Exception as e:
                    logger.error(f"获取视频信息失败: {e}")
                    yield event.plain_result("获取视频信息失败")

        except Exception as e:
            logger.error(f"搜索PornHub视频失败: {e}")
            yield event.plain_result(f"搜索失败: {str(e)}")

    @filter.command("ph_video", alias={"phv", "视频详情"})
    async def get_pornhub_video_details(self, event: AstrMessageEvent, viewkey: str):
        """获取PornHub视频详情"""
        yield event.plain_result("正在获取视频详情，请稍候...")

        # 确保HTTP客户端已初始化
        if not self.http_client:
            await self.initialize_async()

        if not self.phub_client:
            yield event.plain_result("PHub客户端未初始化")
            return

        # 构建完整的视频URL
        video_url = f"https://www.pornhub.com/view_video.php?viewkey={viewkey}"

        # 获取视频对象
        video = None
        try:
            video = self.phub_client.get(video_url)
        except (URLError, VideoError) as e:
            logger.error(f"视频URL无效或视频不可用: {e}")
            yield event.plain_result("视频URL无效或视频不可用")
            return
        except RegionBlocked as e:
            logger.error(f"视频在您所在的地区被限制: {e}")
            yield event.plain_result("视频在您所在的地区被限制访问")
            return
        except PremiumVideo as e:
            logger.error(f"这是Premium视频: {e}")
            yield event.plain_result("这是Premium视频，需要订阅才能访问")
            return
        except (ParsingError, MaxRetriesExceeded) as e:
            logger.error(f"获取视频详情失败: {e}")
            yield event.plain_result("获取视频详情失败，请稍后再试")
            return
        except Exception as e:
            logger.error(f"获取视频异常: {e}")
            yield event.plain_result("获取视频异常，请稍后再试")
            return

        # 下载图片
        image_path = await self.download_phub_image(video.image)
        image_sent = False

        if image_path:
            # 打码处理
            censored_image_path = await self.censor_image(image_path)
            if censored_image_path:  # 如果打码成功
                # 发送图片
                yield event.image_result(censored_image_path)
                image_sent = True
            else:
                logger.warning("图片打码失败，不发送图片")
        else:
            logger.warning("图片下载失败，继续获取视频信息")

        # 发送视频详细信息
        # 禁用查询模拟以避免Regex错误
        if hasattr(video, "ALLOW_QUERY_SIMULATION"):
            video.ALLOW_QUERY_SIMULATION = False

        # 使用更安全的方式获取属性，避免Regex错误
        # 先获取基础信息，使用最安全的方式
        title = self._safe_get_attribute(video, "title", "未知标题", ["title_original", "name"])
        duration = self._safe_get_attribute(video, "duration", "未知时长")
        views = self._safe_get_attribute(video, "views", "未知观看次数")
        date = self._safe_get_attribute(video, "date", "未知日期")
        is_hd = self._safe_get_attribute(video, "is_HD", False)
        is_vr = self._safe_get_attribute(video, "is_VR", False)
        
        # 安全获取作者信息
        author_name = "未知"
        try:
            author = getattr(video, "author", None)
            if author:
                author_name = self._safe_get_attribute(author, "name", "未知作者")
            else:
                # 尝试从视频对象直接获取作者信息
                author_name = self._safe_get_attribute(video, "author_name", "未知")
        except Exception as e:
            logger.warning(f"获取作者信息失败: {e}")
            author_name = "未知"

        video_url = self._safe_get_attribute(video, "url", "未知链接")

        info_text = (
            f"标题: {title}\n"
            f"时长: {duration}\n"
            f"观看次数: {views}\n"
            f"发布日期: {date}\n"
            f"是否高清: {'是' if is_hd else '否'}\n"
            f"是否VR: {'是' if is_vr else '否'}\n"
            f"作者: {author_name}\n"
            f"链接: {video_url}"
        )
        yield event.plain_result(info_text)

        # 如果图片下载失败，在这里提示用户
        if not image_sent:
            yield event.plain_result("（图片下载失败，仅显示视频信息")


    @filter.command("ph_user", alias={"phu", "用户信息"})
    async def get_pornhub_user_info(self, event: AstrMessageEvent, username: str):
        """获取PornHub用户信息"""
        yield event.plain_result(f"正在获取用户 {username} 的信息，请稍候...")

        # 确保HTTP客户端已初始化
        if not self.http_client:
            await self.initialize_async()

        if not self.phub_client:
            yield event.plain_result("PHub客户端未初始化")
            return

        # 获取用户对象
        user = await self._get_user_object(username)
        if not user:
            yield event.plain_result(
                f"未找到用户 '{username}'，请检查用户名是否正确"
            )
            return

        # 下载头像
        try:
            avatar_path = await self.download_phub_image(user.avatar)
            if avatar_path:
                # 打码处理
                censored_avatar_path = await self.censor_image(avatar_path)
                if censored_avatar_path:  # 只有打码成功才发送
                    # 发送头像
                    yield event.image_result(censored_avatar_path)
        except Exception as e:
            logger.error(f"下载用户头像失败: {e}")
            # 头像下载失败不影响用户信息显示

        # 发送用户信息
        name = self._safe_get_attribute(user, "name", "未知用户")
        user_type = self._safe_get_attribute(user, "type", "未知类型")
        bio = self._safe_get_attribute(user, "bio", None)
        bio_text = bio or "无"
        user_url = self._safe_get_attribute(user, "url", "未知链接")

        info_text = (
            f"用户名: {name}\n"
            f"用户类型: {user_type}\n"
            f"生物信息: {bio_text}\n"
            f"用户链接: {user_url}"
        )
        yield event.plain_result(info_text)

    async def _get_user_object(self, username: str):
        """获取用户对象，支持直接获取和搜索两种方式"""
        try:
            # 首先尝试直接获取用户（适用于某些情况）
            user = self.phub_client.get_user(username)
            # 禁用查询模拟以避免Regex错误
            if hasattr(user, "ALLOW_QUERY_SIMULATION"):
                user.ALLOW_QUERY_SIMULATION = False
            return user
        except Exception as e:
            logger.warning(f"直接获取用户失败，尝试搜索: {e}")

        # 如果直接获取失败，尝试搜索用户
        try:
            user_query = self.phub_client.search_user(username=username)
            for found_user in user_query:
                # 禁用查询模拟以避免Regex错误
                if hasattr(found_user, "ALLOW_QUERY_SIMULATION"):
                    found_user.ALLOW_QUERY_SIMULATION = False

                # 检查用户名是否匹配
                try:
                    found_name = self._safe_get_attribute(found_user, "name", "")
                    if found_name.lower() == username.lower():
                        return found_user
                except Exception:
                    continue

            # 如果没有找到完全匹配的用户，使用第一个结果
            for found_user in user_query:
                try:
                    # 禁用查询模拟以避免Regex错误
                    if hasattr(found_user, "ALLOW_QUERY_SIMULATION"):
                        found_user.ALLOW_QUERY_SIMULATION = False
                    return found_user
                except Exception:
                    continue
        except Exception as search_e:
            logger.error(f"搜索用户失败: {search_e}")

        return None


    @filter.command("ph_playlist", alias={"php", "播放列表"})
    async def get_pornhub_playlist(self, event: AstrMessageEvent, playlist_id: str):
        """获取PornHub播放列表"""
        try:
            yield event.plain_result(
                f"正在获取播放列表 {playlist_id} 的信息，请稍候..."
            )

            if not self.phub_client:
                yield event.plain_result("PHub客户端未初始化")
                return

            # 获取播放列表对象
            try:
                playlist = self.phub_client.get_playlist(playlist_id)
            except (URLError, NoResult) as e:
                logger.error(f"播放列表无效: {e}")
                yield event.plain_result("播放列表ID无效，请检查是否正确")
                return
            except (ParsingError, MaxRetriesExceeded) as e:
                logger.error(f"获取播放列表失败: {e}")
                yield event.plain_result("获取播放列表失败，请稍后再试")
                return
            except Exception as e:
                logger.error(f"获取播放列表异常: {e}")
                yield event.plain_result("获取播放列表异常，请稍后再试")
                return

            # 获取播放列表中的第一个视频作为示例
            try:
                if (videos := list(playlist.sample(max=1))):
                    video = videos[0]
                    # 下载图片
                    image_path = await self.download_phub_image(video.image)
                    if image_path:
                        # 打码处理
                        censored_image_path = await self.censor_image(image_path)
                        if censored_image_path:  # 只有打码成功才发送
                            # 发送图片
                            yield event.image_result(censored_image_path)
            except Exception as e:
                logger.error(f"获取播放列表视频失败: {e}")
                # 视频获取失败不影响播放列表信息显示

            # 发送播放列表信息
            try:
                # 使用正确的属性名
                title = getattr(playlist, "title", "未知播放列表")
                views = getattr(playlist, "views", "未知")
                video_count = len(playlist) if hasattr(playlist, "__len__") else "未知"

                info_text = (
                    f"播放列表名称: {title}\n"
                    f"视频数量: {video_count}\n"
                    f"查看次数: {views}\n"
                    f"播放列表链接: {playlist.url}"
                )
                yield event.plain_result(info_text)
            except Exception as e:
                logger.error(f"获取播放列表信息失败: {e}")
                yield event.plain_result("获取播放列表信息失败")

        except Exception as e:
            logger.error(f"获取PornHub播放列表失败: {e}")
            yield event.plain_result(f"获取播放列表失败: {str(e)}")

    @filter.command("ph_hot", alias={"ph热门", "热门视频"})
    async def get_hot_videos(self, event: AstrMessageEvent):
        """获取PornHub热门视频"""
        try:
            yield event.plain_result("正在获取PornHub热门视频，请稍候...")

            # 确保HTTP客户端已初始化
            if not self.http_client:
                await self.initialize_async()

            if not self.phub_client:
                yield event.plain_result("PHub客户端未初始化")
                return

            # 获取热门视频
            try:
                # 使用不同的排序方式获取热门视频
                # HubTraffic API 支持的排序方式
                hubtraffic_sorts = ["recent", "views", "rated", "featured"]
                # 普通搜索支持的排序方式
                search_sorts = ["recent", "views", "rated", "longuest"]

                # 首先尝试使用HubTraffic API
                try:
                    selected_sort = random.choice(hubtraffic_sorts)
                    query = self.phub_client.search_hubtraffic(
                        "popular", sort=selected_sort
                    )
                    videos = list(query.sample(max=10))  # 获取10个热门视频
                except Exception as e:
                    logger.warning(f"HubTraffic API失败，尝试普通搜索: {e}")
                    # 如果HubTraffic失败，尝试普通搜索
                    selected_sort = random.choice(search_sorts)
                    search_terms = ["popular", "recommended", "trending", "featured"]
                    selected_term = random.choice(search_terms)
                    query = self.phub_client.search(selected_term, sort=selected_sort)
                    videos = list(query.sample(max=10))  # 获取10个热门视频
            except (ParsingError, MaxRetriesExceeded) as e:
                logger.error(f"获取热门视频失败: {e}")
                yield event.plain_result("获取热门视频失败，请稍后再试")
                return
            except Exception as e:
                logger.error(f"获取热门视频异常: {e}")
                yield event.plain_result("获取热门视频异常，请稍后再试")
                return

            if not videos:
                yield event.plain_result("未找到热门视频，请稍后再试")
                return

            # 随机选择一个热门视频
            selected_video = random.choice(videos)

            # 下载图片
            image_path = await self.download_phub_image(selected_video.image)
            if not image_path:
                yield event.plain_result("下载图片失败，请稍后再试")
                return

            # 打码处理
            censored_image_path = await self.censor_image(image_path)
            if not censored_image_path:
                yield event.plain_result("图片处理失败，为确保安全不发送图片")
                return

            # 发送图片
            yield event.image_result(censored_image_path)

            # 发送视频信息
            try:
                sort_text = {
                    "featured": "精选",
                    "mostviewed": "最多观看",
                    "rating": "最高评分",
                }.get(selected_sort, selected_sort)

                info_text = f"【{sort_text}热门视频】\n标题: {selected_video.title}\n时长: {selected_video.duration}\n观看次数: {selected_video.views}\n链接: {selected_video.url}"
                yield event.plain_result(info_text)
            except Exception as e:
                logger.error(f"获取视频信息失败: {e}")
                yield event.plain_result("获取视频信息失败")

        except Exception as e:
            logger.error(f"获取PornHub热门视频失败: {e}")
            yield event.plain_result(f"处理失败: {str(e)}")

    @filter.command("ph_category", alias={"ph分类", "视频分类"})
    async def get_category_videos(self, event: AstrMessageEvent, category: str = ""):
        """按分类获取PornHub视频"""
        try:
            if not category:
                # 如果没有提供分类，显示可用分类
                categories_text = """
常用分类:
- amateur (业余)
- anal (肛交)
- asian (亚洲)
- babe (宝贝)
- bdsm (BDSM)
- big-ass (大屁股)
- big-tits (大胸)
- blonde (金发)
- blowjob (口交)
- brunette (棕发)
- creampie (内射)
- cumshot (颜射)
- fetish (恋物)
- gangbang (群交)
- hardcore (硬核)
- interracial (跨种族)
- latina (拉丁)
- lesbian (女同)
- masturbation (自慰)
- mature (成熟)
- milf (熟女)
- pornstar (明星)
- public (公共场所)
- redhead (红发)
- teen (青少年)
- threesome (三人行)

使用方法: /ph_category <分类名>
例如: /ph_category asian
                """
                yield event.plain_result(categories_text)
                return

            yield event.plain_result(f"正在获取分类 '{category}' 的视频，请稍候...")

            if not self.phub_client:
                yield event.plain_result("PHub客户端未初始化")
                return

            # 按分类搜索视频
            try:
                # 首先尝试使用HubTraffic API
                try:
                    query = self.phub_client.search_hubtraffic(category, sort="recent")
                    videos = list(query.sample(max=10))
                except Exception as e:
                    logger.warning(f"HubTraffic API分类搜索失败，尝试普通搜索: {e}")
                    # 如果HubTraffic失败，尝试普通搜索
                    query = self.phub_client.search(category, sort="recent")
                    videos = list(query.sample(max=10))
            except (InvalidCategory, NoResult) as e:
                logger.error(f"分类无效或无结果: {e}")
                yield event.plain_result(f"分类 '{category}' 无效或没有找到相关视频")
                return
            except (ParsingError, MaxRetriesExceeded) as e:
                logger.error(f"获取分类视频失败: {e}")
                yield event.plain_result("获取分类视频失败，请稍后再试")
                return
            except Exception as e:
                logger.error(f"获取分类视频异常: {e}")
                yield event.plain_result("获取分类视频异常，请稍后再试")
                return

            if not videos:
                yield event.plain_result(f"分类 '{category}' 中未找到视频，请稍后再试")
                return

            # 随机选择一个视频
            selected_video = random.choice(videos)

            # 下载图片
            image_path = await self.download_phub_image(selected_video.image)
            if not image_path:
                yield event.plain_result("下载图片失败，请稍后再试")
                return

            # 打码处理
            censored_image_path = await self.censor_image(image_path)
            if not censored_image_path:
                yield event.plain_result("图片处理失败，为确保安全不发送图片")
                return

            # 发送图片
            yield event.image_result(censored_image_path)

            # 发送视频信息
            try:
                info_text = f"【分类: {category}】\n标题: {selected_video.title}\n时长: {selected_video.duration}\n观看次数: {selected_video.views}\n链接: {selected_video.url}"
                yield event.plain_result(info_text)
            except Exception as e:
                logger.error(f"获取视频信息失败: {e}")
                yield event.plain_result("获取视频信息失败")

        except Exception as e:
            logger.error(f"获取分类视频失败: {e}")
            yield event.plain_result(f"处理失败: {str(e)}")

    @filter.command("ph_random", alias={"ph随机", "随机视频"})
    async def get_random_videos(self, event: AstrMessageEvent, count: int = 1):
        """获取多个随机视频"""
        try:
            # 验证数量参数
            if count < 1 or count > 5:
                yield event.plain_result("数量参数必须在1-5之间")
                return

            yield event.plain_result(f"正在获取 {count} 个随机PornHub视频，请稍候...")

            if not self.phub_client:
                yield event.plain_result("PHub客户端未初始化")
                return

            # 获取多个随机视频
            try:
                # 首先尝试使用HubTraffic API
                try:
                    query = self.phub_client.search_hubtraffic("popular", sort="recent")
                    videos = list(
                        query.sample(max=count * 3)
                    )  # 获取更多视频以确保有足够的随机选择
                except Exception as e:
                    logger.warning(f"HubTraffic API失败，尝试普通搜索: {e}")
                    # 如果HubTraffic失败，尝试普通搜索
                    search_terms = ["popular", "recommended", "trending", "featured"]
                    selected_term = random.choice(search_terms)
                    query = self.phub_client.search(selected_term, sort="recent")
                    videos = list(
                        query.sample(max=count * 3)
                    )  # 获取更多视频以确保有足够的随机选择
            except (ParsingError, MaxRetriesExceeded) as e:
                logger.error(f"获取视频列表失败: {e}")
                yield event.plain_result("获取视频列表失败，请稍后再试")
                return
            except Exception as e:
                logger.error(f"获取视频列表异常: {e}")
                yield event.plain_result("获取视频列表异常，请稍后再试")
                return

            if not videos:
                yield event.plain_result("未找到视频，请稍后再试")
                return

            # 随机选择指定数量的视频
            selected_videos = random.sample(videos, min(count, len(videos)))

            # 处理每个视频
            for i, video in enumerate(selected_videos, 1):
                try:
                    # 下载图片
                    image_path = await self.download_phub_image(video.image)
                    if not image_path:
                        yield event.plain_result(f"第 {i} 个视频下载图片失败，跳过")
                        continue

                    # 打码处理
                    censored_image_path = await self.censor_image(image_path)
                    if not censored_image_path:
                        yield event.plain_result(f"第 {i} 个视频图片处理失败，跳过")
                        continue

                    # 发送图片
                    yield event.image_result(censored_image_path)

                    # 发送视频信息
                    try:
                        info_text = f"【随机视频 {i}/{len(selected_videos)}】\n标题: {video.title}\n时长: {video.duration}\n观看次数: {video.views}\n链接: {video.url}"
                        yield event.plain_result(info_text)
                    except Exception as e:
                        logger.error(f"获取第 {i} 个视频信息失败: {e}")
                        yield event.plain_result(f"获取第 {i} 个视频信息失败")

                except Exception as e:
                    logger.error(f"处理第 {i} 个视频失败: {e}")
                    yield event.plain_result(f"处理第 {i} 个视频失败，跳过")

        except Exception as e:
            logger.error(f"获取随机视频失败: {e}")
            yield event.plain_result(f"处理失败: {str(e)}")

    @filter.command("ph_stats", alias={"ph统计", "视频统计"})
    async def get_video_stats(self, event: AstrMessageEvent):
        """获取PornHub视频统计信息"""
        try:
            yield event.plain_result("正在获取PornHub视频统计信息，请稍候...")

            if not self.phub_client:
                yield event.plain_result("PHub客户端未初始化")
                return

            # 获取最新视频
            recent_videos = await self._get_videos_with_fallback("recent", 20)
            if not recent_videos:
                yield event.plain_result("未找到视频，无法生成统计信息")
                return

            # 计算统计信息
            stats = self._calculate_video_stats(recent_videos)
            
            # 获取精选视频数量
            featured_count = await self._get_video_count_with_fallback("featured", "views", 10)
            
            # 获取高评分视频数量
            rating_count = await self._get_video_count_with_fallback("rating", "rated", 10)

            # 发送统计信息
            stats_text = (
                f"📊 PornHub视频统计信息\n"
                f"📹 最新视频数量: {stats['total_videos']}\n"
                f"👀 平均观看次数: {stats['avg_views']:,.0f}\n"
                f"⏱️ 平均时长: {stats['avg_duration_minutes']:.1f} 分钟\n"
                f"⭐ 精选视频数量: {featured_count}\n"
                f"🏆 高评分视频数量: {rating_count}\n"
                f"📅 统计时间: {asyncio.get_event_loop().time()}"
            )
            yield event.plain_result(stats_text)

        except Exception as e:
            logger.error(f"获取视频统计失败: {e}")
            yield event.plain_result(f"获取统计信息失败: {str(e)}")

    async def _get_videos_with_fallback(self, sort_type: str, max_results: int):
        """获取视频，优先使用HubTraffic API，失败时回退到普通搜索"""
        try:
            # 首先尝试使用HubTraffic API
            try:
                search_terms = ["popular", "recommended", "trending", "featured"]
                selected_term = random.choice(search_terms)
                query = self.phub_client.search_hubtraffic(selected_term, sort=sort_type)
                return list(query.sample(max=max_results))
            except Exception as e:
                logger.warning(f"HubTraffic API搜索失败，尝试普通搜索: {e}")
                # 如果HubTraffic失败，尝试普通搜索
                search_terms = ["popular", "recommended", "trending", "featured"]
                selected_term = random.choice(search_terms)
                query = self.phub_client.search(selected_term, sort=sort_type)
                return list(query.sample(max=max_results))
        except Exception as e:
            logger.error(f"获取视频失败: {e}")
            return []

    async def _get_video_count_with_fallback(self, hubtraffic_sort: str, fallback_sort: str, max_results: int):
        """获取视频数量，优先使用HubTraffic API，失败时回退到普通搜索"""
        try:
            # 首先尝试使用HubTraffic API
            try:
                search_terms = ["popular", "recommended", "trending", "featured"]
                selected_term = random.choice(search_terms)
                query = self.phub_client.search_hubtraffic(selected_term, sort=hubtraffic_sort)
                videos = list(query.sample(max=max_results))
                return len(videos)
            except Exception as e:
                logger.warning(f"HubTraffic API搜索失败，尝试普通搜索: {e}")
                # 如果HubTraffic失败，尝试普通搜索
                search_terms = ["popular", "recommended", "trending", "featured"]
                selected_term = random.choice(search_terms)
                query = self.phub_client.search(selected_term, sort=fallback_sort)
                videos = list(query.sample(max=max_results))
                return len(videos)
        except Exception as e:
            logger.error(f"获取视频数量失败: {e}")
            return 0

    def _safe_get_attribute(self, obj, attr_name, default_value=None, fallback_attrs=None):
        """安全获取对象属性，支持多个备选属性名"""
        try:
            # 首先尝试获取主要属性
            value = getattr(obj, attr_name, default_value)
            if value != default_value:
                return value
            
            # 如果主要属性不存在或为默认值，尝试备选属性
            if fallback_attrs:
                for fallback_attr in fallback_attrs:
                    value = getattr(obj, fallback_attr, default_value)
                    if value != default_value:
                        return value
            
            return default_value
        except Exception as e:
            logger.warning(f"获取属性 {attr_name} 失败: {e}")
            return default_value

    def _calculate_video_stats(self, videos):
        """计算视频统计信息"""
        total_videos = len(videos)
        total_views = sum(
            video.views
            for video in videos
            if hasattr(video, "views") and video.views
        )
        avg_views = total_videos > 0 and total_views / total_videos or 0

        # 计算平均时长
        durations = []
        for video in videos:
            if hasattr(video, "duration") and video.duration:
                try:
                    # 尝试解析时长字符串
                    duration_str = str(video.duration)
                    if ":" in duration_str:
                        parts = duration_str.split(":")
                        if len(parts) == 2:  # 格式: mm:ss
                            minutes = int(parts[0])
                            seconds = int(parts[1])
                            durations.append(minutes * 60 + seconds)
                        elif len(parts) == 3:  # 格式: hh:mm:ss
                            hours = int(parts[0])
                            minutes = int(parts[1])
                            seconds = int(parts[2])
                            durations.append(hours * 3600 + minutes * 60 + seconds)
                except (ValueError, TypeError):
                    continue

        avg_duration_seconds = durations and sum(durations) / len(durations) or 0
        avg_duration_minutes = avg_duration_seconds / 60

        return {
            'total_videos': total_videos,
            'avg_views': avg_views,
            'avg_duration_minutes': avg_duration_minutes
        }

    @filter.command("ph_help", alias={"ph帮助", "pornhub帮助"})
    async def show_help(self, event: AstrMessageEvent):
        """显示PornHub插件帮助信息"""
        try:
            help_text = """
🔞 PornHub插件帮助信息

📋 基础指令:
• /ph 或 /pornhub 或 /视频封面 - 获取随机视频封面
• /ph_search <关键词> 或 /phs <关键词> - 搜索视频
• /ph_video <viewkey> 或 /phv <viewkey> - 获取视频详情
• /ph_user <用户名> 或 /phu <用户名> - 获取用户信息
• /ph_playlist <播放列表ID> 或 /php <播放列表ID> - 获取播放列表

🔥 新增功能:
• /ph_hot 或 /ph热门 或 /热门视频 - 获取热门视频
• /ph_category [分类] 或 /ph分类 [分类] - 按分类获取视频
• /ph_random [数量] 或 /ph随机 [数量] - 获取多个随机视频(1-5个)
• /ph_stats 或 /ph统计 或 /视频统计 - 获取视频统计信息

📚 分类示例:
amateur, anal, asian, babe, bdsm, big-ass, big-tits, blonde, blowjob, brunette, creampie, cumshot, fetish, gangbang, hardcore, interracial, latina, lesbian, masturbation, mature, milf, pornstar, public, redhead, teen, threesome

⚙️ 配置选项:
• proxy: HTTP代理地址
• timeout: 请求超时时间(秒)
• phub_language: PHub客户端语言
• phub_delay: 请求延迟(秒)
• phub_login_email: PHub登录邮箱
• phub_login_password: PHub登录密码
• return_details: 是否返回视频详情
• max_search_results: 最大搜索结果数
• search_default_sort: 默认搜索排序
• search_default_period: 默认搜索时间范围

🔒 安全说明:
所有图片都会在本地进行打码处理，确保内容安全。打码失败时不会发送任何图片。

💡 使用提示:
1. 使用 /ph_category 不带参数可查看所有可用分类
2. 使用 /ph_random 不带参数默认获取1个视频
3. 视频详情中的viewkey可以从视频URL中获取
4. 播放列表ID可以从播放列表URL中获取
            """
            yield event.plain_result(help_text)

        except Exception as e:
            logger.error(f"显示帮助信息失败: {e}")
            yield event.plain_result(f"显示帮助信息失败: {str(e)}")

    async def download_phub_image(self, image) -> Optional[str]:
        """下载PHub图片到临时目录"""
        try:
            # 检查image对象是否为None
            if image is None:
                logger.error("图片对象为None")
                return None

            # 检查image对象是否有url属性
            if not hasattr(image, "url"):
                logger.error("图片对象没有url属性")
                return None

            # 获取图片URL
            image_url = getattr(image, "url", None) if image else None
            if not image_url:
                logger.error("图片URL为空")
                return None

            # 生成临时文件路径
            file_extension = os.path.splitext(urlparse(image_url).path)[1] or ".jpg"  # 默认扩展名

            temp_file_path = os.path.join(
                self.temp_dir,
                f"phub_image_{random.randint(1000, 9999)}{file_extension}",
            )

            # 下载图片
            async with self.http_client.get(image_url) as response:
                if response.status != 200:
                    logger.error(f"下载图片失败，状态码: {response.status}")
                    return None

                content = await response.read()
                with open(temp_file_path, "wb") as f:
                    f.write(content)

            logger.info(f"图片下载成功: {temp_file_path}")
            return temp_file_path

        except Exception as e:
            logger.error(f"下载图片失败: {e}")
            return None

    async def censor_image(self, image_path: str) -> str:
        """对图片进行打码处理"""
        try:
            if not image_path or not os.path.exists(image_path):
                logger.error("图片文件不存在")
                return ""

            # 打开图片
            with Image.open(image_path) as img:
                # 转换为RGB模式（如果是RGBA或其他模式）
                if img.mode != "RGB":
                    img = img.convert("RGB")

                # 获取图片尺寸
                width, height = img.size

                # 计算马赛克块大小（基于图片尺寸的百分比）
                if self.config is not None:
                    mosaic_level = self.config.get("mosaic_level", 0.8)  # 默认马赛克程度
                    if mosaic_level <= 0 or mosaic_level > 1:
                        mosaic_level = 0.8
                else:
                    mosaic_level = 0.8  # 默认值

                # 根据马赛克程度计算块大小
                # 马赛克程度越高，块大小越大
                block_size = int(
                    min(width, height) * mosaic_level * 0.05
                )  # 5% * 马赛克程度
                block_size = max(block_size, 5)  # 最小块大小为5像素

                # 创建马赛克效果
                for y in range(0, height, block_size):
                    for x in range(0, width, block_size):
                        # 获取当前块的平均颜色
                        block = img.crop((x, y, x + block_size, y + block_size))
                        if block.size[0] > 0 and block.size[1] > 0:
                            # 计算平均颜色
                            avg_color = tuple(
                                int(sum(c) / len(c)) for c in zip(*block.getdata())
                            )

                            # 创建纯色块
                            solid_block = Image.new(
                                "RGB", (block_size, block_size), avg_color
                            )
                            img.paste(solid_block, (x, y))

                # 保存打码后的图片
                censored_path = os.path.join(
                    self.temp_dir, f"censored_{os.path.basename(image_path)}"
                )
                img.save(censored_path, "JPEG", quality=85)

            # 删除原始图片
            try:
                os.remove(image_path)
            except Exception as e:
                logger.warning(f"删除原始图片失败: {e}")

            logger.info(f"图片打码完成: {censored_path}")
            return censored_path

        except Exception as e:
            logger.error(f"图片打码失败: {e}")
            # 如果打码失败，尝试删除原始图片
            try:
                if os.path.exists(image_path):
                    os.remove(image_path)
            except Exception as e:
                logger.warning(f"删除原始图片失败: {e}")
            return ""  # 返回空字符串表示打码失败
