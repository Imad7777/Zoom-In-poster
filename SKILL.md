---
name: zoomin-collage-poster
description: "ZOOM IN! 认知拼贴海报生成 Skill：用户提供 1 张正面人像 + 4 张元素素材，一键生成 800×800 拼贴风海报。含本地 Python 管线（抠图→错位滤镜→8 层排布合成）、4 套风格底图与完整使用说明，无需编程知识。"
---

# ZOOM IN! 认知拼贴海报 Skill

把一张自拍变成复古拼贴风海报：人像自动抠图 → 青黄鲜三色错位叠印 → 与元素素材按固定版式合成 → 加渐变边框和 ZOOM IN! 标志。

## 三步用法

1. **放照片**：一张正面人像（`input/selfie.jpg`）
2. **备素材**：4 张元素图（E1 背景主块 / E2 前景点缀 / E3 道具左上 / E4 道具右中）
3. **跑一条命令**：

```bash
python scripts/generate.py --style 复古 --portrait input/selfie.jpg \
    --elements e1.png e2.png e3.png e4.png --out poster.png
```

注：氛围词（E5）只用于 AI 一次性生图路径的提示词槽位（见 style-guide.md），**本地管线不做全图冷暖调色**（原作业无此步，勿问用户要氛围词）。

- 风格：`可爱` / `复古` / `搞怪` / `酷帅`（或 cute / retro / funny / cool）
- 人像已抠好透明背景 → 加 `--no-cutout-portrait`
- 元素抠图默认开启：E1 背景块矩形直贴（原版拼贴块设计），E2-E4 贴纸自动走 rembg → 关闭用 `--no-cutout-elements`
- **人像默认先做双图参考风格化**（见下方「人像风格化 ★ 默认路径」），产物再进管线；用户明确要"真人质感/不要风格化"才直接贴原图，`--stylize oil` 为零依赖备选

## 环境准备（一次性）

```bash
pip install pillow        # 必需
pip install rembg         # 抠图后端二选一（推荐，首次运行自动下模型）
pip install modelscope    # 或原作业同款抠图后端（体积较大）
```

不装任何抠图后端也能跑：人像会以矩形直接贴入（建议此时自带透明底 PNG）。

## 人像风格化（替代原本地 SD，默认走双图参考）

原作业人像管线（已核实：**四风格共用同一套 SD payload，逐字段一致**）：
wd14 tagger 反推 tags → prompt `(oil painting:1.5), {tags}` → img2img **denoising 0.5** + ControlNet **tile**（只锁构图不锁质感）→ 512×512。
**SD 输出的实物（AfterSd_Koutu.png）验证：是干净的美型数字插画**——脸被 denoising 0.5 重绘理想化（「变好看」），无笔触无颗粒；颗粒/黑白/偏色全部来自滤镜层。四风格的差异全部来自生图之后的底图 + 三层滤镜。人像模板只需一个。

**★ 默认路径 · 真双图参考（v34 配方定稿；除非用户明确说"不要风格化/要真人质感"，否则一律先走这条再进管线）**

分工逻辑（v34 实测验证）：**第一张参考（用户照片）给脸**——下颌线/鼻梁/唇形/下巴前倾角度等特征来自本人；**第二张参考（艺术人像）给画风**——平滑绘画皮肤、精细发丝刻画、复古配色块背景（红棕/青/米）。结果即原版感觉：「既能看出来是谁，但又不是那么像真人，还变好看了」。

**关键教训（2026-10-15 复盘，勿回退）：艺术人像画风锚必须纯文生图生成，禁止用照片 img2img 生成**——img2img（哪怕 fidelity=low）产出的"艺术人像"本质是照片精修图，画风锚失效，步骤二两张参考风格趋同，必然滑回真人质感（与 E 方案同款证伪逻辑：img2img 永远是"还原"，不是"重绘"）。

**步骤一 · 反求身份符号 + 纯文生图画风锚**（**不传任何参考图**）：
1. 视觉分析用户照片，提取身份符号清单：发型发色 / 配饰（墨镜/头饰等）/ 服装特征 / 姿势手位 / **脸的类型**（眉/唇/下颌线/肤色——不锚定具体五官，只锚定"同一类人"）
2. 纯文生图提示词 = D 加强版三段式（身份符号段 + Face type 段 + Composition 文字 tile 段，骨架见下方「路径 D」模板，符号槽位按照片填）→ 产物存 `work/art_anchor.png`
3. **画风锚可跨照片复用**：同系列海报沿用同一张 `art_anchor.png`，换人/换造型才重新生成——保证系列画风统一（v35-v37 已验证）

