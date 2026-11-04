"""Procedural 1980s Tokyo night-city visuals + VHS post-processing."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

JP_FONT = "/usr/share/fonts/opentype/ipafont-gothic/ipagp.ttf"
EN_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
MONO_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf"

THEMES = {
    "sunset": dict(sky=[(0.0, (22, 8, 58)), (0.45, (98, 24, 112)), (0.75, (232, 70, 120)), (1.0, (255, 168, 96))],
                   sun=True, sun_top=(255, 236, 130), sun_bot=(255, 54, 140), stars=40,
                   bld=[(70, 30, 95), (40, 16, 66), (18, 8, 36)], water=(40, 10, 70)),
    "midnight": dict(sky=[(0.0, (3, 3, 18)), (0.5, (16, 12, 58)), (0.85, (70, 26, 110)), (1.0, (150, 50, 140))],
                     sun=False, moon=True, stars=260,
                     bld=[(38, 26, 80), (22, 14, 52), (10, 6, 28)], water=(10, 8, 40)),
    "magic_hour": dict(sky=[(0.0, (12, 30, 90)), (0.5, (70, 80, 170)), (0.8, (240, 120, 160)), (1.0, (255, 200, 140))],
                       sun=True, sun_top=(255, 250, 200), sun_bot=(255, 120, 120), stars=15,
                       bld=[(80, 60, 130), (45, 30, 90), (20, 12, 45)], water=(30, 30, 90)),
    "neon_rain": dict(sky=[(0.0, (2, 10, 22)), (0.5, (10, 40, 70)), (0.85, (60, 30, 100)), (1.0, (200, 40, 140))],
                      sun=False, moon=False, stars=0, rain=True,
                      bld=[(30, 40, 80), (16, 22, 52), (6, 10, 26)], water=(5, 15, 35)),
}
WINDOW_COLS = [(255, 214, 120), (255, 190, 90), (255, 240, 200), (120, 230, 255), (255, 120, 200)]


def gradient(h, w, stops):
    ys = np.linspace(0, 1, h)
    pos = [s[0] for s in stops]
    cols = np.array([s[1] for s in stops], np.float32)
    g = np.stack([np.interp(ys, pos, cols[:, c]) for c in range(3)], -1)
    return np.repeat(g[:, None, :], w, 1).astype(np.float32)


def blur(arr, radius):
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return np.asarray(img.filter(ImageFilter.GaussianBlur(radius)), np.float32)


class Scene:
    def __init__(self, W, H, fps, seed, theme, title_jp, title_en, artist, duration):
        self.W, self.H, self.fps = W, H, fps
        self.rng = np.random.default_rng(seed + 1000)
        self.theme_name = theme
        self.th = THEMES[theme]
        self.duration = duration
        self.horizon = int(H * 0.66)
        self.s = H / 720.0  # scale factor
        self.title = (title_jp, title_en, artist)
        self._build()

    # ------------------------------------------------------------------ build
    def _build(self):
        W, H, hz, s, r = self.W, self.H, self.horizon, self.s, self.rng
        self.sky = gradient(hz, W, self.th["sky"])
        # stars
        n = self.th.get("stars", 0)
        self.stars = np.stack([r.integers(0, W, n), r.integers(0, int(hz * 0.6), n),
                               r.uniform(0, 6.28, n), r.uniform(0.5, 3, n)], 1) if n else None
        # sun
        self.sun_r = int(H * 0.21)
        self.sun_c = (W // 2, hz - int(self.sun_r * 1.15))
        yy, xx = np.mgrid[0:H, 0:W]
        d = np.sqrt((xx - self.sun_c[0]) ** 2 + (yy - self.sun_c[1]) ** 2).astype(np.float32)
        self.glow = np.exp(-(d / (self.sun_r * 1.6)) ** 2)[:hz, :, None]
        if self.th.get("sun"):
            mask = np.clip(self.sun_r - d + 1, 0, 1)[:hz]
            f = np.clip((yy[:hz] - (self.sun_c[1] - self.sun_r)) / (2 * self.sun_r), 0, 1)[..., None]
            col = (1 - f) * np.array(self.th["sun_top"], np.float32) + f * np.array(self.th["sun_bot"], np.float32)
            self.sun_mask, self.sun_col = mask, col
            self.sun_rel_y = (yy[:hz, 0] - self.sun_c[1]) / self.sun_r  # -1..1
        elif self.th.get("moon"):
            mc = (int(W * 0.78), int(hz * 0.28)); mr = int(H * 0.06)
            dm = np.sqrt((xx[:hz] - mc[0]) ** 2 + (yy[:hz] - mc[1]) ** 2)
            dm2 = np.sqrt((xx[:hz] - mc[0] - mr * 0.45) ** 2 + (yy[:hz] - mc[1] + mr * 0.2) ** 2)
            self.moon = (np.clip(mr - dm, 0, 1) * np.clip(dm2 - mr * 0.85, 0, 1))[..., None]
            self.moon_glow = np.exp(-(dm / (mr * 3)) ** 2)[..., None]
        # skyline layers (far -> near)
        cols = self.th["bld"]
        self.layers = []
        specs = [(0.24, 0.08, 0.6, 6), (0.30, 0.10, 0.8, 16), (0.17, 0.06, 1.0, 34)]
        for i, (hmax, hmin, lit, speed) in enumerate(specs):
            self.layers.append(self._skyline(int(W * 2), int(H * hmax), int(H * hmin), cols[i], lit,
                                             speed * s, tower=(i == 1), far=(i == 0)))
        # vignette, scanlines, grain
        vx = (xx / W - 0.5) * 2; vy = (yy / H - 0.5) * 2
        self.vignette = (1 - 0.35 * np.clip(vx ** 2 * 0.6 + vy ** 2 * 0.8, 0, 1) ** 1.5)[..., None].astype(np.float32)
        period = max(2, int(round(3 * s)))
        self.scan = (1 - 0.13 * ((np.arange(H) % period) == 0))[:, None, None].astype(np.float32)
        self.grain = [r.normal(0, 5, (H, W, 1)).astype(np.float32) for _ in range(6)]
        # bokeh particles
        k = 28
        self.bokeh = np.stack([r.uniform(0, W, k), r.uniform(hz * 0.9, H, k), r.uniform(4, 14, k) * s,
                               r.uniform(-12, -4, k) * s, r.integers(0, len(WINDOW_COLS), k)], 1)
        if self.th.get("rain"):
            self.rain = np.stack([r.uniform(0, W, 500), r.uniform(0, H, 500), r.uniform(0.6, 1.0, 500)], 1)
        self._build_text()
        self._osd_cache = {}

    def _skyline(self, L, hmax, hmin, color, lit, speed, tower=False, far=False):
        r, s = self.rng, self.s
        hz = self.horizon
        img = Image.new("RGBA", (L, hmax + int(60 * s) + (int(self.H * 0.45) if tower else 0)), (0, 0, 0, 0))
        Ht = img.size[1]
        dr = ImageDraw.Draw(img)
        lights = []
        x = 0
        while x < L:
            bw = int(r.uniform(30, 110) * s)
            bh = int(r.uniform(hmin, hmax))
            if r.random() < 0.15:
                bh = int(bh * 1.35)
            bw = min(bw, L - x)
            top = Ht - bh
            c = tuple(int(v * r.uniform(0.85, 1.15)) for v in color)
            dr.rectangle([x, top, x + bw - 1, Ht], fill=c + (255,))
            if r.random() < 0.3:  # stepped roof
                iw = int(bw * r.uniform(0.4, 0.7)); ih = int(r.uniform(8, 30) * s)
                ox = x + (bw - iw) // 2
                dr.rectangle([ox, top - ih, ox + iw, top], fill=c + (255,))
            if r.random() < 0.35:  # antenna + aviation light
                ax = x + bw // 2; ah = int(r.uniform(10, 40) * s)
                dr.line([ax, top - ah, ax, top], fill=c + (255,), width=max(1, int(2 * s)))
                lights.append((ax, top - ah, r.uniform(0, 6.28)))
            # windows
            if not far or r.random() < 0.6:
                wx, wy = max(2, int(4 * s)), max(2, int(3 * s))
                gx, gy = max(3, int(r.choice([6, 8, 10]) * s)), max(4, int(r.choice([7, 9]) * s))
                pal = WINDOW_COLS[:3] if r.random() < 0.8 else WINDOW_COLS
                density = r.uniform(0.15, 0.55) * lit
                for yy in range(top + gy, Ht - gy, gy):
                    row_on = r.random() < 0.85
                    for xx in range(x + gx // 2, x + bw - wx, gx):
                        if row_on and r.random() < density:
                            wc = pal[r.integers(len(pal))]
                            a = int(255 * (0.5 if far else 1.0))
                            dr.rectangle([xx, yy, xx + wx - 1, yy + wy - 1], fill=wc + (a,))
            # neon signboard
            if not far and r.random() < 0.12 and bh > hmin * 1.2:
                nc = [(255, 60, 180), (60, 230, 255), (255, 90, 60)][r.integers(3)]
                sy = top + int(bh * 0.2); sx = x + int(bw * 0.15)
                dr.rectangle([sx, sy, sx + int(bw * 0.12) + 3, sy + int(bh * 0.35)], fill=nc + (255,))
            x += bw + int(r.uniform(0, 6) * s)
        if tower:
            self._tokyo_tower(dr, int(L * r.uniform(0.25, 0.4)), Ht, int(self.H * 0.5), lights)
        arr = np.asarray(img, np.float32)
        rgb, a = arr[..., :3], arr[..., 3:] / 255.0
        bright = rgb.max(-1, keepdims=True)
        glowsrc = rgb * (bright > max(color) + 40)
        glow = blur(glowsrc, 5 * s) * 0.9
        return dict(rgb=rgb, a=a, glow=glow, L=L, h=Ht, speed=speed, lights=lights,
                    y0=hz - Ht + int(4 * s))

    def _tokyo_tower(self, dr, cx, base_y, h, lights):
        s = self.s
        top = base_y - h
        orange, white = (255, 110, 40, 255), (255, 235, 210, 255)
        bw = int(h * 0.28)
        lw = max(1, int(2 * s))

        def half_w(y):  # flared lattice profile
            f = (base_y - y) / h
            return max(1.5 * s, bw / 2 * (1 - f) ** 2.2)

        # legs + cross bracing
        prev = None
        for i in range(0, 41):
            y = base_y - h * (i / 40) ** 1.0
            hw = half_w(y)
            if prev:
                py, phw = prev
                dr.line([cx - phw, py, cx - hw, y], fill=orange, width=lw)
                dr.line([cx + phw, py, cx + hw, y], fill=orange, width=lw)
                if i < 34:
                    dr.line([cx - phw, py, cx + hw, y], fill=orange, width=max(1, lw // 2 + 1))
                    dr.line([cx + phw, py, cx - hw, y], fill=orange, width=max(1, lw // 2 + 1))
            prev = (y, hw)
        # observation decks
        for f, dh in ((0.38, 0.04), (0.68, 0.022)):
            y = base_y - h * f
            hw = half_w(y) + 6 * s
            dr.rectangle([cx - hw, y - h * dh, cx + hw, y], fill=(255, 150, 70, 255))
            dr.rectangle([cx - hw + 2 * s, y - h * dh * 0.7, cx + hw - 2 * s, y - h * dh * 0.3],
                         fill=white)
        # base arch
        dr.arc([cx - bw / 2.3, base_y - h * 0.09, cx + bw / 2.3, base_y + h * 0.07], 180, 360,
               fill=orange, width=lw * 2)
        lights.append((cx, top, 0.0))

    def _build_text(self):
        W, H, s = self.W, self.H, self.s
        jp, en, artist = self.title
        layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(layer)
        f_jp = ImageFont.truetype(JP_FONT, int(78 * s))
        f_en = ImageFont.truetype(EN_FONT, int(26 * s))
        f_ar = ImageFont.truetype(JP_FONT, int(30 * s))
        cy = int(H * getattr(self, "title_y", 0.08))
        for txt, font, y, col in ((jp, f_jp, cy, (255, 240, 250)),
                                  (" ".join(en.upper()), f_en, cy + int(95 * s), (140, 240, 255)),
                                  (artist, f_ar, cy + int(140 * s), (255, 200, 120))):
            w = dr.textlength(txt, font=font)
            dr.text(((W - w) / 2 + 4 * s, y + 4 * s), txt, font=font, fill=(255, 40, 160, 200))
            dr.text(((W - w) / 2, y), txt, font=font, fill=col + (255,))
        arr = np.asarray(layer, np.float32)
        self.text_rgb = arr[..., :3]
        self.text_a = arr[..., 3:] / 255
        pink = np.zeros_like(self.text_rgb); pink[...] = (255, 60, 190)
        self.text_glow = blur(pink * self.text_a, 10 * s) * 1.4
        # small corner credit
        small = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(small)
        fs = ImageFont.truetype(JP_FONT, int(22 * s))
        pos = (int(28 * s), H - int(52 * s))
        d2.text((pos[0] + 2, pos[1] + 2), f"♪ {jp} / {artist}", font=fs, fill=(10, 0, 20, 200))
        d2.text(pos, f"♪ {jp} / {artist}", font=fs, fill=(255, 235, 245, 240))
        a2 = np.asarray(small, np.float32)
        self.credit_rgb, self.credit_a = a2[..., :3], a2[..., 3:] / 255

    def _osd(self, t):
        sec = int(t)
        if sec in self._osd_cache:
            return self._osd_cache[sec]
        W, H, s = self.W, self.H, self.s
        img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        f = ImageFont.truetype(MONO_FONT, int(30 * s))
        fsm = ImageFont.truetype(MONO_FONT, int(24 * s))
        if sec < 6 and sec % 2 == 0:
            dr.text((int(40 * s), int(34 * s)), "PLAY ▶", font=f, fill=(255, 255, 255, 235))
        if sec < 6:
            dr.text((W - int(170 * s), int(34 * s)), "SP  Hi-Fi", font=fsm, fill=(255, 255, 255, 200))
        hh, mm = 23 + (sec // 3600), (12 + sec // 60) % 60
        dr.text((W - int(300 * s), H - int(70 * s)), f"PM {hh - 12:2d}:{mm:02d}:{sec % 60:02d}",
                font=fsm, fill=(255, 255, 255, 220))
        dr.text((W - int(300 * s), H - int(40 * s)), "AUG. 21 1985", font=fsm, fill=(255, 255, 255, 220))
        arr = np.asarray(img, np.float32)
        out = (arr[..., :3], arr[..., 3:] / 255)
        self._osd_cache = {sec: out}
        return out

    # ------------------------------------------------------------------ frame
    def frame(self, t, energy=0.0, onset=0.0, bands=None):
        W, H, hz, s = self.W, self.H, self.horizon, self.s
        img = np.empty((H, W, 3), np.float32)
        top = self.sky.copy()
        # stars
        if self.stars is not None:
            st = self.stars
            tw = 0.5 + 0.5 * np.sin(st[:, 2] + t * st[:, 3])
            top[st[:, 1].astype(int), st[:, 0].astype(int)] += (tw * 200)[:, None]
        # sun / moon + glow
        g = 0.55 + 0.6 * energy
        if self.th.get("sun"):
            top += self.glow * np.array(self.th["sun_bot"], np.float32) * 0.45 * g
            ry = self.sun_rel_y
            phase = (t * 0.08) % 1
            stripes = np.ones_like(ry)
            lower = ry > -0.1
            k = ((ry + 0.1) * 6 + phase) % 1
            gap = 0.08 + 0.45 * np.clip(ry + 0.1, 0, 1)
            stripes[lower & (k < gap)] = 0
            m = self.sun_mask * stripes[:, None]
            top = top * (1 - m[..., None]) + self.sun_col * m[..., None]
        elif self.th.get("moon"):
            top += self.moon_glow * np.array([120, 110, 200], np.float32) * 0.5
            top = top * (1 - self.moon) + np.array([255, 245, 220], np.float32) * self.moon
        else:
            top += self.glow * np.array([200, 40, 150], np.float32) * 0.3 * g
        # skyline layers with parallax
        for li, L in enumerate(self.layers):
            off = int(t * L["speed"]) % L["L"]
            cols = (np.arange(W) + off) % L["L"]
            y0 = L["y0"]
            ys = max(0, y0)
            sl = slice(ys - y0, hz - y0)
            rgb, a, gl = L["rgb"][sl][:, cols], L["a"][sl][:, cols], L["glow"][sl][:, cols]
            reg = top[ys:hz]
            reg[:] = reg * (1 - a) + rgb * a + gl * (0.7 + 0.5 * energy)
            # haze between layers
            if li == 0:
                top[ys:hz] += 18 * np.linspace(0, 1, hz - ys)[:, None, None]
            for (lx, ly, ph) in L["lights"]:
                x = int((lx - off) % L["L"])
                if x >= W - 4 or x < 4:
                    continue
                y = int(ly + y0)
                if 3 <= y < hz - 3 and np.sin(t * 3 + ph) > 0.2:
                    rr = max(2, int(3 * s))
                    top[y - rr:y + rr, x - rr:x + rr] = (255, 50, 50)
        img[:hz] = top
        # water reflection with ripples
        wh = H - hz
        yy = np.arange(wh)
        depth = yy / wh
        src = np.clip(hz - 1 - (yy * 0.9).astype(int), 0, hz - 1)
        dx = (np.sin(yy * 0.18 / s - t * 2.4) * (1 + 7 * depth) * s
              + np.sin(yy * 0.045 / s + t * 1.1) * 3 * s).astype(int)
        cols = (np.arange(W)[None, :] + dx[:, None]) % W
        st = max(1, int(3 * s))  # vertical smear like real water
        refl = (top[src[:, None], cols] + top[np.clip(src - st, 0, hz - 1)[:, None], cols]
                + top[np.clip(src - 2 * st, 0, hz - 1)[:, None], cols]) / 3
        water = np.array(self.th["water"], np.float32)
        fade = (0.62 - 0.35 * depth)[:, None, None]
        img[hz:] = refl * fade + water * (1 - fade)
        img[hz:hz + max(1, int(2 * s))] += 40  # shoreline glint
        # bokeh
        for bx, by, br, vy, ci in self.bokeh:
            y = int((by + vy * t - hz) % (H - hz) + hz)
            x = int(bx + 20 * s * np.sin(t * 0.5 + by))
            rr = int(br)
            y1, y2, x1, x2 = max(0, y - rr), min(H, y + rr), max(0, x - rr), min(W, x + rr)
            if y2 > y1 and x2 > x1:
                img[y1:y2, x1:x2] += np.array(WINDOW_COLS[int(ci)], np.float32) * 0.12
        # rain
        if self.th.get("rain"):
            R = self.rain
            ys = ((R[:, 1] + t * 900 * s * R[:, 2]) % H).astype(int)
            xs = ((R[:, 0] - t * 120 * s) % W).astype(int)
            ln = int(18 * s)
            for k in range(ln):
                yk = np.clip(ys + k, 0, H - 1); xk = np.clip(xs - k // 5, 0, W - 1)
                img[yk, xk] += 38 * (1 - k / ln) + 12
        img = self.text_overlay(img, t, energy)
        return self.post(img, t, onset)

    def text_overlay(self, img, t, energy):
        """Title (fades in/out during the first seconds) then a small corner credit."""
        ta = np.clip((t - 1.0) / 1.2, 0, 1) * np.clip((9.0 - t) / 1.2, 0, 1)
        if ta > 0:
            img += self.text_glow * ta * (0.8 + 0.4 * energy)
            a = self.text_a * ta
            img = img * (1 - a) + self.text_rgb * a
        ca = np.clip((t - 9.5) / 1.5, 0, 1) * np.clip((self.duration - 1 - t) / 1.5, 0, 1)
        if ca > 0:
            a = self.credit_a * ca
            img = img * (1 - a) + self.credit_rgb * a
        return img

    def post(self, img, t, onset):
        W, H, s = self.W, self.H, self.s
        r = np.random.default_rng(int(t * self.fps) + 7)
        # bloom
        small = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).resize((W // 4, H // 4), Image.BILINEAR)
        small = small.filter(ImageFilter.GaussianBlur(4))
        bloom = np.asarray(small.resize((W, H), Image.BILINEAR), np.float32)
        img = img + np.clip(bloom - 90, 0, None) * 0.55
        # color grade: lifted blacks, warm highlights
        img = img * np.array([1.03, 0.96, 1.02], np.float32) + np.array([14, 6, 22], np.float32)
        # chromatic aberration
        sh = max(1, int(round(2 * s + 2 * onset)))
        img[..., 0] = np.roll(img[..., 0], sh, 1)
        img[..., 2] = np.roll(img[..., 2], -sh, 1)
        # VHS chroma bleed (horizontal smear)
        img = 0.75 * img + 0.25 * np.roll(img, int(3 * s), 1)
        # tracking glitch
        if (int(t * 2) * 7919) % 23 == 0 or onset > 0.95:
            y = int(r.uniform(0, H - 30 * s)); hgt = int(r.uniform(6, 26) * s)
            img[y:y + hgt] = np.roll(img[y:y + hgt], int(r.uniform(-25, 25) * s), 1) + 30
        # OSD + film/VHS texture
        orgb, oa = self._osd(t)
        img = img * (1 - oa) + orgb * oa
        img = img * self.scan * self.vignette + self.grain[(int(t * self.fps) // 2) % len(self.grain)]
        if r.random() < 0.03:
            img = np.roll(img, 1, 0)
        return np.clip(img, 0, 255).astype(np.uint8)
