# CowAgent 微信通道语音回复功能

## 功能概述

为 Weixin 通道（ilink 机器人协议）增加 TTS 语音回复能力，支持以下交互：

| 命令 | 效果 |
|------|------|
| `/voice on` | 开启语音回复：每次回复**先发文本，再发语音文件** |
| `/voice off` | 关闭语音回复，仅发送文本 |
| `/voice speed <1.0-4.0>` | 设置 TTS 语速倍率（默认 1.0） |

语音内容会经过自动清洗：去掉 Markdown 标记符号、表格转换为"如下表所示"、移除 Emoji，确保合成语音自然。

## 依赖安装

语音合成使用 `edge-tts`（免费，内置中文语音），音频处理需要 `pydub`。

```bash
pip install edge-tts pydub
```

## 修改的文件

### 1. `voice/edge/edge_voice.py`

添加语速（rate）参数支持。

**改动内容：**
- `gen_voice()` 新增 `rate` 参数，传递给 `edge_tts.Communicate`
- `textToVoice()` 从 `conf()["text_to_voice_rate"]` 读取语速设置
- 日志增加 rate 输出

```python
# gen_voice 方法（新增 rate 参数）
async def gen_voice(self, text, fileName, rate=""):
    kwargs = {"voice": self.voice}
    if rate:
        kwargs["rate"] = rate
    communicate = edge_tts.Communicate(text, **kwargs)
    await communicate.save(fileName)

# textToVoice 方法（从配置读取 rate）
def textToVoice(self, text):
    fileName = TmpDir().path() + "reply-" + str(int(time.time())) + "-" + str(hash(text) & 0x7FFFFFFF) + ".mp3"
    rate = conf().get("text_to_voice_rate", "")
    asyncio.run(self.gen_voice(text, fileName, rate))
    logger.info("[EdgeTTS] textToVoice text={} voice file name={} rate={}".format(text, fileName, rate or "default"))
    return Reply(ReplyType.VOICE, fileName)
```

---

### 2. `channel/weixin/weixin_channel.py`

核心改动，包含 6 个部分：

#### 2a. 新增 import

```python
import re  # 文本清洗用正则
```

#### 2b. 文本清洗函数 `_clean_text_for_tts()`

添加在 `WeixinChannel` 类之前。对 LLM 返回的文字进行预处理：

| 输入 | 处理 |
|------|------|
| `# 标题` | 去掉 `#`，保留"标题" |
| `**加粗**` | 去掉 `**`，保留文字 |
| `` `代码` `` | 替换为"以下是代码内容，" |
| Markdown 表格 | 替换为"如下表所示，" |
| Emoji 表情 | 全部移除 |
| 连续空行 | 合并为两个换行 |

**Emoji 正则说明：** 使用精准的 Unicode 范围，仅匹配 Emoji 区域的字符，**不覆盖 CJK 汉字区域**。如果将来 Unicode 新增 Emoji 范围，可能需要补充。

#### 2c. 类属性与初始化

```python
NOT_SUPPORT_REPLYTYPE = []  # 解除基类对 VOICE 类型的限制
```

`__init__` 中新增：
```python
self._voice_enabled = {}  # user_id -> bool，按用户记录语音开关
self._voice_speed = {}    # user_id -> float (1.0-4.0)，按用户记录语速
```

#### 2d. 命令处理（`_process_message`）

在 `ContextType.TEXT` 分支中，优先拦截 `/voice` 前缀的命令：

- `/voice on` → 设置 `_voice_enabled[user_id] = True`，回复用户"语音已开启"
- `/voice off` → 设置 `_voice_enabled[user_id] = False`，回复用户"语音已关闭"
- `/voice speed <value>` → 限制 1.0-4.0，保存到 `_voice_speed[user_id]`
- 无效参数 → 回复用法提示

这些命令**不转发给 LLM**。

#### 2e. 发送逻辑（`send()` 方法）

在 `ReplyType.TEXT` 分支中，发送文本后增加语音二次发送：

```python
if reply.type == ReplyType.TEXT:
    self._send_text(reply.content, receiver, context_token)
    # 如果该用户开启了语音回复
    if self._voice_enabled.get(receiver, False):
        clean_text = _clean_text_for_tts(reply.content)    # 清洗文本
        speed = self._voice_speed.get(receiver, 1.0)
        if speed != 1.0:
            conf()["text_to_voice_rate"] = f"+{int((speed-1.0)*100)}%"
        voice_reply = self.build_text_to_voice(clean_text)   # TTS 合成
        if speed != 1.0:
            conf().pop("text_to_voice_rate", None)           # 清理临时配置
        if voice_reply.type == ReplyType.VOICE:
            self._send_voice(voice_reply.content, ...)        # 发送语音文件
```

同时新增 `ReplyType.VOICE` 分支（供其他代码路径使用）。

#### 2f. `_send_voice()` 方法

ilink 机器人协议不支持原生语音消息（type=3），因此使用文件消息（type=4）发送音频：

