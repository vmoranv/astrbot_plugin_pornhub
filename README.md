# AstrBot PornHub 插件

[![文档](https://img.shields.io/badge/AstrBot-%E6%96%87%E6%A1%A3-blue)](https://astrbot.app)
[![phub](https://img.shields.io/pypi/v/phub.svg)](https://pypi.org/project/phub/)
[![GitHub](https://img.shields.io/badge/GitHub-仓库-green)](https://github.com/vmoranv/astrbot_plugin_pornhub)

这是一个为 [AstrBot](https://astrbot.app) 开发的 PornHub 插件，让你可以在聊天中轻松搜索和获取 PornHub 视频信息和封面图片。

## ✨ 核心特性

- 🎬 **多种搜索方式**: 支持随机视频、关键词搜索、视频详情查询
- 👤 **用户功能**: 获取用户信息和头像
- 📚 **播放列表**: 支持播放列表信息获取
- 🛡️ **内容控制**: 可配置的马赛克打码程度
- ⚙️ **高度可配置**: 代理设置、语言设置、登录功能等
- 🔐 **安全管理**: 通过 WebUI 安全管理配置信息
- 🌍 **多语言支持**: 支持多种语言界面

## 🎯 主要功能

### 视频搜索
- `/ph` - 获取随机视频封面
- `/ph_search <关键词>` - 关键词搜索视频
- `/ph_video <viewkey>` - 获取指定视频详情

### 用户功能
- `/ph_user <用户名>` - 获取用户信息和头像
- `/ph_user <用户ID>` - 获取用户信息和头像

### 播放列表功能
- `/ph_playlist <播放列表ID>` - 获取播放列表信息

### 热门视频功能
- `/ph_hot` - 获取热门视频（精选、最多观看或最高评分）

### 分类视频功能
- `/ph_category [分类]` - 按分类获取视频，不提供参数时显示可用分类列表

### 多随机视频功能
- `/ph_random [数量]` - 一次获取1-5个随机视频

### 视频统计功能
- `/ph_stats` - 获取PornHub视频统计信息

### 帮助功能
- `/ph_help` - 显示插件帮助信息

## 📝 使用示例

```bash
# 基础功能
/ph
/ph_search rooster
/ph_video 123456

# 用户功能
/ph_user username
/ph_user 123456

# 播放列表功能
/ph_playlist 123456

# 热门视频功能
/ph_hot

# 分类视频功能
/ph_category asian
/ph_category  # 显示所有可用分类

# 多随机视频功能
/ph_random 3  # 获取3个随机视频

# 视频统计功能
/ph_stats

# 获取帮助
/ph_help
```

## ⚙️ 配置选项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `mosaic_level` | 封面图打码程度 (0.0-1.0) | 0.8 |
| `proxy` | 网络代理地址，如 `http://127.0.0.1:7890` | 留空 |
| `timeout` | 网络请求超时时间（秒） | 30 |
| `user_agent` | 用户代理字符串 | Mozilla/5.0... |
| `max_retries` | 最大重试次数 | 3 |
| `return_details` | 是否返回视频详细信息 | true |
| `phub_language` | PHub API语言设置 | cn |
| `phub_delay` | PHub API请求延迟（秒） | 0.0 |
| `phub_login_email` | PHub登录邮箱 | 留空 |
| `phub_login_password` | PHub登录密码 | 留空 |
| `search_default_sort` | 默认搜索排序方式 | recent |
| `search_default_period` | 默认搜索时间范围 | all |
| `max_search_results` | 最大搜索结果数量 | 10 |

### 语言选项
- `en` - English
- `cn` - 中文
- `de` - Deutsch
- `fr` - Français
- `it` - Italiano
- `pt` - Português
- `pl` - Polski
- `rt` - Русский
- `nl` - Nederlands
- `cz` - Čeština
- `jp` - 日本語

### 搜索排序选项
- `recent` - 最新
- `views` - 最多观看
- `rated` - 最高评分
- `longuest` - 最长时长

### 搜索时间范围
- `all` - 全部时间
- `day` - 今日
- `week` - 本周
- `month` - 本月
- `year` - 今年

## 🛠️ 技术实现

### 核心技术栈
- **PHub库**: 使用官方PHub库进行API调用
- **异步处理**: 基于aiohttp的异步网络请求
- **图片处理**: 使用Pillow库进行马赛克打码
- **错误处理**: 完善的异常处理机制

### 打码算法
采用全图马赛克打码，马赛克程度通过配置文件设置（默认0.8），通过缩小图片然后放大的方式实现全图打码效果，确保图片内容完全不可见。

## 🔧 错误处理

插件内置了完善的错误处理机制，能够处理以下常见错误：

- **登录错误**: 账户信息错误或已登录
- **网络错误**: 连接超时、代理失败等
- **解析错误**: 页面解析失败
- **内容错误**: 视频/用户/播放列表不存在
- **地区限制**: 视频在您所在的地区被限制
- **Premium内容**: 需要订阅才能访问的内容

当遇到错误时，插件会提供友好的错误提示信息，帮助用户了解问题所在。

## 📖 更多信息

- [AstrBot 官方文档](https://astrbot.app/)
- [插件开发指南](https://astrbot.app/develop/plugin.html)
- [PHub库文档](https://pypi.org/project/phub/)

## ⚠️ 免责声明

**重要声明**: 本插件仅供技术研究和学习目的使用。使用者必须遵守以下条款：

### 法律合规
1. 使用者必须年满18岁或达到当地法定成年年龄
2. 请确保使用本插件符合您所在国家/地区的法律法规
3. 插件开发者不对使用者的任何违法行为承担责任

### 使用限制
1. 本插件不得用于商业用途
2. 禁止将插件用于任何非法活动
3. 请合理使用API功能，避免频繁请求
4. 不得绕过或破解网站的访问限制

### 内容声明
1. 插件仅提供信息检索功能，不存储、传播任何内容
2. 所有内容均来源于原始网站，插件不对内容的合法性负责
3. 马赛克打码功能旨在符合内容分享规范，但不保证完全合规

### 隐私保护
1. 插件不会收集用户的个人信息
2. 登录信息仅用于API访问，不会被存储或分享
3. 使用代理功能时，请确保代理服务的合法性和安全性

### 风险提示
1. 使用本插件可能存在网络风险，请自行承担相应风险
2. 插件开发者不保证服务的持续性和稳定性
3. 使用过程中如遇到任何问题，请立即停止使用并联系开发者

### 免责条款
使用本插件即表示您同意：
- 自行承担使用风险和后果
- 遵守所有适用的法律法规
- 不将插件用于任何违法或不当用途
- 如因使用本插件造成任何损失，开发者概不负责
