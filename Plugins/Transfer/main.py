import os
import sqlite3
from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import BaseMessage
from ncatbot.utils import get_log
LOG = get_log("Transfer")
bot = CompatibleEnrollment
BASE_DIR = os.path.dirname(os.path.abspath(__file__)) 
PARENT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(BASE_DIR)))  
DB_PATH = os.path.join(PARENT_DIR, "ArkanaServer\\database\\arcaea_database.db")
class Transfer(BasePlugin):
    name = "Transfer"
    version = "1.0.0"
    author = "Swiro"
    description = "Ticket转账插件"
    dependencies = {}

    async def Transfer(self, msg: BaseMessage):
        parts = list(msg.raw_message.split())
        if len(parts) != 3:
            return await msg.reply("参数错误，请按照格式：\n/transfer [@收款方] [数量]")
        if not parts[2].isdigit():
            return await msg.reply("参数错误，请按照格式：\n/transfer [@收款方] [数量]")
        count = int(parts[2])
        with sqlite3.connect(DB_PATH, timeout=30) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT user_id, ticket FROM user WHERE email=?", (str(msg.sender.user_id) + "@qq.com",))
            origin_user = cursor.fetchone()
            if origin_user is None:
                return await msg.reply("你还没有注册，请先注册！")
            if origin_user[1] < count:
                return await msg.reply("余额不足！")
            qq_id = parts[1]
            if qq_id.strip().startswith("[CQ:at,qq=") and qq_id.strip().endswith("]"):
                qq_id = qq_id.strip()[10:-1]
            cursor.execute("SELECT user_id FROM user WHERE email=?", (qq_id + "@qq.com",))
            target_user = cursor.fetchone()
            if target_user is None:
                return await msg.reply("找不到收款方！")
            else:
                cursor.execute("UPDATE user SET ticket=ticket+? WHERE user_id=?", (count, target_user[0]))
                conn.commit()
                cursor.execute("UPDATE user SET ticket=ticket-? WHERE user_id=?", (count, origin_user[0]))
                conn.commit()
                await msg.reply(f"转账成功，{parts[2]}枚虚实构想已转给{parts[1]}！")
        LOG.info(f"收到转账请求：{msg.sender.user_id} -> {parts}")

    async def on_load(self):
        self.register_user_func(
            "/transfer",
            self.Transfer,
            prefix="/transfer",
            description="Ticket转账插件",
            usage="/transfer qq num",
            examples=["/transfer 123456 10"],
            tags=["user"]
        )
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")