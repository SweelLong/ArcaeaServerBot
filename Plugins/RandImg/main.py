from ncatbot.plugin import BasePlugin, CompatibleEnrollment
from ncatbot.core.message import BaseMessage
from ncatbot.core import MessageChain, Image
from ncatbot.utils import get_log
import os
import random
import re
LOG = get_log("RandImg")
bot = CompatibleEnrollment
class RandImg(BasePlugin):
    name = "RandImg"
    version = "1.0.0"
    author = "Swiro"
    description = "发送随机二次元图片"
    dependencies = {}
    async def _load_image(self):
        """加载配置路径中的图片"""
        paths = self.config["path"].split(";")
        self.images = []
        for path in paths:
            path = path.strip()
            if not path or not os.path.exists(path):
                continue
            if self.config["recursive"]:
                for root, _, files in os.walk(path):
                    for file in files:
                        self.images.append(os.path.join(root, file))
            else:
                for file in os.listdir(path):
                    file_path = os.path.join(path, file)
                    if os.path.isfile(file_path):
                        self.images.append(file_path)
        LOG.info(f"共加载了 {len(self.images)} 张图片")
        return len(self.images)
    async def send_image(self, msg: BaseMessage, count: int):
        """发送指定数量的随机图片"""
        if len(self.images) < count:
            await msg.reply(f"图片数量不足，当前只有 {len(self.images)} 张图片")
            return
        selected_images = random.sample(self.images, count)
        msg_chain = MessageChain([Image(image) for image in selected_images])
        if hasattr(msg, "group_id"):
            await self.api.post_group_msg(msg.group_id, rtf=msg_chain)
        else:
            await self.api.post_private_msg(msg.user_id, rtf=msg_chain)
    async def img(self, msg: BaseMessage):
        """处理/img命令"""
        count = 1
        match = re.match(r"/img\s*(\d+)?", msg.raw_message)
        if match and match.group(1):
            try:
                count = int(match.group(1))
                count = max(1, min(self.config["max_count"], count))
            except ValueError:
                count = 1
        await self.send_image(msg, count)
    async def on_load(self):
        """插件加载时初始化配置和注册命令"""
        self.register_config("path", "plugins/RandImg/images", description="图片路径, 支持多个, 用 `;` 分割", value_type="str")
        self.register_config("recursive", False, description="是否递归加载子目录中的图片", value_type="bool")
        self.register_config("max_count", 5, description="一次请求最大发送数量", value_type="int")
        self.register_user_func(
            "/img", 
            self.img, 
            prefix="/img", 
            description="发送随机二次元图片",
            usage="/img [数量] - 发送若干张随机二次元图片，默认为1张",
            examples=["/img", "/img 3"],
            tags=["user"]
        )
        self.images = []
        await self._load_image()
        LOG.info(f"{self.name} 插件已加载，版本: {self.version}")