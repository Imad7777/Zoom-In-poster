# -*- coding: utf-8 -*-
"""
ZOOM IN! 认知拼贴海报生成器（简化版 Skill 核心脚本）

三步用法:
  1. 准备一张正面人像照片 (jpg/png)
  2. 准备 4 张元素素材图 (png, 建议带透明背景)
  3. 运行:
     python generate.py --style retro --portrait selfie.jpg \
         --elements e1.png e2.png e3.png e4.png --out poster.png

注: 氛围词(E5)不参与本地管线调色, 原作业无此步;
    仅在使用 AI 一次性生成整张海报时(style-guide.md 模板)作为提示词槽位。

依赖: pip install pillow
可选抠图后端(任一): pip install rembg  或  pip install modelscope
  -- 未安装任何抠图后端时, 人像需自带透明背景(否则以矩形贴入)
可选油画风格化: pip install opencv-contrib-python numpy
  -- --stylize oil 在抠图前把照片转为油画质感, 无需本地部署 SD
"""
import argparse
import os
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageOps

SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_DIR = os.path.join(SKILL_DIR, "assets", "base")
FRAME_PATH = os.path.join(SKILL_DIR, "assets", "frame", "frame.png")
LOGO_PATH = os.path.join(SKILL_DIR, "assets", "logo", "zoomin_logo.png")
SUNFLOWER_PATH = os.path.join(SKILL_DIR, "assets", "stickers", "sunflower.png")
CAMERA_PHOTO_PATH = os.path.join(SKILL_DIR, "assets", "stickers", "camera_photo.png")

STYLE_FILE = {
    "可爱": "cute.png",
    "复古": "retro.png",
    "搞怪": "funny.png",
    "酷帅": "cool.png",
}
STYLE_ALIAS = {"cute": "可爱", "retro": "复古",
               "funny": "搞怪", "cool": "酷帅"}

CANVAS = 800  # 原作业锁定 800x800 画布


# ---------------------------------------------------------------- 抠图后端
def cutout_image(input_path, output_path, model="u2net"):
    """人像/元素抠图: 优先 rembg, 其次 modelscope, 都没有则原样返回。
    model: rembg 模型名, 人像用 u2net_human_seg(发丝更细腻), 元素用默认 u2net
    """
    try:
        from rembg import remove, new_session  # noqa
        try:
            session = new_session(model)
        except Exception:
            session = None  # 模型不可用时退回默认
        with open(input_path, "rb") as f_in:
            result = remove(f_in.read(), session=session) if session else remove(f_in.read())
        with open(output_path, "wb") as f_out:
            f_out.write(result)
        return output_path
    except ImportError:
        pass
    try:
        import cv2  # noqa
        from modelscope.pipelines import pipeline
        from modelscope.utils.constant import Tasks
        from modelscope.outputs import OutputKeys
        matting = pipeline(Tasks.universal_matting,
                           model="damo/cv_unet_universal-matting")
        res = matting(input_path)
        cv2.imwrite(output_path, res[OutputKeys.OUTPUT_IMG])
        return output_path
    except ImportError:
        print("[warn] 未安装 rembg/modelscope, 跳过抠图, 直接使用原图")
        return input_path


# ---------------------------------------------------- 油画风格化(替代本地SD)
def _grain(img, strength=18):
    """叠加胶片颗粒, 模拟印刷噪点(近似原 SD 成图后的 riso 质感)"""
    try:
        import numpy as np
        arr = np.array(img.convert("RGB")).astype("int16")
        noise = np.random.randint(-strength, strength + 1, arr.shape[:2])
        arr = np.clip(arr + noise[..., None], 0, 255).astype("uint8")
        return Image.merge("RGBA", (*Image.fromarray(arr).split(), img.split()[3]))
    except ImportError:
        return img


