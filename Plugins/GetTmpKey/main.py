from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import BaseMessage
from ncatbot.utils import get_log
from datetime import datetime

LOG = get_log("GetTmpKey")
bot = CompatibleEnrollment

class GetTmpKey(BasePlugin):
    name = "GetTmpKey"
    version = "1.0.0"
    author = "Swiro"
    description = "生成临时密钥插件"
    dependencies = {}

    async def generate_tmpkey(self, msg: BaseMessage):
        """处理生成临时密钥的命令"""
        qq_id = msg.sender.user_id
        try:
            if hasattr(msg, "group_id"):
                return await msg.reply("为了您的账号安全，请私聊我生成临时密钥。")
            now = datetime.now()
            minute_block = now.minute // 5
            xor_key = f"{minute_block}{now.hour}{now.date()}{minute_block}".encode()
            plaintext = str(qq_id).encode()
            xor_key_len = len(xor_key)
            if len(plaintext) < xor_key_len:
                plaintext += b'#' * (xor_key_len - len(plaintext))
            plaintext = bytes(b + 6 for b in plaintext)
            code = bytes(i ^ j for i, j in zip(plaintext, xor_key)).hex()
            await msg.reply("已为您生成临时密钥，请在五分钟内使用，为了方便您复制，故单独发送临时密钥消息。")
            await msg.reply(code)
            LOG.info(f"为QQ号 {qq_id} 生成了临时密钥")
        except Exception as e:
            await msg.reply(f"生成临时密钥失败: {str(e)}")
            LOG.error(f"生成临时密钥时出错: {str(e)}")

    async def on_load(self):
        """插件加载时注册命令"""
        self.register_user_func(
            "/tmpkey", 
            self.generate_tmpkey, 
            prefix="/tmpkey", 
            description="生成临时密钥用于注册账号等相关操作",
            usage="/tmpkey",
            examples=["/tmpkey"],
            tags=["user"]
        )
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")