```python
def _send_voice(self, voice_file_path, receiver, context_token):
    local_path = self._resolve_media_path(voice_file_path)
    ...
    result = upload_media_to_cdn(self.api, local_path, receiver, media_type=3)
    self.api.send_file_item(
        to=receiver, context_token=context_token,
        encrypt_query_param=result["encrypt_query_param"],
        aes_key_b64=result["aes_key_b64"],
        file_name=f"voice_{int(time.time())}.mp3",
        file_size=result["raw_size"],
    )
```

---

### 3. `agent/protocol/agent_stream.py`

修复微信通道图片无法被 LLM Vision 识别的问题。所有通道（微信、网页、飞书、钉钉、QQ 等）统一受益。

**问题原因：** 通道收到图片后下载到本地，在下一条文字消息中追加 `[图片: /path]` 文本引用。Agent 一直以纯文本形式发给 LLM，LLM 需要自行调用 `vision` 工具来分析图片——这经常失败。

**修复方式：** 在 `run_stream()` 中将 `[图片: /path]` 引用解析出来，加载图片为 base64，构造正确的多模态内容块：

```python
# 之前（纯文本，靠 LLM 猜是否调用 vision）
{"role": "user", "content": [{"type": "text", "text": "这是什么 [图片: /tmp/a.jpg]}]}

# 之后（LLM 原生看到图片）
{"role": "user", "content": [
    {"type": "text", "text": "这是什么"},
    {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,/9j..."}}
]}
```

**新增代码位置：** `agent/protocol/agent_stream.py`，`run_stream()` 方法之前：

```python
import base64
import os
import re
from typing import List, Tuple

_IMAGE_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}
_IMAGE_REF_RE = re.compile(r'\[图片:\s*([^\]]+)\]')

def _parse_image_refs(text: str) -> Tuple[str, List[str]]:
    paths = _IMAGE_REF_RE.findall(text)
    clean = _IMAGE_REF_RE.sub('', text).strip()
    seen = set()
    unique = []
    for p in paths:
        p = p.strip()
        if p and p not in seen:
            seen.add(p)
            unique.append(p)
    return clean, unique

def _build_image_blocks(image_paths: List[str]) -> List[Dict]:
    blocks = []
    for path in image_paths:
        if not os.path.isfile(path):
            continue
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext not in _IMAGE_EXTENSIONS:
            continue
        try:
            with open(path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                    "png": "image/png", "gif": "image/gif",
                    "webp": "image/webp"}.get(ext, "image/jpeg")
            blocks.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            })
        except Exception:
            pass
    return blocks
```

**`run_stream()` 中的修改（约 248 行）：**

```python
# 改为多模态内容块
clean_text, image_paths = _parse_image_refs(user_message)
content_blocks = [{"type": "text", "text": clean_text}]
if image_paths:
    image_blocks = _build_image_blocks(image_paths)
    content_blocks.extend(image_blocks)
self.messages.append({"role": "user", "content": content_blocks})
```

---

### 4. `config.json`

当前配置已设定默认值，无需额外修改即可使用：

```json
{
    "text_to_voice": "edge",
    "voice_reply_voice": false,
    "always_reply_voice": false,
    "speech_recognition": true
}
```

- `text_to_voice`: 使用 `"edge"`（免费，中文语音好）
- `always_reply_voice`: 保持 `false`，由 `/voice on/off` 命令控制
- `speech_recognition`: 保持 `true`，语音输入自动转文字

## 在其他机器上部署

### 步骤

1. **复制四个修改后的文件：**
   - `voice/edge/edge_voice.py`
   - `channel/weixin/weixin_channel.py`
   - `agent/protocol/agent_stream.py`
   - `config.json`（或合并配置项）

2. **安装依赖：**
   ```bash
   pip install edge-tts pydub
   ```

3. **验证（启动后）：**
   - 向机器人发一条文字消息，确认普通文本回复正常
   - 发 `/voice on`，确认收到"语音回复已开启"
   - 再发一条文字，确认先收到文本后收到 `voice_xxx.mp3` 文件
   - 发 `/voice speed 2.0` 调节语速后测试
   - 发送一张图片并问"这张图里是什么"，确认 LLM 能识别图片内容（不再返回"我看不到图片"）

### 如果使用其他 TTS 提供商

要支持语速调节，需要修改对应的 TTS 实现类，从 `conf().get("text_to_voice_rate")` 读取 rate 参数。目前仅 `edge` 支持。

## 已知限制

| 限制 | 说明 |
|------|------|
| 语音格式 | 以 MP3 文件形式发送，非原生语音消息（ilink 协议限制） |
| 重启后设置清空 | `_voice_enabled` / `_voice_speed` 保存在内存中，重启后需重新 `/voice on` |
| 语速仅支持 edge | 仅 `EdgeVoice` 实现了 rate 参数，其他 TTS 提供商需自行修改 |
| 图片格式 | 支持 jpg/png/gif/webp，大图片（>1MB）自动压缩后发送给 LLM |