**步骤二 · 双图参考分工重绘**：生图工具 `image=[用户照片, work/art_anchor.png]`、`input_fidelity=medium`、提示词用下方「分工模板」（逐字骨架，禁止临场改写质感/负面词）：

> ⚠️ **硬性检查（2026-10-15 事故）**：调用生图工具时 `image` 参数**必须显式传 `[用户照片路径, art_anchor路径]` 两张图**。漏传 `image` 不会报错，会静默降级成纯文生图——脸完全由模型自由发挥，产出"看起来像那么回事但完全不是本人"的假风格化图（v5 事故即此因）。生成后必须目检：脸是否跟着照片走。同时：尺寸固定 1024x1024（勿自作主张改竖版）、模板逐字照抄禁止增删句子（曾因加服装描述句导致画风漂移）。
>
> ⚠️ **保真度标定（2026-10-15 v6/v7 对比实测）**：`input_fidelity=medium` 在高质量正面照上会产出"照片精修"效果——太像本人，丢失原版「既像又不像」的重绘感。**要复现原版 denoising 0.5 的理想化重绘效果，双图参考一律用 `input_fidelity=low`**（脸被美化重绘，靠发型/服装/脸型符号认人），medium 仅在用户明确要"更像本人"时使用。另外生图产物若带"AI生成"水印且落在人像身上（抠图会保留），先把源图底部裁 60px 再进管线。
>
> ⚠️ **服装符号必补（2026-10-15 女生街拍实测）**：`input_fidelity=low` 下模型经常把照片里的服装整个丢掉（产出裸肩/换装）。双图参考时**必须显式补服装身份符号句**（如 "She is fully clothed, wearing the same beige knit cardigan over a dark top as in the first photo"）+ 负面词 `bare shoulders, exposed skin`——这属于身份符号槽位的必要填充，不算改写模板。

> Redraw the person from the first reference image as a semi-realistic digital painting portrait — keep his facial identity recognizable (face shape, brows, nose, lips, jawline from the first photo), but paint him in the exact art style of the second reference image: soft smooth painterly skin, fine hair strand detailing, vintage color-block background (brick red, teal, cream). Chest-up medium close-up, subject fills the frame, shoulders extending beyond the frame edges. Neutral white balance, keep the natural skin tone, no ochre/orange tint on the face. Flat even lighting, subtle film grain. Negative: photorealistic, photo texture, 3D render, white outline, edge stroke, rim light, sticker border, thick impasto, anime, cartoon, orange or yellow tinted skin, neon colors, text, watermark.

最终产物存 `work/portrait_dual.png`，再进管线（风格化产物自带绘画背景，照常走 rembg 抠图）：

```bash
python scripts/generate.py --style 复古 --portrait work/portrait_dual.png ...
```

**单图参考 · 路径 B（备选，画风锚生成失败时降级）——两步法**
先用生图工具按下方模板把人像美型插画化，产物存为 `work/portrait_oil.png`，再运行：

```bash
python scripts/generate.py --style 复古 --portrait work/portrait_oil.png ...
```

**主模板（唯一主推；替代 wd14 tags 的是手写身份特征句）**：

> Semi-realistic digital painting portrait based on the reference photo, idealized and flattering features, smooth clean rendering with beautiful soft shading — a painted, better-looking version of the reference, not photographic. The subject fills the frame, shoulders extend beyond the frame edges. Keeping the exact same hairstyle, hair color, accessories, clothing style, pose and expression as the reference so the identity stays recognizable. Keep the natural skin tone, no ochre/orange tint on the face. Neutral white balance — correct any warm indoor lighting cast from the reference. Vintage palette (brick red, teal, cream) applied to background and clothing only. Flat even lighting, plain painted background, subtle film grain. Negative: photorealistic, photo texture, oil painting brush strokes, thick impasto, 3D render, white outline, edge stroke, rim light, sticker border, altered identity, orange or yellow tinted skin, neon colors, text, watermark.