def _oil_pil(img, size=9, levels=6):
    """纯 Pillow 近似油画: 中值滤波块面化 + 色阶分离 + 描边增强"""
    q = img.filter(ImageFilter.MedianFilter(size))
    q = ImageOps.posterize(q.convert("RGB"), levels)
    q = ImageEnhance.Color(q).enhance(1.35)
    edges = q.convert("L").filter(ImageFilter.FIND_EDGES)
    edges = ImageEnhance.Contrast(edges).enhance(1.4)
    q = Image.blend(q, Image.merge("RGB", (edges, edges, edges)), 0.15)
    a = img.split()[3] if img.mode == "RGBA" else Image.new("L", q.size, 255)
    return Image.merge("RGBA", (*q.split(), a))


def stylize_oil(input_path, output_path):
    """油画风格化: 替代原 SD tagger+img2img+ControlNet 管线。
    优先 OpenCV xphoto.oilPainting(真实笔触块面), 未装则退化为纯 Pillow 近似。
    两版均基于原图结构, 面部相似度基本保留。
    """
    img = Image.open(input_path).convert("RGBA")
    try:
        import cv2  # noqa
        import numpy as np
        bgr = np.array(img.convert("RGB"))[:, :, ::-1].copy()
        try:  # opencv-contrib 才有 xphoto
            painted = cv2.xphoto.oilPainting(bgr, 7, 1)
        except AttributeError:
            painted = None
        if painted is not None:
            out = Image.merge("RGBA", (*Image.fromarray(painted[:, :, ::-1]).split(),
                                       img.split()[3]))
        else:
            print("[warn] 当前 opencv 无 xphoto 模块, 使用 Pillow 近似油画")
            out = _oil_pil(img)
    except ImportError:
        print("[warn] 未安装 opencv-contrib-python, 使用 Pillow 近似油画")
        out = _oil_pil(img)
    out = _grain(out)
    out.save(output_path)
    print(f"[stylize] 油画风格化完成: {output_path}")
    return output_path


# ------------------------------------------------------------ 人像错位滤镜
# 原作业每个风格一套滤镜组合+偏移(来自 可爱/复古/搞怪/酷帅滤镜.py 的 composite_images)
# 列表顺序=paste 顺序(先底层后顶层), 最后一项是人像本体层

def _np(img):
    """RGBA -> int16 numpy 数组"""
    return np.array(img.convert("RGBA")).astype("int16")


def _img(arr):
    """int16 numpy 数组 -> RGBA Image (自动 clamp)"""
    return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGBA")


def _pil_fx(img, color=None, contrast=None, brightness=None, sharpness=None):
    """按顺序应用 PIL 增强, 保留 alpha"""
    img = img.convert("RGBA")
    if color is not None:
        img = Image.merge("RGBA", (*ImageEnhance.Color(img.convert("RGB")).enhance(color).split(), img.split()[3]))
    if contrast is not None:
        img = Image.merge("RGBA", (*ImageEnhance.Contrast(img.convert("RGB")).enhance(contrast).split(), img.split()[3]))
    if brightness is not None:
        img = Image.merge("RGBA", (*ImageEnhance.Brightness(img.convert("RGB")).enhance(brightness).split(), img.split()[3]))
    if sharpness is not None:
        img = Image.merge("RGBA", (*ImageEnhance.Sharpness(img.convert("RGB")).enhance(sharpness).split(), img.split()[3]))
    return img


def _f_vivid(img):
    """可爱底层: 对比/饱和/锐度各 x1.5 (原 make_image_vivid)"""
    return _pil_fx(img, color=1.5, contrast=1.5, sharpness=1.5)


def _f_vintage(img):
    """复古底层: 饱和0.5 + 对比1.5 + 高斯噪std20 + 锐度2 (原 apply_vintage_filter+add_noise)"""
    img = _pil_fx(img, color=0.5, contrast=1.5, sharpness=2.0)
    arr = _np(img).astype("float32")
    noise = np.random.normal(0, 20, arr.shape[:2])[:, :, None]  # 灰度噪声加到所有通道
    return _img(arr + noise)


