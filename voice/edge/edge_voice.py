import time

import edge_tts
import asyncio

from bridge.reply import Reply, ReplyType
from common.log import logger
from common.tmp_dir import TmpDir
from config import conf
from voice.voice import Voice


class EdgeVoice(Voice):

    def __init__(self):
        '''
        # 普通话
        zh-CN-XiaoxiaoNeural
        zh-CN-XiaoyiNeural
        zh-CN-YunjianNeural
        zh-CN-YunxiNeural
        zh-CN-YunxiaNeural
        zh-CN-YunyangNeural
        # 地方口音
        zh-CN-liaoning-XiaobeiNeural
        zh-CN-shaanxi-XiaoniNeural
        # 粤语
        zh-HK-HiuGaaiNeural
        zh-HK-HiuMaanNeural
        zh-HK-WanLungNeural
        # 湾湾腔
        zh-TW-HsiaoChenNeural
        zh-TW-HsiaoYuNeural
        zh-TW-YunJheNeural
        '''
        self.voice = "zh-CN-YunjianNeural"

    def voiceToText(self, voice_file):
        pass

    async def gen_voice(self, text, fileName, rate=""):
        kwargs = {"voice": self.voice}
        if rate:
            kwargs["rate"] = rate
        communicate = edge_tts.Communicate(text, **kwargs)
        await communicate.save(fileName)

    def textToVoice(self, text):
        fileName = TmpDir().path() + "reply-" + str(int(time.time())) + "-" + str(hash(text) & 0x7FFFFFFF) + ".mp3"

        rate = conf().get("text_to_voice_rate", "")
        asyncio.run(self.gen_voice(text, fileName, rate))

        logger.info("[EdgeTTS] textToVoice text={} voice file name={} rate={}".format(text, fileName, rate or "default"))
        return Reply(ReplyType.VOICE, fileName)