要点（历史踩坑记录，勿回退）：
- 原版 SD 输出 = **干净的美型数字插画**：脸被重绘理想化（「变好看」），无笔触无颗粒；颗粒全部来自滤镜层——生图端出干净插画，颗粒交给管线
- 身份逻辑：脸允许被美化重绘，靠**发型/发色/配饰/服装/姿势/表情**保持可辨认（原版 ControlNet tile 也只锁构图，不锁脸）
- **fidelity 用 low + 「inspired by / creative liberty」措辞**：high fidelity 会把输出锚定成「照片精修版」（太像真人）。已否决链：写实印刷 → 大笔触 impasto → 细笔触油画+重网点 → 高保真美型插画
- **满幅约束**（subject fills the frame, shoulders beyond edges）必须带：人像撑满画面才能让套色色边保持「细色带」比例，不满幅时色边会变成「彩色翻版人形」
- **禁描边**（white outline / edge stroke / rim light / sticker border）：插画风格易自代人像描边，抠图后会留下白边轮廓
- 肤色防黄三件套缺一不可：natural skin tone 句 + neutral white balance 句 + 调色板限定 background/clothing only

**二次转换（重绘步骤，对首绘结果再转一次，fidelity=low）**：

> Redraw this portrait as a stylized painterly illustration — dreamy idealized features, soft painterly skin, luminous delicate rendering. Keep the same composition and identity markers (hairstyle, accessories, clothing, pose). Chest-up medium close-up, subject fills the frame. Not photographic, not 3D. Negative: photorealistic, photo texture, white outline, edge stroke, rim light, thick impasto, anime, cartoon, orange or yellow tinted skin, neon colors, text, watermark.

**路径 E · 结构底稿模式（ControlNet tile 语义的确定性模拟，默认推荐）**

原理：tile 模型只把照片的**低频结构**（大色块/姿势/构图）注入生成，五官等高频细节根本不进入生成过程——所以脸自由重绘。云端模拟：送参考图**之前**先本地把照片毁掉细节——

```python
small = img.resize((w//8, h//8), Image.BILINEAR)   # 强降采样 1/8: 五官/纹理消失
out = small.resize((w, h), Image.BILINEAR)         # 回放: 只剩大色块+姿势剪影
out = ImageOps.autocontrast(out, cutoff=1)          # 拉开黑白场(逆光照片必要)
out = ImageOps.posterize(out.convert("RGB"), 4).convert("RGB")
out = out.filter(ImageFilter.GaussianBlur(3))
```

然后：**结构底稿作参考图（`input_fidelity=medium`）** + 提示词（主模板风格段 + 身份符号 + 「Paint over this composition, render the face as an idealized painted face」）。建议输入/输出 768×1152 级（过大过暗的底稿会让生图端输出全黑崩坏）。

效果（v31 实测）：姿势/构图/服装色块完全跟随照片（tile 语义），脸自由重绘——「既有真人的感觉又不太写实」同时达成，介于两步法与路径 D 之间。若生图输出全黑：先查底稿是否过大/过暗（autocontrast+缩小可解）。

**路径 D · 反求提示词 + 纯文生图（ControlNet tile 语义等价，艺术化最彻底）**

原理：原版 ControlNet **tile** 只把照片当「构图+色块」参考，脸是 SD 审美先验自由发挥的——所以原版效果「能看出是谁（发型/服装/姿势的组合识别）但完全不是那张脸」。云端等价实现 = **反求提示词后纯文生图，不传任何参考图**，彻底切断像素锚定。

流程：
1. **反求**：用视觉能力分析原照片，提取身份符号清单（发型发色/墨镜/服装品牌特征/姿势/手位/场景元素），写成具体文字描述
2. **纯文生图**：提示词 = 身份符号清单 + 主模板风格段（防黄三件套 + 满幅 + 禁描边）——**不带 image 参数**
3. 脸部完全由模型审美重绘（可能不是本人的脸，但气质/造型/vibe 一致——即原版 AfterSd_Koutu 卷发男的效果本质）

模板骨架（**加强版 v32 定稿**：身份符号 + 脸部类型 + 构图文字 tile 三段式）：

> A semi-realistic digital painting portrait of a young asian man, idealized and flattering features — a painted, better-looking version, not photographic. Face type: strong defined brows, thin lips, sharp clean jawline, healthy warm skin tone, short black fluffy wavy hair with a few strands sticking up. Wearing black rectangular sunglasses and a black retro track jacket with three white stripes. Composition: chest-up close-up, the head positioned in the upper third of the frame, arms crossed over chest at the center, shoulders extending beyond the frame edges, dark jacket filling the lower 40% of the frame. Smooth clean digital painting rendering with soft shading. Keep the natural skin tone, no ochre/orange tint. Neutral white balance. Vintage palette (brick red, teal, cream) on background and clothing only. Flat even lighting, plain painted background, subtle film grain. Negative: photorealistic, photo texture, oil painting brush strokes, thick impasto, 3D render, white outline, edge stroke, rim light, anime, cartoon, orange or yellow tinted skin, neon colors, text, watermark.