def _f_weird(img, brightness=0.67):
    """搞怪底层: 红1.2/蓝0.8阈值调色 + 亮度(原0.67) + 对比1.85 (原 process_image)。
    偏暗照片可用 --brightness 0.8-0.9 提亮, 默认忠实原版。"""
    arr = _np(img)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    red_mask = (r > 100) & (r > g) & (r > b)
    blue_mask = (b > 100) & (b > r) & (b > g) & ~red_mask
    arr[..., 0] = np.where(red_mask, np.clip(r * 1.2, 0, 255), r)
    arr[..., 2] = np.where(blue_mask, np.clip(b * 0.8, 0, 255), b)
    return _pil_fx(_img(arr), brightness=brightness, contrast=1.85)


def _f_cyber(img):
    """酷帅底层: 饱和0.2 + 对比1.5 (原 reduce_saturation_and_increase_contrast)"""
    return _pil_fx(img, color=0.2, contrast=1.5)


def _channel_fx(img, r_add=None, g_add=None, b_add=None, r_min=0, g_min=0, b_min=0,
                r_max=255, g_max=255, b_max=255):
    """通用通道滤镜(向量化等价原逐像素实现)
    *_add: 加到该通道的增量系数 k, 如 r+k*(255-r); None 则该通道不变
    *_min/*_max: 通道结果 clamp 边界"""
    arr = _np(img).astype("float32")
    for i, (k, lo, hi) in enumerate(((r_add, r_min, r_max), (g_add, g_min, g_max), (b_add, b_min, b_max))):
        if k is not None:
            arr[..., i] = np.clip(arr[..., i] + k * (255 - arr[..., i]) if k >= 0
                                  else arr[..., i] + k * arr[..., i], lo, hi)
    return _img(arr)


def _f_teal(img, k=0.3):
    """青色滤镜(可爱/酷帅): 减红、增益蓝绿"""
    return _channel_fx(img, r_add=-k, g_add=k, b_add=k)


def _f_yellow(img, k=0.3):
    """黄色滤镜(可爱): 增红黄、压蓝(min 100)"""
    return _channel_fx(img, r_add=k, g_add=k, b_add=-k, b_min=100)


def _f_yellow_vintage(img):
    """复古黄: clamp (227,174,118) (原复古版 apply_yellow_filter)"""
    return _channel_fx(img, r_add=0.3, g_add=0.3, b_add=-0.3, r_max=227, g_max=174, b_min=118)


def _f_teal_vintage(img):
    """复古深墨绿: r>=36, g<=56, b<=23 (原 apply_custom_teal_filter 0.6/0.8/0.6)"""
    return _channel_fx(img, r_add=-0.6, g_add=0.8, b_add=0.6, r_min=36, g_max=56, b_max=23)


def _f_pink(img, k=0.3):
    """粉色滤镜(酷帅): g 压到 min 100 (原 apply_pink_filter)"""
    return _channel_fx(img, r_add=k, g_add=-k, b_add=k, g_min=100)


def _f_orange(img, k=0.3):
    """橙色滤镜(搞怪): b 压到 min 50 (原 apply_orange_filter)"""
    return _channel_fx(img, r_add=k, g_add=-k, b_add=-k, b_min=50)


def _f_purple(img, k=0.5):
    """紫色滤镜(搞怪): 减红绿、增益蓝 (原 apply_purple_filter)"""
    return _channel_fx(img, r_add=-k, g_add=-k, b_add=k)


FILTERS = {
    "vivid": _f_vivid, "vintage": _f_vintage, "weird": _f_weird, "cyber": _f_cyber,
    "teal": _f_teal, "yellow": _f_yellow, "yellow_vintage": _f_yellow_vintage,
    "teal_vintage": _f_teal_vintage, "pink": _f_pink, "orange": _f_orange, "purple": _f_purple,
}

