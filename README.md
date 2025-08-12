# Arcaea Server Bot
这是某3D音游服务器可用的QQ机器人开源项目。
写的不太好但是能用且实现了大部分功能喵~
使用的是基于napcat且易于上手的[NCatBot](https://github.com/liyihao1110/ncatbot)框架

NapCat文件夹请自行[前往下载](https://github.com/NapNeko/NapCatQQ)shell版并解压

部分插件需要以下路径处于同一父目录下：
- ArkanaBot文件夹——本项目的文件夹
- ArkanaServer文件夹——[Arcaea-server项目](https://github.com/Lost-MSth/Arcaea-server)
- ArkanaBundler文件夹——[Arcaea-Bundler项目](https://github.com/Lost-MSth/Arcaea-Bundler)

此外，示例数据库文件夹下的user.db数据库实际上存放在ArkanaServer(Arcaea-server)的web文件夹下
具体配置可以研究一下代码，应该还是很好上手的。

请严格按照上面的文件夹安排路径，否则需要修改文件夹信息。

大致指令如下：
```
⭐/aichan在所有游玩过的歌曲中随机选一首歌并推荐给你！
⭐/aa add [歌曲ID/别名]添加歌曲别名~
⭐/aa del [歌曲ID/别名]删除歌曲别名~
⭐/aa info [歌曲ID/别名]查看歌曲别名及ID~
⭐/b30获取最新的b30成绩图，请勿频繁查询！
⭐/chart [歌曲ID/别名] [难度(0-4)]获取谱面2d图，若生成过直接发送，当谱面改动时请联系管理删除图片，请勿频繁查询！
⭐/tmpkey生成临时密钥，请在五分钟内使用！
⭐/validator refresh(仅管理可用，不可私发)刷新封号名单并验游戏数据库！
⭐/help查询机器人使用帮助！
⭐/userdb refresh(仅管理可用，不可私发)刷新用户数据库，止非本群玩家注册账号！
⭐/img [数量(默认1)]随机获取图片，如需要添加随机图片的@Swiro！
⭐/rating [定数]查询定数表，小数点只有一位哦~
⭐/recent获取最近的游戏成绩图，请勿频繁查询！
⭐/say [目标群群号] [发送文本](仅管理可用)以机器人的身份指定群发送文本！
⭐/snatch触发虚实构想互动，规则如下：
    Nymph有游戏账号且好友码为000000000存有她虚实构想余额！
    约  2% 概率随机翻 2 ~ 5 倍虚实构想，
    约  6% 概率获得 Nymph 的 (25% ~ 50%) x (50% ~ 100%) 的虚实构想，
    约 20% 概率获得 0 ~ 100 枚虚实构想，
    约 32% 概率被夺取 50 ~ MAX(50, 自身25%) 枚虚实构想，
    约 40% 概率被夺取 0 ~ 100 枚虚实构想。
    ※拥有的虚实构想数量必须超过100才会触发！
⭐/transfer [@收款方/QQ号] [数量]转账功能，仅支持虚实想，一经赠与不可撤回！
⭐/vote for [歌曲ID/别名] [数量(默认1)]为歌曲投票，一张奖励10枚虚实构想~
⭐/vote info [歌曲ID/别名]查询歌曲的投票数量
⭐/vote rank [数量(默认10)]获取歌曲投票排名
⭐/rank [类型(默认#值排名)]玩家世界排名(POTENTIAL榜['1', "ptt"]、#VALUE榜：['2', "#"])
⭐@Nymph 签到每日签到，随机获取100~200枚虚实构想~
⭐@Nymph [问题]已接入AI智能体，每日回答次数有限~
⭐{戳一戳@Nymph}随机文本。
```

此外还有事件如下：

- 入群事件：自动记录入群的玩家并重新清点群内玩家

- 退群事件：自动封号退群的玩家并重新清点群内玩家

- 整点事件：自动检测数据库有没有存在非本群的玩家

插件详解：

- Start.py：签到功能+接入百度API智能体

- AiChan插件：输入指令获取你游玩的曲目并随机推荐一首并添加Ai酱的图片到曲绘中并展示文件。参考自本地查分项目[新st解析](https://github.com/SmartRTE/SmartRTE.github.io)

- Alias：歌曲别名插件

- B30：查看b30图片，部分贴图来自本地查分项目[新st解析](https://github.com/SmartRTE/SmartRTE.github.io)

- Chart：生成曲面2d图，保存图片到saves下，如果生成过了直接调用保存的图片，代码来自[ArcaeaChartRender](https://github.com/Arcaea-Infinity/ArcaeaChartRender)

- GetTmpKey：生成临时密钥，算法本质就是异或运算QQ号码，这个配合网页端使用的，然后可以直接获取QQ号码，就不需要绑定玩家账号了，因为已经知道了。思路是来自Arcaea API的。

- GroupMemberValidator：就是保存群内玩家的信息，可以配合前端，检验这个数据库，不让群外玩家注册。

- Help：帮助菜单，实际上是爬取网页端的内容，然后发送帮助菜单图片。

- OnlyInGroup：自动封号非群内玩家。

- PokeMe：戳一戳发送随机文本。

- RandImg：发送随即图片。

- Rating：发送某一定数的所有曲目。

- RecentPlay：发送最近游玩曲目的成绩图，包含定数、画师、谱师信息。

- Say：让机器人在某群发送指定文本。

- Snatch：趣味性玩法，记忆源点赌注类玩法。

- Transfer：转账记忆源点的功能。

- Vote：歌曲投票功能，此外投票奖励10个记忆源点。

- WorldList：发送世界排名信息图，一个#榜一个ppt榜。