三段式要点（v32 实测定稿）：
- **身份符号段**：发型/墨镜/服装/姿势——「能看出是谁」的来源
- **脸部类型段**（Face type）：剑眉/薄唇/下颌线/肤色——让重绘脸和本人是「同一类人」但不复制五官
- **构图文字 tile 段**（Composition）：头部位置/肩部出画/服装占比——模拟 tile 的构图锁定，替代像素锚定
- 配合管线端人像宽撑满 680 + x=280 偏左 + 底出画 50px（pytorch2 版式）

取舍：艺术化最彻底、绝不像素锚定；脸部相似度归零（身份仅靠符号识别）、有 roll 随机性（可能需要 2-3 次挑选）。适合追求「海报艺术人物」而非「本人肖像」的场景。

**路径 A · 脚本内置近似（零依赖备选）**
`--stylize oil`。cv2+xphoto 不可用时自动降级为纯 Pillow 近似：
中值滤波块面化 → 色阶分离（posterize 6 级）→ 饱和度 ×1.35 → 描边叠加 15% → 胶片颗粒。
效果偏"扁平插画"，结构完全保留原照片。

**路径 C · opencv-contrib 增强（可选）**
`pip install opencv-contrib-python` 后 `--stylize oil` 自动改用 `cv2.xphoto.oilPainting` 真实笔触滤镜（比路径 A 更像手绘）。装不上也无妨，自动回退路径 A。

**备选模板（原版不常用，仅特殊需求）**：
- 写实印刷风（最接近真人）：`Retro printed portrait ... photo printed in an indie riso zine: fine film grain and subtle halftone dots overlay ...`（其余同主模板防黄三件套）

生成后仍走脚本的 抠图→错位滤镜→合成 流程，与原 SD 管线位置完全一致。

## 目录结构

```
zoomin-collage-poster/
├── SKILL.md                  ← 本文件
├── scripts/generate.py       ← 核心管线（抠图/滤镜/合成）
├── assets/
│   ├── base/                 ← 4 套 800×800 底图：cute/retro/funny/cool
│   ├── frame/frame.png       ← 彩虹渐变边框
│   └── logo/zoomin_logo.png  ← ZOOM IN! 标志
├── references/style-guide.md ← 完整视觉风格规则 + AI 生图提示词模板
├── references/element-prompts.md ← 元素素材固定提示词骨架（E1-E4）
└── input/                    ← 放入照片与素材
```

## 管线说明（对应原作业三段脚本）

| 步骤 | 原脚本 | 现实现 | 输出 |
|---|---|---|---|
| 1 人像处理 | 可爱滤镜.py | `cutout_image` + `make_portrait_effect` | portrait_effect.png |
| 2 元素处理 | 可爱排布.py 前半 + koutu.py | E2-E4 自动 `cutout_image`(贴纸类抠图)，E1 矩形直贴 | element_*_cut.png |
| 3 排布合成 | 可爱排布.py 后半 | `compose`（8 层固定坐标） | poster.png |

**签名效果（按风格分派——来自原作业各风格滤镜脚本的 `composite_images`，偏移为原版 1.0x 原参数）**：
- 可爱：鲜艳(对比/饱和/锐×1.5) / 青0.3 / 黄0.3，偏移 黄(10,-20)→青(-10,0)→本体(-30,20)
- 复古：vintage(饱和0.5+对比1.5+高斯噪std20+锐2) / 深墨绿(r≥36,g≤56,b≤23) / 黄(clamp 227/174/118)，偏移同可爱
- 搞怪：weird(暗0.67+对比1.85+红1.2蓝0.8) / 橙0.3 / 紫0.5，偏移同可爱
- 酷帅：赛博(饱和0.2+对比1.5) / 青0.3 / 粉0.3，偏移 粉(0,20)→青(-60,20)→本体(-30,20)——横向错位大于其他风格
- **偏移量计算依据**：抠图 512 高 → Effect 叠印 562 高 → 排布放大 680/562=1.21×，视觉色边 = 偏移×1.21（原版 1.0x → 本体↔色层视觉 ≈48px 单轴）。滤镜层 duotone 化后内容不可辨，偏移只控制色带几何宽度，**勿再收窄**
- 共同逻辑：抠图复制三份分别套滤镜，按偏移叠印在 +50px 画布上；**滤镜层（非本体层）duotone 双色调映射**（`_duotone`：灰度压 5 级 → `ImageOps.colorize` 沿暗↔亮色轴映射，暗/亮锚点取自原版 effect 中间产物取色，见 `DUOTONE` 表）——整层坍缩为单色调版画，「看上去只有颜色」；**叠印后印刷化后处理链按风格分派（PRINT_FX 表）**：复古=posterize 4 + halftone 0.3 + grain 20（原版滤镜自带 add_noise），可爱/搞怪/酷帅=posterize 4 + halftone 0.1 + grain 12（原版滤镜无噪声，轻量补偿保住美型插画干净质感）
- **人像满幅（管线端强制）**：compose 贴入时人像宽度撑满画布（≥700px），底部对齐画布底边、头顶留白——生图端满幅提示词不可靠，此处兜底，同时保证色带「细带」比例
- **`--brightness` 参数（搞怪专属）**：weird 底层亮度，默认 0.67 忠实原版；人穿深色衣服/本身偏暗的照片实测 **0.8 合适**（0.85 已验证过亮），勿超 0.85