# 色边偏移: 完全恢复原版参数。缩放链精密计算——抠图 512 高 → Effect 562 高 → 排布放大
# 680/562=1.21×, 视觉色边 = 偏移×1.21 (原版 1.0x → 本体↔紫层视觉 ≈48px 单轴)。
# 滤镜层已 duotone 化(内容不可辨), 偏移只控制色带几何宽度, 无需再收窄。
PORTRAIT_FX = {
    "可爱": [("yellow", (10, -20)), ("teal", (-10, 0)), ("vivid", (-30, 20))],
    "复古": [("yellow_vintage", (10, -20)), ("teal_vintage", (-10, 0)), ("vintage", (-30, 20))],
    "搞怪": [("purple", (10, -20)), ("orange", (-10, 0)), ("weird", (-30, 20))],
    "酷帅": [("pink", (0, 20)), ("teal", (-60, 20)), ("cyber", (-30, 20))],
}


# ---------------------------------------------------- 剪纸白边与手工抖动
def _white_key(img, thresh=242):
    """白底色键: 接近白色的像素转透明(带 32 级平滑过渡)。
    白底扁平插画素材(riso 贴纸)用它比 rembg 干净——rembg 为照片设计,
    会把大色块插画的浅色花瓣/留白半透明化。人像仍走 rembg。"""
    arr = np.array(img.convert("RGBA"))
    mn = arr[..., :3].min(axis=-1).astype("int16")
    alpha = np.clip((thresh - mn) * 8, 0, 255).astype("uint8")
    arr[..., 3] = alpha
    return Image.fromarray(arr, "RGBA")


