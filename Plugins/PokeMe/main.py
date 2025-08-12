import os
import random
import sqlite3
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import BaseMessage
from ncatbot.utils import get_log
from ncatbot.plugin.event import Event

LOG = get_log("PokeMe")
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR))) 
DATABASE_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\database\\arcaea_database.db")
nymph_user_id = 2000018

class PokeMe(BasePlugin):
    name = "PokeMe"
    author = "Swiro"
    description = "戳一戳~"
    version = "1.0.0"

    async def handle_notify_poke(self, data):
        """处理戳一戳事件"""
        user_id = data.get("user_id")
        group_id = data.get("group_id")
        LOG.info(f"收到戳一戳事件的数据：{data}")
        if data.get("self_id") == data.get("target_id"):
            if group_id is None:
                return await self.api.post_private_msg(user_id, random.choice(self.words))
            else:
                return await self.api.post_group_msg(group_id, random.choice(self.words))

    async def handle_notice_event(self, event: Event):
        """统一处理所有通知事件，按子类型分发"""
        notice_data = event.data
        notice_type = notice_data.get("notice_type")
        # notice_type前往napcat查看~https://napneko.github.io/develop/event#notice-%E4%BA%8B%E4%BB%B6
        LOG.info(f"收到通知事件：{notice_type}")
        if notice_type == "notify":
            await self.handle_notify_poke(notice_data)

    async def on_load(self):
        """插件加载时执行"""
        self.words = [
            "给其他部门的资料都整理完了，植物也刚浇过水..…，啊，这是您想要的水，点心也已经麻烦食堂在做了。请您放心，我事先都找其他干员了解过了，不会出差错的。",
            "我家旁边就有个输送能源的小熔炉，埃米说过它的用处，不过我们一般用它来烤食物、烘衣服，还有取暖。听别人说，只要在使用炉子前敲两下，先祖的护佑就会一直在身边。",
            "笞心魔不读心，也不会吸走情感，更不会吃脑子!真是的，您从哪里听来的胡言乱语呀!您要是再说这些，我可要生气了!信不信我现在就扑上来，把您的脑袋咔咔啃下来！",
            "当时在城里找先祖的时候，埃米把这个方块送给我暂时用来装他们。现在嘛，我就用它来装些大件行李。我很想知道它是怎么运作的，但巫妖的技术太复杂了，就算埃米袒露心灵，还是很难搞懂。",
            "这笔钱得好好计划计划，嘻嘻....嗯，您好啊博士。这个?这是合法收入，帮朋友们排忧解难收些报酬也很正常嘛。您问我做了什么?唔，也就帮人找找宠物、整理思绪之类，没什么特别的。",
            "我最近做得怎么样，您还满意吗?信赖和青睐还是有区别的，毕竟笞心魔很容易获得后者，但前者嘛.....唔，我听得出来，谢谢您的信任。",
            "爸爸妈妈离开好一阵了。想他们吗?嗯...还行吧。我是他们的孩子，又不是他们的一部分。我能够自力更生了，没道理把他们强留在身边。只要能感受到他们的爱，就随他们去吧。",
            "笞心魔笞心魔，鞭笞别人心灵的同时，也得记得鞭苔自己的。传说曾经有过度放纵心灵而疯癫的同族，最终被魔王亲手击杀了。当、当然，我从没亲眼见过。总之，只要守好本心，就不会有事的!",
            "鞭苔心灵可不是闹着玩的，您真要试试看吗?好，好吧。我会控制好度的。看着我的眼睛....啊，对不起，我有点紧张，心都提到嗓子眼了。下、下次再试吧，我得准备一下......",
            "真是个好梦，我也有点困了......",
            "让我和您交个心吧，这位讲述者。我们一定能够更加了解对方的。",
            "看着我的眼睛！",
            "回头吧，别让心碎在这里。",
            "将这钥索，挥向心灵！",
            "锁已经解开了。",
            "好干净啊，简单布置一下肯定能变成很舒适的小窝。",
            "别胡闹啦。",
            "您心底里的那把锁没有钥匙？别担心，我会帮您找到它的。",
            "到处都是欢声笑语，沉浸在这样的氛围里心都要化了.....今天就好好狂欢一下吧，讲述者。",
            "让自己的思绪休息一下吧，讲述者。",
            "回头看看，今年怎么做了这么多事?阿尔克那、罗德岛两头跑，快把我腿都跑断了。累?好像也没有，挺满足的，至于明年嘛....还是不想了，有未知才有期待，对不对？",
            "呜呜，你再戳，我就要钻进被窝里不出来了",
            "再戳的话，我就要把你的虚实构想藏起来哦",
            "别戳啦，再戳我就要告诉魔王和Swiro你欺负我",
            "别闹啦～再戳我就把你的脑袋卡卡啃下来！",
            "呜呜，你再戳，我就要把你的虚实构想偷走了。",
            "再戳的话，我就要把你的合成玉和寻访凭证偷走！",
            "阿卡尔那真是一个充满了美好故事的地方呢！好想在这好好地睡一觉呜呜。",
            "再戳的话，我就要把你的虚实构想都吃了！",
            "别戳啦，再戳我就要把你的残片偷走！",
            "阿尔卡那真是一个和蔼的灰色天国呢！",
        ]
        self.register_handler("ncatbot.notice_event", self.handle_notice_event)