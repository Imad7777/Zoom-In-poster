---
name: element-prompts
description: "元素素材(E1-E4)生图提示词模板——固定骨架+关键词槽位，消除逐次生成的措辞随机性，保证系列海报素材风格一致。"
---

# 元素素材提示词模板（A 方案 · 固定骨架）

> 用法：AI 助手生成元素素材时，**必须**把用户关键词填入 `{SUBJECT}` 槽位套用下列骨架，禁止临场改写质感词/配色词/负面词。
> 参数：**全部用白底（`background=opaque`，勿用 transparent——生图端执行不可靠，会翻车成实底卡片）**、`size=1024x1024`、`quality=medium`（系列成片可升 high）。
> 生图后：E2/E3/E4 由管线自动抠图（rembg），E1 保持矩形直贴——见 SKILL.md。

## 骨架 1 · E1 背景主块（大块纹样/场景，矩形拼贴块，不抠图）

```
{SUBJECT} as a large ornamental background panel with decorative frame, riso screen-print style poster element, flat colors: mustard yellow #D9A441, brick red #B5442E, teal #2E7F86, cream #EFE6D0, halftone dot texture, paper grain, flat lighting, no cast shadow, square composition, decorative gibberish letters only, centered
```

负面词（骨架 1 专属，**不含卡片禁令**——frame/border 是 E1 的正面向，禁令会打架）：

```
Negative: photorealistic photo texture, 3D render, glossy CG, digital smooth gradients, neon colors, readable text, watermark, drop shadow
```

## 骨架 2 · E2 / E3 / E4 点缀与道具（单件贴纸，白底生成 + 管线抠图）

```
{SUBJECT}, the object itself is the entire shape filling most of the frame, riso screen-print sticker style, flat colors: mustard yellow #D9A441, brick red #B5442E, teal #2E7F86, cream #EFE6D0, halftone dot texture, paper grain, flat lighting, no cast shadow, single isolated object on plain white background, centered
```

负面词（骨架 2 专属，含卡片禁令——防止贴纸类生成带边框的实底卡片）：

```
Negative: photorealistic photo texture, 3D render, glossy CG, digital smooth gradients, neon colors, readable text, watermark, drop shadow, square card, panel border, frame
```

## 规则

1. **只允许改 `{SUBJECT}`**（可附 1-2 个必要限定词，如 "Miao ethnic silver headdress crown"、"indigo batik fabric swatch"），骨架其余部分逐字保留。
2. **配色微调**：若海报主色不是默认四色，可整体替换 `flat colors:` 后的色值列表，但**色值必须取自 style-guide.md 配色表**，且主色 ≤3 个。
3. **禁止**添加骨架之外的质感词、构图词、镜头词——那些是风格漂移的来源。
4. 人物照片不适用本模板（人像走 SKILL.md 路径 B 的模板 1/2）。