def _duotone(img, dark, light, levels=5):
    """双色调版画映射 (对齐原版 effect 中间产物观感): 灰度压到 levels 级后,
    沿 dark↔light 色轴映射——整层坍缩为「暗部一色 + 亮部一色」的单色调版画,
    看上去只有颜色没有人像细节 (替换原 posterize 硬色块方案, 质地柔软如丝网印刷)。
    """
    g = img.convert("L")
    step = 256 // levels
    g = g.point(lambda p: p // step * step)
    return Image.merge("RGBA", (*ImageOps.colorize(g, black=dark, white=light).split(),
                                img.split()[3]))


# 滤镜层 duotone 暗部/亮部锚点 (取自原版 effect 中间产物取色)
DUOTONE = {
    "teal": ((20, 60, 70), (190, 225, 230)),
    "teal_vintage": ((36, 56, 35), (80, 110, 70)),
    "yellow": ((200, 160, 70), (250, 235, 180)),
    "yellow_vintage": ((150, 110, 50), (235, 215, 160)),
    "pink": ((170, 60, 50), (250, 215, 190)),
    "purple": ((55, 30, 85), (205, 180, 225)),
    "orange": ((170, 85, 25), (250, 205, 130)),
}


def _sticker_border(img, width=4):
    """剪纸白边: 画布外扩 pad, alpha 膨胀 width px 填白——拼贴「剪纸贴上去」的核心观感。
    用于人像本体层与 E2-E4 抠图贴纸; E1 矩形拼贴块不加(原版以白缝分隔)。
    """
    pad = width + 2
    canvas = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
    canvas.paste(img, (pad, pad), img)
    big = canvas.split()[3].filter(ImageFilter.MaxFilter(width * 2 + 1))
    white = Image.new("RGBA", canvas.size, (255, 255, 255, 255))
    white.paste(canvas, (0, 0), canvas)
    white.putalpha(big)
    return white


def _jitter(img, angle=3.0, shift=15, enabled=True):
    """手工拼贴感: ±angle° 微旋转 + ±shiftpx 位置抖动 (每张随机, --no-jitter 关闭)"""
    if not enabled:
        return img, (0, 0)
    a = random.uniform(-angle, angle)
    out = img.rotate(a, expand=True, resample=Image.BICUBIC) if abs(a) > 0.3 else img
    return out, (random.randint(-shift, shift), random.randint(-shift, shift))


# ---------------------------------------------------- 印刷化后处理(补偿链)
def _posterize(img, levels=4):
    """色阶分离: 皮肤自然过渡 -> 色块拼图 (对齐原版汇总图要素①)"""
    rgb = img.convert("RGB")
    q = ImageOps.posterize(rgb, levels)
    return Image.merge("RGBA", (*q.split(), img.split()[3]))


def _halftone(img, cell=3, strength=0.3):
    """半调网点 (对齐原版汇总图要素②): 灰度按 cell 网格采样,
    每格画直径与亮度成正比的圆点, 与原图按 strength 混合。
    cell=3 在 512 基准上点径细腻, cell 越大颗粒越粗。
    """
    g = img.convert("L")
    w, h = g.size
    grid = g.resize((max(1, w // cell), max(1, h // cell)))
    out = Image.new("L", (w, h), 255)
    dr = ImageDraw.Draw(out)
    px = grid.load()
    for gy in range(grid.height):
        for gx in range(grid.width):
            r = (255 - px[gx, gy]) / 255 * (cell / 2)
            if r > 0.3:
                cx, cy = gx * cell + cell / 2, gy * cell + cell / 2
                dr.ellipse([cx - r, cy - r, cx + r, cy + r], fill=0)
    dots = Image.merge("RGB", (out, out, out))
    blended = Image.blend(img.convert("RGB"), dots, strength)
    return Image.merge("RGBA", (*blended.split(), img.split()[3]))


# 印刷化后处理强度按风格分派 (对齐原版滤镜噪声行为):
# 复古滤镜自带 add_noise(std20) -> 全量网点+重颗粒; 其余三套滤镜无噪声 -> 轻网点+轻颗粒,
# 保住生图端「美型插画」的干净质感 (原版 SD 输出即干净插画, 颗粒主要来自滤镜层)。
PRINT_FX = {
    "可爱": dict(posterize=4, halftone=(3, 0.1), grain=12),
    "复古": dict(posterize=4, halftone=(3, 0.3), grain=20),
    "搞怪": dict(posterize=4, halftone=(3, 0.1), grain=12),
    "酷帅": dict(posterize=4, halftone=(3, 0.1), grain=12),
}


def make_portrait_effect(cutout_path, output_path, style="可爱", brightness=0.67):
    """签名效果: 按风格应用原作业滤镜组合+偏移, 三层套色错位叠印。
    brightness: 搞怪 weird 底层亮度(原版 0.67), 偏暗照片可提到 0.8-0.9。
    叠印后印刷化后处理链(按风格分派): posterize(色阶压缩) -> halftone(网点) -> grain(颗粒)。
    生图端为「美型插画」干净底子(对齐原 SD denoising 0.5 重绘的理想化输出),
    颗粒/网点只做轻量补偿, 不再四风格一刀切埋掉插画质感。
    """
    src = Image.open(cutout_path).convert("RGBA")
    # 原版人像基准: SD 输出固定 512x512, 偏移在此尺度施加后放大进画布(视觉偏移≈参数x1.31)。
    # 不归一化的话, 高分辨率原图上的 30px 偏移会被 compose 缩小到不足一半, 错位感消失。
    scale = 512 / src.height
    if scale < 1:
        src = src.resize((max(1, int(src.width * scale)), 512))
    layers = PORTRAIT_FX.get(style, PORTRAIT_FX["可爱"])
    base = Image.new("RGBA", (src.width + 50, src.height + 50))
    for idx, (name, (dx, dy)) in enumerate(layers):
        if name == "weird":
            layer = _f_weird(src, brightness=brightness)
        else:
            layer = FILTERS[name](src)
        if idx == len(layers) - 1:
            # 本体层加剪纸白边: 白边紧贴本体轮廓, 色边层在白边外露出(剪纸+套印层次)
            layer = _sticker_border(layer, width=4)
        if idx < len(layers) - 1:
            # 滤镜层 duotone 双色调映射: 整层坍缩为「暗部一色+亮部一色」的单色调版画,
            # 看上去只有颜色没有人像细节 (对齐原版 effect 中间产物质地, 替换 posterize 硬色块)
            layer = _duotone(layer, *DUOTONE[name])
        base.paste(layer, (dx, dy), layer)
    fx = PRINT_FX.get(style, PRINT_FX["可爱"])
    base = _posterize(base, levels=fx["posterize"])
    ht_cell, ht_strength = fx["halftone"]
    base = _halftone(base, cell=ht_cell, strength=ht_strength)
    base = _grain(base, strength=fx["grain"])
    base.save(output_path)
    return output_path


# ------------------------------------------------------------------ 排布合成
def _paste(canvas, path, size, center, square_resize=True):
    if not os.path.exists(path):
        print(f"[warn] 缺少素材 {path}, 已跳过该层")
        return
    img = Image.open(path).convert("RGBA")
    if square_resize:
        img = img.resize((size, size))
    else:
        img = img.resize(size)
    x = center[0] - img.width // 2
    y = center[1] - img.height // 2
    canvas.paste(img, (x, y), img)


def compose(style, element_paths, portrait_effect, out_path, jitter=True):
    """拼贴合成 (原作业布局 + 拼贴增强):
    底图 → E1 背景块 → E3/E4 道具 → 人像(白边) → E2 前景穿插(压肩) →
    向日葵/相机照片固定锚点 → 边框 → logo
    E1-E4 与人像带 ±3° 微旋转和 ±15px 位置抖动(手工拼贴感, --no-jitter 关闭)
    """
    canvas = Image.new("RGBA", (CANVAS, CANVAS), (255, 255, 255, 0))
    base = os.path.join(BASE_DIR, STYLE_FILE[style])

    def _paste_j(path, size, center, square=True, angle=3, shift=15):
        if isinstance(path, Image.Image):
            img = path.convert("RGBA")
        elif os.path.exists(path):
            img = Image.open(path).convert("RGBA")
        else:
            print(f"[warn] 缺少素材 {path}, 已跳过该层")
            return
        img = img.resize((size, size) if square else size)
        img, (sx, sy) = _jitter(img, angle, shift, jitter)
        canvas.paste(img, (center[0] - img.width // 2 + sx,
                           center[1] - img.height // 2 + sy), img)

    def _sticker(path):
        """固定锚点素材: 白底图 -> 白色色键 + 剪纸白边 (结果缓存 *_cut.png, 只处理一次)"""
        cut = path.replace(".png", "_cut.png")
        if not os.path.exists(cut):
            _white_key(Image.open(path).convert("RGBA")).save(cut)
        return _sticker_border(Image.open(cut), width=4)

    _paste(canvas, base, 800, (400, 400))                    # L1 底图
    # 版式坐标对齐 pytorch2 可爱排布.py 原版:
    # E1 380@(500,210) / E3 260@(130,350) / E4 300@(650,330) + E4 复用 260@(140,640) / E2 400@(600,600) 前景
    els = (element_paths + [None] * 4)[:4]
    if els[0]: _paste_j(els[0], 380, (500, 210))             # L2 E1 背景主块 380 右上
    if els[2]: _paste_j(els[2], 260, (130, 350))             # L3 E3 道具 260 左中
    if els[3]:
        _paste_j(els[3], 300, (650, 330))                    # L4 E4 道具 300 右中
        _paste_j(els[3], 260, (140, 640))                    # L4b E4 同素材复用 260 左下(原版彩蛋手法)
    if portrait_effect and os.path.exists(portrait_effect):
        pe = Image.open(portrait_effect).convert("RGBA")
        # 人像缩放回到 v28 比例: 高 680 等比缩放(不强制宽撑满, 避免大头特写),
        # 中心 x=280 偏左, 底边出画 50px(头顶≈y170)
        scale = 680 / pe.height
        pe = pe.resize((int(pe.width * scale), 680))
        pe, (sx, sy) = _jitter(pe, 2, 10, jitter)
        x = 280 - pe.width // 2 + sx
        y = 850 - pe.height + sy
        canvas.paste(pe, (x, y), pe)  # L5 人像
    if els[1]: _paste_j(els[1], 400, (600, 600), angle=2, shift=10)  # L6 E2 前景穿插 400 右下(人像之上)
    sun = _sticker(SUNFLOWER_PATH).resize((150, 150))    # L7 固定锚点: 右下向日葵
    canvas.paste(sun, (625, 625), sun)
    cam = _sticker(CAMERA_PHOTO_PATH).resize((170, 170))  # L8 固定锚点: 左上相机小照片
    canvas.paste(cam, (10, 10), cam)
    _paste(canvas, FRAME_PATH, 800, (400, 400))              # L9 渐变边框
    _paste(canvas, LOGO_PATH, (250, 125), (670, 70), square_resize=False)  # L10 logo

    canvas.save(out_path)
    print(f"[done] 海报已保存: {out_path}")
    return out_path


# ---------------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser(description="ZOOM IN! 认知拼贴海报生成器")
    ap.add_argument("--style", required=True, metavar="可爱|复古|搞怪|酷帅",
                    help="底图风格(也接受 cute/retro/funny/cool)")
    ap.add_argument("--portrait", required=True, help="正面人像照片路径")
    ap.add_argument("--elements", nargs=4, required=True,
                    help="四个元素素材图路径 E1-E4")
    ap.add_argument("--out", default="poster.png", help="输出路径")
    ap.add_argument("--workdir", default=None, help="中间文件目录")
    ap.add_argument("--stylize", choices=["none", "oil"], default="none",
                    help="人像风格化: oil=油画质感(替代原本地SD), none=保持原照片")
    ap.add_argument("--no-cutout-portrait", action="store_true",
                    help="人像已带透明背景时跳过抠图")
    ap.add_argument("--no-cutout-elements", action="store_true",
                    help="关闭 E2-E4 元素自动抠图(默认对贴纸类元素抠图, E1 背景块始终直贴)")
    ap.add_argument("--brightness", type=float, default=0.67,
                    help="搞怪 weird 底层亮度(原版 0.67); 深色衣服/偏暗照片实测 0.8 合适, 勿超 0.85")
    ap.add_argument("--no-jitter", action="store_true",
                    help="关闭元素/人像的微旋转与位置抖动(默认开启, 手工拼贴感)")
    args = ap.parse_args()
    args.style = STYLE_ALIAS.get(args.style, args.style)
    if args.style not in STYLE_FILE:
        ap.error(f"--style 无效: {args.style} (可选 可爱/复古/搞怪/酷帅)")

    workdir = args.workdir or os.path.dirname(os.path.abspath(args.out))
    os.makedirs(workdir, exist_ok=True)

    # Step 1 人像: 风格化 → 抠图 → 错位滤镜
    src = args.portrait
    if args.stylize == "oil":
        src = stylize_oil(src, os.path.join(workdir, "portrait_oil.png"))
    if args.no_cutout_portrait:
        cut = src
    else:
        cut = os.path.join(workdir, "portrait_cutout.png")
        cutout_image(src, cut, model="u2net_human_seg")
    effect = os.path.join(workdir, "portrait_effect.png")
    make_portrait_effect(cut, effect, style=args.style, brightness=args.brightness)

    # Step 2 元素: E1 背景块矩形直贴(原版拼贴块设计), E2-E4 贴纸类默认抠图+剪纸白边
    els = []
    for i, p in enumerate(args.elements, 1):
        if i >= 2 and not args.no_cutout_elements:
            dst = os.path.join(workdir, f"element_{i}_cut.png")
            els.append(_sticker_border(Image.open(cutout_image(p, dst)), width=4))
        else:
            els.append(p)

    # Step 3 排布合成
    compose(args.style, els, effect, args.out, jitter=not args.no_jitter)


if __name__ == "__main__":
    sys.exit(main())
