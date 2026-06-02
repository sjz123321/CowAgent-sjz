# CowAgent (Fork)

本项目 fork 自 [zhayujie/CowAgent](https://github.com/zhayujie/CowAgent)，基于原项目进行了以下定制修改。

## 修改内容

### 微信通道语音回复

为微信通道增加 TTS 语音回复能力，支持按用户控制的语音开关和语速调节。

- **`/voice on` / `/voice off`** — 开启/关闭语音回复。开启后每次回复先发文本，再发语音文件
- **`/voice speed <1.0-4.0>`** — 设置 TTS 语速倍率（默认 1.0）
- 文本自动清洗：去除 Markdown 标记、Emoji、表格替换为"如下表所示"
- 语音通过 edge-tts（免费，中文语音好）合成，以 MP3 文件形式发送
- 涉及文件：`voice/edge/edge_voice.py`、`channel/weixin/weixin_channel.py`

### 图片 Vision 识别修复

修复微信通道图片无法被 LLM Vision 识别的问题。

- 将文本中的 `[图片: /path]` 引用自动解析为多模态内容块
- LLM 直接"看到"图片内容，无需依赖 vision 工具被调用
- 所有使用 `[图片: /path]` 约定的通道（微信、飞书、钉钉、QQ 等）统一受益
- 涉及文件：`agent/protocol/agent_stream.py`

### 临时文件自动清理

- **启动时自动清理**：每次启动清理 ./tmp/ 中超过 7 天的临时文件
- **`/clear-log` 命令**：手动清理所有缓存文件（语音文件、下载的图片等）
- 涉及文件：`common/tmp_dir.py`、`channel/weixin/weixin_channel.py`

### 部署文档

`docs/weixin-tts-guide.md` 包含上述所有功能在其它机器上部署的详细步骤。
