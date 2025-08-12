import os
import random
import sqlite3
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import BaseMessage
from ncatbot.utils import get_log

LOG = get_log("Snatch")
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR))) 
DATABASE_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\database\\arcaea_database.db")
nymph_user_id = 2000018 # 给机器人创建游戏账号的游戏存档ID

class Snatch(BasePlugin):
    name = "Snatch"
    author = "Swiro"
    description = "通过/snatch指令进行虚实构想抽奖"
    version = "1.0.0"
    dependencies = {}

    async def snatch(self, msg: BaseMessage):
        """处理/snatch指令，执行抽奖逻辑"""
        user_id = msg.sender.user_id
        group_id = msg.group_id if hasattr(msg, 'group_id') else None
        # 检查是否为私聊
        #if group_id is None:
            #return await msg.reply("此指令仅支持在群聊中使用哦~")
        
        # 验证用户是否为讲述者
        with sqlite3.connect(DATABASE_PATH, timeout=30) as conn:
            conn.row_factory = sqlite3.Row
            c = conn.cursor()
            c.execute("SELECT * FROM user WHERE email=?", (f"{user_id}@qq.com",))
            whose_info = c.fetchone()
            if not whose_info:
                return await msg.reply("你不是讲述者，无法使用此指令哦！")
            elif whose_info['ticket'] <= 100:
                return await msg.reply("诶诶，你才这点虚实构想，想...想干嘛？我才不让你抢走我的东西呢！")
        
        # 执行抽奖逻辑
        TYPE = [2, 6, 32, 20, 40]
        SNATCH_POOL = [j for i in range(len(TYPE)) for j in [TYPE[i]] * TYPE[i]]
        grab_ticket = random.choice(SNATCH_POOL)
        
        # 2%概率：用户虚实构想翻倍
        if grab_ticket == 2:
            n = random.randint(2, 5)
            with sqlite3.connect(DATABASE_PATH, timeout=30) as conn:
                c = conn.cursor()
                # 获取当前用户的虚实构想数量
                c.execute("SELECT ticket FROM user WHERE email=?", (f"{user_id}@qq.com",))
                current_ticket = c.fetchone()[0]
                # 更新为翻倍后的值
                new_ticket = current_ticket * n
                c.execute("UPDATE user SET ticket=? WHERE email=?", (new_ticket, f"{user_id}@qq.com",))
                conn.commit()
            return await msg.reply(f"等等，我会施展魔力，把你所有的虚实构想翻{n}倍，可以放过我吗...")
        
        # 6%概率：从nymph处获得虚实构想
        elif grab_ticket == 6:
            with sqlite3.connect(DATABASE_PATH, timeout=30) as conn:
                c = conn.cursor()
                c.execute("SELECT ticket FROM user WHERE user_id=?", (nymph_user_id,))
                nymph_ticket = c.fetchone()[0]
            
            if nymph_ticket <= 0:
                return await msg.reply("呜呜呜，放过我吧，我一枚虚实构想都没有...")
            
            rate = random.uniform(0.5, 1.0)
            n = int(random.randint(nymph_ticket // 4, nymph_ticket // 2) * rate)
            with sqlite3.connect(DATABASE_PATH, timeout=30) as conn:
                c = conn.cursor()
                # 更新用户的虚实构想
                c.execute("UPDATE user SET ticket = ticket + ? WHERE email=?", (n, f"{user_id}@qq.com",))
                # 更新nymph的虚实构想
                c.execute("UPDATE user SET ticket = ticket - ? WHERE user_id=?", (n, nymph_user_id,))
                conn.commit()
            
            return await msg.reply(f"呜呜呜，我分你一点{n}枚虚实构想，就放过我吧...")
        
        # 32%概率：被nymph夺走虚实构想（8-40区间）
        elif grab_ticket == 32:
            with sqlite3.connect(DATABASE_PATH, timeout=30) as conn:
                c = conn.cursor()
                c.execute("SELECT ticket FROM user WHERE email=?", (f"{user_id}@qq.com",))
                user_ticket = c.fetchone()
                
                if user_ticket is None or user_ticket[0] <= 0:
                    return await msg.reply("什么？你居然一枚虚实构想都没有！没事，我会给你打欠条的！")
                
                # 计算可夺取的数量
                max_value = user_ticket[0] // 4
                ticket = random.randint(50, max_value) if max_value >= 50 else 50
                
                # 更新数据库
                c.execute("UPDATE user SET ticket = ticket + ? WHERE user_id=?", (ticket, nymph_user_id,))
                c.execute("UPDATE user SET ticket = ticket - ? WHERE email=?", (ticket, f"{user_id}@qq.com",))
                conn.commit()
                
                # 获取更新后的nymph的虚实构想数量
                c.execute("SELECT ticket FROM user WHERE user_id=?", (nymph_user_id,))
                nymph_ticket = c.fetchone()[0]

                # 获取更新后的玩家的虚实构想数量
                c.execute("SELECT ticket FROM user WHERE email=?", (f"{user_id}@qq.com",))
                user_rest_ticket = c.fetchone()[0]
            
            return await msg.reply(f"嘻嘻，你有{ticket}枚虚实构想现在都是我的啦，而你只剩下{user_rest_ticket}枚咯！\n哎呀，看看呐，{nymph_ticket}枚虚实构想，略略略~")
        
        # 60%概率：20 + 40
        elif grab_ticket == 20:
            with sqlite3.connect(DATABASE_PATH, timeout=30) as conn:
                c = conn.cursor()
                c.execute("SELECT ticket FROM user WHERE user_id=?", (nymph_user_id,))
                nymph_ticket = c.fetchone()[0]
            
            if nymph_ticket <= 0:
                return await msg.reply("呜呜呜，放过我吧，我一枚虚实构想都没有...")

            n = random.randint(0, 100)
            with sqlite3.connect(DATABASE_PATH, timeout=30) as conn:
                c = conn.cursor()
                # 更新用户的虚实构想
                c.execute("UPDATE user SET ticket = ticket + ? WHERE email=?", (n, f"{user_id}@qq.com",))
                # 更新nymph的虚实构想
                c.execute("UPDATE user SET ticket = ticket - ? WHERE user_id=?", (n, nymph_user_id,))
                conn.commit()
            
            return await msg.reply(f"好啦好啦，我赏你{n}枚虚实构想，下次我可不会再让你了！")
    
        elif grab_ticket == 40:
            with sqlite3.connect(DATABASE_PATH, timeout=30) as conn:
                c = conn.cursor()
                c.execute("SELECT ticket FROM user WHERE email=?", (f"{user_id}@qq.com",))
                user_ticket = c.fetchone()
                
                if user_ticket is None or user_ticket[0] <= 0:
                    return await msg.reply("什么？你居然一枚虚实构想都没有！没事，我会给你打欠条的！")
                
                # 计算可夺取的数量
                ticket = random.randint(0, 100)
                
                # 更新数据库
                c.execute("UPDATE user SET ticket = ticket + ? WHERE user_id=?", (ticket, nymph_user_id,))
                c.execute("UPDATE user SET ticket = ticket - ? WHERE email=?", (ticket, f"{user_id}@qq.com",))
                conn.commit()
                
                # 获取更新后的nymph的虚实构想数量
                c.execute("SELECT ticket FROM user WHERE user_id=?", (nymph_user_id,))
                nymph_ticket = c.fetchone()[0]

                # 获取更新后的玩家的虚实构想数量
                c.execute("SELECT ticket FROM user WHERE email=?", (f"{user_id}@qq.com",))
                user_rest_ticket = c.fetchone()[0]
            
            return await msg.reply(f"哎，这次拿的不多，不过你知道我的厉害就好，哈哈！{ticket}枚虚实构想我就收下了。嗯，没事...我数过，你还有{user_rest_ticket}枚的！\n我可是有{nymph_ticket}枚虚实构想的角色呢~")

    async def on_load(self):
        """插件加载时注册指令"""
        self.register_user_func(
            "/snatch",
            self.snatch,
            prefix="/snatch",
            description="虚实构想抽奖指令",
            usage="/snatch",
            examples=["/snatch"],
            tags=["user"]
        )
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")