**8 层版式（800×800 画布，中心坐标）**：
底图(800,400) → E1 450px@(130,380) → E2 400px@(700,700) → E3 500px@(280,150) → E4 450px@(580,270) → 人像高 670px@(320,560) → 边框(400,400) → logo 250×125@(670,70)。成品色调由底图+元素素材本身决定，不做全图调色（原作业即如此）。

**抠图模型**：人像用 rembg `u2net_human_seg`（人像专用，发丝更细腻），元素用默认 `u2net`。

## 元素怎么来

- **用户有素材图**：直接传路径（推荐 PNG 透明底）
- **用户只给文字关键词**：**必须**按 `references/element-prompts.md` 的固定骨架套模板生成（关键词只填 `{SUBJECT}` 槽位，**白底 opaque** / 1024x1024 / medium，勿用 transparent——生图端执行不可靠），禁止临场改写措辞——这是消除素材风格随机性的关键（原版靠本地 SD 固定 checkpoint 保风格，云端生图靠模板补）
- 五元素分配规则、配色规范、负面约束详见 `references/style-guide.md`

## 使用示例（无需编程）

把想说的话交给 AI 助手即可：
> 「用我的这张自拍，复古风格，元素：寺庙、猫、构图海报、军装小人，生成海报」

AI 会自动：确定风格=`复古` → 映射 E1=寺庙(背景) / E2=猫(前景) / E3=构图海报(道具) / E4=军装小人(道具) → 生成/收集素材 → 执行上述命令。

## 原代码处置清单（重构依据）

**pytorch/ 目录**：
- ✅ 保留重构：可爱滤镜.py（三层错位滤镜→`make_portrait_effect`）、可爱排布.py（8 层合成→`compose`）、koutu.py（抠图→`cutout_image`，改为 rembg 优先的双后端）
- 🔄 参数化：硬编码路径（`capture.png`、`D:\大学牲\...`）、CSV 关键词中间层全部改为 CLI 参数
- ❌ 删除：ArduinoSerial4.0/5.0、FinalSerial、PlayerA/B_FinalSerial、Control/TwoControl/Close（Arduino 串口交互）；全部 MP3 音效；SdCsvDeliver/Txt_Deliver（CSV 传输层）；sdTry/sdFinalDeliver/stableDiffusionDeliver/Img2img（SD 本地部署实验脚本，SD 生图改为外部生图工具按风格规则产出）；.idea
- ✅ 打包：可爱/复古/搞怪/酷帅 1.png → assets/base/；35.png → assets/frame/；logo.png → assets/logo/

**前端Code/ 目录**：❌ 全部删除（136 个 html/mp4 为 Arduino 互动装置的视频播放网页，与本效果无关）

## 已知限制

- 输出锁定 800×800（原作业版式即此尺寸）；要更高分辨率需同步放大素材与坐标（均可按比例换算）
- `rembg` 人像抠图已默认用 `u2net_human_seg` 人像专用模型；强光/逆光背景仍可能毛边，可用 `--no-cutout-portrait` 配合预先精抠，或先走路径 B 风格化让质感吞掉毛边
- 路径 A 的 Pillow 近似质感偏"扁平插画"；要最接近原作业效果用路径 B（固定提示词），或装 opencv-contrib 走路径 C
- 原 SD 的 wd14 tagger 反推提示词环节不再需要：路径 B 的固定提示词已覆盖印刷质感风格定义
