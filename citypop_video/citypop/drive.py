"""Night drive through central Tokyo, seen from the back seat.

Japanese road rules are respected:
  * traffic keeps LEFT: our car drives in the left-hand carriageway, oncoming
    headlights pass on the right, the yellow centre line is to our right;
  * the car is right-hand drive: driver and steering wheel sit on the right,
    the empty passenger seat on the left, wipers are mirrored (RHD layout);
  * horizontal Japanese traffic lights, blue (general road) direction signs,
    Shuto Expressway overpasses, zebra crossings and vertical neon signboards.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from .visuals import EN_FONT, JP_FONT, MONO_FONT, Scene, gradient

TAU = 2 * np.pi
NEON = [(255, 60, 170), (60, 230, 255), (255, 140, 40), (120, 255, 140), (190, 90, 255),
        (255, 70, 70), (255, 230, 120)]
SIGN_TEXTS = ["カラオケ", "喫茶", "ホテル", "BAR", "居酒屋", "レコード", "ディスコ", "寿司", "ラーメン",
              "薬", "酒", "CLUB", "映画", "焼肉", "麻雀", "ゲーム", "ビデオ", "スナック", "質", "珈琲"]
ROAD_SIGNS = [("渋谷", "Shibuya", "新宿", "Shinjuku"), ("銀座", "Ginza", "六本木", "Roppongi"),
              ("赤坂", "Akasaka", "青山", "Aoyama"), ("東京駅", "Tokyo Sta.", "有楽町", "Yurakucho")]
WIN_COLS = [(255, 214, 140), (255, 196, 110), (205, 230, 255), (255, 240, 210)]

# Lane geometry in metres (+x = right). Japan keeps LEFT.
L_FACADE, L_EDGE, LANE_DIV, CENTER, ONC_DIV, R_EDGE, R_FACADE = -9.0, -5.25, -1.75, 1.75, 5.25, 8.75, 12.0
LZ = 840.0                       # world loop length
INTERSECTIONS = [110.0, 520.0]   # crossings (zebra + traffic light)
OVERPASSES = [300.0, 720.0]      # Shuto Expressway
GANTRIES = [190.0, 610.0]        # blue direction signs
LAMP_GAP = 34.0                  # street-light spacing


class DriveScene(Scene):
    title_y = 0.2

    # ------------------------------------------------------------------ build
    def _build(self):
        W, H, r = self.W, self.H, self.rng
        s = self.s
        self.f = W * 0.78
        self.cx = W / 2
        self.hy0 = H * 0.46
        self.cam_h = 1.25
        self.speed = 14.0  # m/s ~ 50 km/h
        self.znear, self.zfar = 2.0, 260.0
        self.horizon = int(self.hy0)
        th = self.th
        sky_bottom = np.array(th["sky"][-1][1], np.float32)
        self.fog = sky_bottom * 0.22 + 4
        self.bg = np.zeros((H, W, 3), np.float32)
        self.bg[: self.horizon] = gradient(self.horizon, W, th["sky"])
        g = np.linspace(0, 1, H - self.horizon)[:, None, None]
        self.bg[self.horizon:] = self.fog * (1 - g) + np.array([8, 8, 14], np.float32) * g
        self.far = self._skyline(int(W * 2), int(H * 0.15), int(H * 0.05), th["bld"][0], 0.5, 2 * s, far=True)
        self.stars = None

        # ---- world: buildings, windows, neon signs
        self.buildings, self.signs = [], []
        for side, xf in (("L", L_FACADE), ("R", R_FACADE)):
            z = 0.0
            while z < LZ:
                hit = [zi for zi in INTERSECTIONS if z + 30 > zi - 4 and z < zi + 16]
                if hit:
                    z = max(z, hit[0] + 16)
                w = r.uniform(8, 24)
                for zi in INTERSECTIONS:
                    if z < zi - 4 < z + w:
                        w = zi - 4 - z
                if w < 4:
                    z += w + 0.5
                    continue
                h = r.uniform(10, 46) * (1.35 if r.random() < 0.15 else 1.0)
                col = np.array(th["bld"][r.integers(0, 2)], np.float32) * r.uniform(0.75, 1.25)
                wins = []
                if r.random() < 0.6:  # lit shop front at street level
                    wins.append((0.3, w - 0.3, 0.3, 3.0, WIN_COLS[r.integers(4)], r.uniform(0.6, 1.0)))
                style = r.random()
                for fl in range(1, int(h / 3.4)):
                    y0 = fl * 3.4 + 0.6
                    if y0 + 1.6 > h:
                        break
                    if style < 0.45:
                        if r.random() < 0.5:
                            wins.append((0.4, w - 0.4, y0, y0 + 1.6, WIN_COLS[r.integers(4)], r.uniform(0.3, 0.8)))
                    else:
                        for j in range(int(w / 3)):
                            if r.random() < 0.3:
                                wins.append((j * 3 + 0.6, j * 3 + 2.2, y0, y0 + 1.6,
                                             WIN_COLS[r.integers(4)], r.uniform(0.5, 1.0)))
                self.buildings.append(dict(x=xf, out=-1 if side == "L" else 1, z1=z, w=w, h=h,
                                           col=col, wins=wins, beacon=h > 38))
                if r.random() < 0.75:
                    for _ in range(r.integers(1, 3)):
                        hm = r.uniform(3.5, 7.0)
                        self.signs.append(dict(side=side, z=z + r.uniform(0.8, max(1.0, w - 0.8)),
                                               y=r.uniform(3.2, 8.0), hm=hm, sprite=self._sign_sprite(
                                                   SIGN_TEXTS[r.integers(len(SIGN_TEXTS))],
                                                   NEON[r.integers(len(NEON))], hm)))
                z += w + r.uniform(0.5, 4.0)
        self.gantry_sprites = [self._road_sign_sprite(ROAD_SIGNS[i % len(ROAD_SIGNS)]) for i in range(len(GANTRIES))]
        self.shuto_sprite = self._shuto_sprite()
        # ---- traffic
        self.lead_col = np.array([40, 34, 52], np.float32)
        self.left_cars = [dict(z0=r.uniform(0, 230), v=-r.uniform(1.5, 4.0),
                               col=np.array(r.choice([[60, 20, 30], [30, 30, 40], [70, 70, 80], [20, 30, 60]]), np.float32))
                          for _ in range(4)]
        self.oncoming = [dict(x=3.5 if k % 2 else 7.0, z0=r.uniform(0, 260), v=-(self.speed + r.uniform(10, 16)))
                         for k in range(8)]
        # ---- cabin
        self._build_cabin()
        self._build_drops()
        # ---- shared VHS assets (same as the bay scene)
        yy, xx = np.mgrid[0:H, 0:W]
        vx = (xx / W - 0.5) * 2
        vy = (yy / H - 0.5) * 2
        self.vignette = (1 - 0.35 * np.clip(vx ** 2 * 0.6 + vy ** 2 * 0.8, 0, 1) ** 1.5)[..., None].astype(np.float32)
        period = max(2, int(round(3 * s)))
        self.scan = (1 - 0.13 * ((np.arange(H) % period) == 0))[:, None, None].astype(np.float32)
        self.grain = [r.normal(0, 5, (H, W, 1)).astype(np.float32) for _ in range(6)]
        self.rain = np.stack([r.uniform(0, W, 600), r.uniform(0, H, 600), r.uniform(0.6, 1.0, 600)], 1)
        self._build_text()
        self._osd_cache = {}
        self._lcd_font = ImageFont.truetype(MONO_FONT, max(8, int(15 * s)))
        self._lcd_jp = ImageFont.truetype(JP_FONT, max(8, int(12 * s)))

    def _fogged(self, sprite, levels=5):
        out = []
        arr = np.asarray(sprite, np.float32)
        for k in range(levels):
            a = k / levels * 0.85
            rgb = arr[..., :3] * (1 - a) + self.fog * a
            out.append(Image.fromarray(np.dstack([rgb, arr[..., 3]]).clip(0, 255).astype(np.uint8), "RGBA"))
        return out

    def _sign_sprite(self, text, col, hm):
        pw = 90
        ph = int(pw * hm / 1.2)
        img = Image.new("RGBA", (pw, ph), tuple(int(c * 0.18) + 8 for c in col) + (255,))
        d = ImageDraw.Draw(img)
        d.rectangle([2, 2, pw - 3, ph - 3], outline=col + (255,), width=5)
        chars = list(text)
        fs = int(min(pw * 0.66, (ph - 18) / len(chars) / 1.08))
        font = ImageFont.truetype(JP_FONT, max(10, fs))
        y = (ph - fs * 1.08 * len(chars)) / 2
        for ch in chars:
            w = d.textlength(ch, font=font)
            d.text(((pw - w) / 2, y), ch, font=font, fill=(255, 250, 245, 255), stroke_width=2, stroke_fill=col + (255,))
            y += fs * 1.08
        return dict(levels=self._fogged(img), col=col)

    def _road_sign_sprite(self, names):
        jp1, en1, jp2, en2 = names
        img = Image.new("RGBA", (420, 140), (10, 60, 150, 255))
        d = ImageDraw.Draw(img)
        d.rectangle([4, 4, 415, 135], outline=(235, 240, 250, 255), width=5)
        fj, fe = ImageFont.truetype(JP_FONT, 46), ImageFont.truetype(EN_FONT, 20)
        d.text((24, 22), f"↑ {jp1}", font=fj, fill=(245, 245, 250, 255))
        d.text((62, 84), en1, font=fe, fill=(245, 245, 250, 255))
        d.text((230, 22), f"{jp2} →", font=fj, fill=(245, 245, 250, 255))
        d.text((230, 84), en2, font=fe, fill=(245, 245, 250, 255))
        return self._fogged(img)

    def _shuto_sprite(self):
        img = Image.new("RGBA", (260, 70), (0, 110, 70, 255))
        d = ImageDraw.Draw(img)
        d.rectangle([3, 3, 256, 66], outline=(240, 245, 240, 255), width=3)
        d.text((16, 10), "首都高 C1  都心環状線", font=ImageFont.truetype(JP_FONT, 30), fill=(245, 250, 245, 255))
        return self._fogged(img)

    def _build_cabin(self):
        W, H, s = self.W, self.H, self.s
        dark, panel, edge = (9, 7, 14, 255), (13, 10, 19, 255), (34, 26, 44, 255)
        A = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(A)
        xs = np.linspace(0, W, 48)
        roof = [(0, 0), (W, 0)] + [(x, H * (0.075 + 0.03 * ((x / W - 0.5) * 2) ** 2)) for x in xs[::-1]]
        d.polygon(roof, fill=dark)
        d.polygon([(0, 0), (W * 0.12, 0), (W * 0.038, H * 0.72), (0, H * 0.75)], fill=dark)  # A-pillars
        d.polygon([(W, 0), (W * 0.88, 0), (W * 0.962, H * 0.72), (W, H * 0.75)], fill=dark)

        def dash_y(x):
            u = (x / W - 0.5) * 2
            hood = np.exp(-(((x / W) - 0.72) / 0.09) ** 2) * 0.035  # instrument hood on the RIGHT (RHD)
            return H * (0.69 + 0.02 * u * u - hood)
        top = [(x, dash_y(x)) for x in xs]
        d.polygon(top + [(W, H), (0, H)], fill=panel)
        d.line(top, fill=(72, 42, 92, 255), width=max(1, int(2 * s)))
        # vents + centre console with car stereo (cassette deck)
        for x0 in (0.335, 0.60):
            d.rounded_rectangle([W * x0, H * 0.735, W * (x0 + 0.065), H * 0.765], radius=int(4 * s), fill=(6, 5, 9, 255))
        self.stereo = (int(W * 0.425), int(H * 0.755), int(W * 0.575), int(H * 0.875))
        x0, y0, x1, y1 = self.stereo
        d.rounded_rectangle([x0, y0, x1, y1], radius=int(6 * s), fill=(22, 17, 28, 255), outline=edge, width=2)
        self.lcd = (int(W * 0.45), int(H * 0.768), int(W * 0.55), int(H * 0.842))
        d.rectangle(self.lcd, fill=(4, 18, 24, 255), outline=(30, 50, 60, 255))
        for kx in (0.437, 0.563):
            d.ellipse([W * kx - 9 * s, H * 0.80 - 9 * s, W * kx + 9 * s, H * 0.80 + 9 * s], fill=(40, 34, 48, 255))
        d.rectangle([W * 0.46, H * 0.853, W * 0.54, H * 0.862], fill=(3, 3, 5, 255))  # cassette slot
        d.text((W * 0.462, H * 0.84), "AUTO REVERSE  Dolby B", font=ImageFont.truetype(MONO_FONT, max(6, int(9 * s))),
               fill=(120, 110, 130, 255))
        # rear-view mirror
        d.line([(W * 0.5, H * 0.07), (W * 0.5, H * 0.1)], fill=dark, width=int(6 * s))
        self.mirror = (int(W * 0.418), int(H * 0.098), int(W * 0.582), int(H * 0.158))
        d.rounded_rectangle(self.mirror, radius=int(10 * s), fill=(14, 12, 20, 255), outline=edge, width=2)
        m = self.mirror
        d.rounded_rectangle([m[0] + 6 * s, m[1] + 5 * s, m[2] - 6 * s, m[3] - 5 * s], radius=int(7 * s), fill=(24, 20, 38, 255))
        # empty passenger seat (LEFT side in a Japanese car)
        seat = (16, 12, 21, 255)
        d.line([(W * 0.24, H * 0.69), (W * 0.24, H * 0.79)], fill=(40, 40, 46, 255), width=int(4 * s))
        d.line([(W * 0.28, H * 0.69), (W * 0.28, H * 0.79)], fill=(40, 40, 46, 255), width=int(4 * s))
        d.rounded_rectangle([W * 0.205, H * 0.60, W * 0.315, H * 0.70], radius=int(W * 0.028), fill=seat, outline=edge, width=2)
        d.rounded_rectangle([W * 0.14, H * 0.78, W * 0.38, H * 1.05], radius=int(W * 0.04), fill=seat, outline=edge, width=2)
        a = np.asarray(A, np.float32)
        self.cabA_rgb, self.cabA_a = a[..., :3], a[..., 3:] / 255

        # driver (RIGHT side) — long dark hair, black jacket, seen from behind
        D = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        d = ImageDraw.Draw(D)
        jacket, hair = (11, 9, 15, 255), (26, 16, 20, 255)
        d.polygon([(W * 0.615, H * 0.86), (W * 0.622, H * 0.70), (W * 0.65, H * 0.655), (W * 0.695, H * 0.635),
                   (W * 0.745, H * 0.635), (W * 0.79, H * 0.655), (W * 0.818, H * 0.70), (W * 0.825, H * 0.86)], fill=jacket)
        d.ellipse([W * 0.683, H * 0.40, W * 0.757, H * 0.565], fill=hair)
        d.polygon([(W * 0.685, H * 0.49), (W * 0.677, H * 0.57), (W * 0.668, H * 0.66), (W * 0.68, H * 0.735),
                   (W * 0.72, H * 0.75), (W * 0.76, H * 0.735), (W * 0.772, H * 0.66), (W * 0.763, H * 0.57),
                   (W * 0.755, H * 0.49)], fill=hair)
        for k in range(6):  # subtle strands
            x = W * (0.688 + 0.013 * k)
            d.line([(x, H * 0.44), (x - 3 * s + k * s, H * 0.58), (x - 6 * s + 2 * k * s, H * 0.73)],
                   fill=(44, 28, 34, 255), width=max(1, int(s)))
        drv = np.asarray(D, np.float32)
        mask = Image.fromarray((drv[..., 3]).astype(np.uint8))
        er = mask.filter(ImageFilter.MinFilter(max(3, int(7 * s)) | 1))
        edge_m = (np.asarray(mask, np.float32) - np.asarray(er, np.float32)) / 255
        edge_m *= (np.arange(H) < H * 0.79)[:, None]
        self.rim = np.asarray(Image.fromarray((edge_m * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2 * s)),
                              np.float32)[..., None] / 255
        d.rounded_rectangle([W * 0.60, H * 0.80, W * 0.84, H * 1.05], radius=int(W * 0.045), fill=seat, outline=edge, width=2)
        b = np.asarray(D, np.float32)
        self.cabB_rgb, self.cabB_a = b[..., :3], b[..., 3:] / 255
        self.cab_mask = np.clip(self.cabA_a + self.cabB_a, 0, 1)
        self.wheel_c = (W * 0.72, H * 0.715)
        self.wheel_r = (W * 0.135, H * 0.095)

    def _build_drops(self):
        W, H, s, r = self.W, self.H, self.s, self.rng
        n = 340
        cx, cy = r.uniform(W * 0.06, W * 0.94, n), r.uniform(H * 0.1, H * 0.68, n)
        rad = np.clip(r.gamma(2.0, 1.4, n) * s + 1.2 * s, 1.2, 7 * s)
        py, px, sy, sx, did, shade = [], [], [], [], [], []
        for i in range(n):
            R = int(np.ceil(rad[i]))
            oy, ox = np.mgrid[-R:R + 1, -R:R + 1]
            dd = np.sqrt(ox ** 2 + oy ** 2)
            m = dd <= rad[i]
            yy, xx = (cy[i] + oy[m]).astype(int), (cx[i] + ox[m]).astype(int)
            py.append(yy); px.append(xx)
            sy.append(np.clip((cy[i] - oy[m] * 2.2 - rad[i] * 3).astype(int), 0, H - 1))  # inverted lens
            sx.append(np.clip((cx[i] - ox[m] * 2.2).astype(int), 0, W - 1))
            did.append(np.full(m.sum(), i))
            shade.append(np.clip((dd[m] / rad[i]) ** 3 * (oy[m] > 0), 0, 1))
        self.dr_py = np.clip(np.concatenate(py), 0, H - 1)
        self.dr_px = np.clip(np.concatenate(px), 0, W - 1)
        self.dr_sy, self.dr_sx = np.concatenate(sy), np.concatenate(sx)
        self.dr_id, self.dr_shade = np.concatenate(did), np.concatenate(shade)[:, None]
        self.dr_delay = r.uniform(0.05, 2.6, n)
        # wipers — RHD layout: blades rest pointing left and sweep up towards the driver (right)
        self.pivots = [(W * 0.30, H * 0.715), (W * 0.67, H * 0.715)]
        self.blade = [W * 0.29, W * 0.31]
        self.wipe_P, self.wipe_T = 2.8, 1.0
        self.dr_cover = np.zeros((n, 2), bool)
        self.dr_uup = np.zeros((n, 2))
        for k, (pxv, pyv) in enumerate(self.pivots):
            dist = np.hypot(cx - pxv, cy - pyv)
            ang = np.degrees(np.arctan2(pyv - cy, cx - pxv))
            self.dr_cover[:, k] = (dist < self.blade[k]) & (ang >= 75) & (ang <= 180)
            c = np.clip((ang - 127.5) / 52.5, -1, 1)
            self.dr_uup[:, k] = np.arccos(c) / np.pi * self.wipe_T / 2
        self.dr_phase = r.uniform(0, 6, n)

    # ------------------------------------------------------------------ helpers
    def wiper_angle(self, t):
        u = t % self.wipe_P
        if u >= self.wipe_T:
            return 180.0
        return 127.5 + 52.5 * np.cos(TAU * u / self.wipe_T)

    def fogc(self, col, z):
        a = 1 - np.exp(-max(z, 0) / 140)
        c = np.asarray(col, np.float32) * (1 - a) + self.fog * a
        return tuple(int(v) for v in np.clip(c, 0, 255))

    def P(self, x, y, z):
        z = max(z, 0.3)
        return (self.cx + (x + self.kc * z * z) * self.f / z, self.hy - (y - self.cam_h) * self.f / z)

    def rel(self, zw):
        zr = (zw - self.camz) % LZ
        return zr - LZ if zr > LZ - 60 else zr

    def glow(self, x, y, rad, col, k=1.0):
        rad = max(1.0, rad / 2)
        self.ld.ellipse([x / 2 - rad, y / 2 - rad, x / 2 + rad, y / 2 + rad],
                        fill=tuple(int(min(255, c * k)) for c in col))

    def streak(self, x, ytop, length, width, col, k=0.6):
        x, ytop, length, width = x / 2, ytop / 2, length / 2, max(1.0, width / 2)
        self.ld.polygon([(x - width / 2, ytop), (x + width / 2, ytop), (x + width * 0.2, ytop + length),
                         (x - width * 0.2, ytop + length)], fill=tuple(int(min(255, c * k)) for c in col))

    def lamp(self, x, y, z, col, size, k=1.0, refl=True):
        """Light source with bloom and a long reflection on the wet road."""
        if z < self.znear:
            return
        fa = np.exp(-z / 170)
        sx, sy = self.P(x, y, z)
        rad = size * self.f / z
        self.d.ellipse([sx - rad * 0.35, sy - rad * 0.35, sx + rad * 0.35, sy + rad * 0.35],
                       fill=tuple(int(min(255, c * (0.6 + 0.4 * fa) + 60)) for c in col))
        self.glow(sx, sy, min(rad * 2.2, 70 * self.s), col, 0.75 * k * (0.3 + 0.7 * fa))
        if refl:
            gx, gy = self.P(x, 0, z)
            self.streak(gx, gy, min((gy - sy) * 1.1 + 8, self.H * 0.35), min(rad * 1.4, 40 * self.s),
                        col, 0.45 * k * (0.3 + 0.7 * fa))

    # ------------------------------------------------------------------ world
    def draw_ground(self):
        d, P, fogc = self.d, self.P, self.fogc
        zs = np.geomspace(self.znear, self.zfar, 46)[::-1]
        for a, b in zip(zs[1:], zs[:-1]):  # far -> near ; a < b
            d.polygon([P(L_EDGE, 0, a), P(R_EDGE, 0, a), P(R_EDGE, 0, b), P(L_EDGE, 0, b)], fill=fogc((20, 19, 30), a))
            d.polygon([P(L_FACADE, 0.15, a), P(L_EDGE, 0.15, a), P(L_EDGE, 0.15, b), P(L_FACADE, 0.15, b)], fill=fogc((34, 30, 44), a))
            d.polygon([P(R_EDGE, 0.15, a), P(R_FACADE, 0.15, a), P(R_FACADE, 0.15, b), P(R_EDGE, 0.15, b)], fill=fogc((34, 30, 44), a))
            for x, col, w in ((L_EDGE + 0.15, (190, 190, 185), 0.15), (CENTER, (230, 170, 40), 0.16),
                              (R_EDGE - 0.15, (190, 190, 185), 0.15)):
                d.polygon([P(x - w / 2, 0, a), P(x + w / 2, 0, a), P(x + w / 2, 0, b), P(x - w / 2, 0, b)], fill=fogc(col, a))
        off = self.camz % 12
        for n in range(int(self.zfar / 12) + 2):
            a, b = n * 12 - off, n * 12 - off + 6
            if b < self.znear or a > self.zfar:
                continue
            a = max(a, self.znear)
            for x in (LANE_DIV, ONC_DIV):
                d.polygon([P(x - 0.07, 0, a), P(x + 0.07, 0, a), P(x + 0.07, 0, b), P(x - 0.07, 0, b)], fill=fogc((200, 200, 195), a))
        for zi in INTERSECTIONS:  # zebra crossing + stop line
            z0 = self.rel(zi - 7)
            if not (self.znear < z0 < self.zfar):
                continue
            x = L_EDGE + 0.3
            while x < R_EDGE - 0.3:
                d.polygon([P(x, 0, z0), P(x + 0.45, 0, z0), P(x + 0.45, 0, z0 + 4), P(x, 0, z0 + 4)], fill=fogc((205, 205, 200), z0))
                x += 0.9
            zs_ = z0 - 2
            if zs_ > self.znear:
                d.polygon([P(L_EDGE, 0, zs_), P(CENTER, 0, zs_), P(CENTER, 0, zs_ + 0.4), P(L_EDGE, 0, zs_ + 0.4)],
                          fill=fogc((210, 210, 205), zs_))

    def drawables(self, t):
        out = []
        for b in self.buildings:
            z1 = self.rel(b["z1"])
            if z1 + b["w"] > self.znear and z1 < self.zfar:
                out.append((z1 + b["w"], self.draw_building, (b, z1)))
        for sg in self.signs:
            z = self.rel(sg["z"])
            if self.znear < z < self.zfar:
                out.append((z, self.draw_sign, (sg, z)))
        off = self.camz % LAMP_GAP
        for n in range(int(self.zfar / LAMP_GAP) + 2):
            z = n * LAMP_GAP - off + 6
            if self.znear < z < self.zfar:
                out.append((z, self.draw_streetlights, (z,)))
        for zo in OVERPASSES:
            z = self.rel(zo)
            if -10 < z < self.zfar:
                out.append((z + 12, self.draw_overpass, (z,)))
        for k, zg in enumerate(GANTRIES):
            z = self.rel(zg)
            if self.znear < z < self.zfar:
                out.append((z, self.draw_gantry, (z, k)))
        for zi in INTERSECTIONS:
            z = self.rel(zi)
            if self.znear < z < self.zfar:
                out.append((z, self.draw_signal, (z,)))
        out.append((22 + 3 * np.sin(t / 7), self.draw_car, (0.0, 22 + 3 * np.sin(t / 7), self.lead_col, t, 0)))
        for k, c in enumerate(self.left_cars):
            z = 3 + (c["z0"] + c["v"] * t) % 230
            out.append((z, self.draw_car, (-3.5, z, c["col"], t, k + 1)))
        for c in self.oncoming:
            z = 3 + (c["z0"] + c["v"] * t) % 260
            out.append((z, self.draw_oncoming, (c["x"], z)))
        out.sort(key=lambda o: -o[0])
        return out

    def draw_building(self, b, z1):
        d, P, fogc = self.d, self.P, self.fogc
        xf, out, h, w = b["x"], b["out"], b["h"], b["w"]
        z2 = z1 + w
        za = max(z1, self.znear)
        if z1 >= self.znear:  # front face
            d.polygon([P(xf, 0, z1), P(xf, h, z1), P(xf + out * 25, h, z1), P(xf + out * 25, 0, z1)], fill=fogc(b["col"] * 0.55, z1))
        d.polygon([P(xf, 0, za), P(xf, h, za), P(xf, h, z2), P(xf, 0, z2)], fill=fogc(b["col"], za))
        if za < 175:
            for (wa, wb, ya, yb, wc, k) in b["wins"]:
                a_, b_ = z1 + wa, z1 + wb
                if b_ <= self.znear:
                    continue
                a_ = max(a_, self.znear)
                d.polygon([P(xf, ya, a_), P(xf, yb, a_), P(xf, yb, b_), P(xf, ya, b_)],
                          fill=fogc(np.array(wc, np.float32) * k * 0.62, a_))
                if ya < 1 and a_ < 90:  # shop-front spill light on the wet pavement
                    gx, gy = self.P(xf - out * 1.5, 0, (a_ + b_) / 2)
                    self.glow(gx, gy, (b_ - a_) * self.f / max(a_, 1) * 0.4, wc, 0.25)
        if b["beacon"] and np.sin(self.t * 2.4 + z1) > 0.3:
            self.lamp(xf + out * 4, h + 1.5, (z1 + z2) / 2, (255, 40, 40), 0.6, 0.8, refl=False)

    def draw_sign(self, sg, z):
        xa, xb = (L_FACADE + 0.15, L_FACADE + 1.35) if sg["side"] == "L" else (R_FACADE - 1.35, R_FACADE - 0.15)
        p1, p2 = self.P(xa, sg["y"] + sg["hm"], z), self.P(xb, sg["y"], z)
        x0, x1 = sorted((p1[0], p2[0]))
        w, h = int(x1 - x0), int(p2[1] - p1[1])
        if w < 2 or h < 3 or x1 < 0 or x0 > self.W:
            return
        lv = sg["sprite"]["levels"]
        spr = lv[min(len(lv) - 1, int((1 - np.exp(-z / 140)) * len(lv)))]
        spr = spr.resize((w, h), Image.BILINEAR)
        self.img.paste(spr, (int(x0), int(p1[1])), spr)
        col = sg["sprite"]["col"]
        fa = 0.35 + 0.65 * np.exp(-z / 160)
        flick = 0.75 + 0.25 * np.sin(self.t * 13 + z * 3) if (int(z * 7) % 11 == 0) else 1.0
        self.ld.rectangle([x0 / 2 - w * 0.25, p1[1] / 2, x1 / 2 + w * 0.25, p2[1] / 2],
                          fill=tuple(int(c * 0.75 * fa * flick) for c in col))
        gx, gy = self.P((xa + xb) / 2, 0, z)
        self.streak(gx, gy, (gy - p1[1]) * 0.9, w * 1.1, col, 0.45 * fa)

    def draw_streetlights(self, z):
        d, P, fogc = self.d, self.P, self.fogc
        wpx = max(1, int(0.22 * self.f / z))
        for xp, xl in ((-5.7, -4.3), (9.3, 7.9)):
            d.line([P(xp, 0, z), P(xp, 8.3, z), P(xl, 8.3, z)], fill=fogc((40, 38, 50), z), width=wpx)
            self.lamp(xl, 8.2, z, (255, 160, 70), 0.55, 1.0)
            gx, gy = P(xl, 0, z)
            self.glow(gx, gy, 3.5 * self.f / z, (255, 120, 50), 0.18)

    def draw_overpass(self, z):
        d, P, fogc = self.d, self.P, self.fogc
        zf = max(z, self.znear)
        if z + 12 > self.znear:
            d.polygon([P(-40, 7.6, zf), P(50, 7.6, zf), P(50, 7.6, z + 12), P(-40, 7.6, z + 12)], fill=fogc((14, 12, 22), zf))
        for xp in (-7.5, 10.5):
            zp = z + 6
            if zp > self.znear:
                d.polygon([P(xp, 0, zp), P(xp + 1.6, 0, zp), P(xp + 1.6, 7.6, zp), P(xp, 7.6, zp)], fill=fogc((26, 22, 34), zp))
        if z > self.znear:
            d.polygon([P(-40, 10.8, z), P(50, 10.8, z), P(50, 7.6, z), P(-40, 7.6, z)], fill=fogc((30, 26, 40), z))
            p1, p2 = P(-2.0, 10.4, z), P(4.0, 8.4, z)
            w, h = int(p2[0] - p1[0]), int(p2[1] - p1[1])
            if w > 4 and h > 2:
                lv = self.shuto_sprite
                spr = lv[min(len(lv) - 1, int((1 - np.exp(-z / 140)) * len(lv)))].resize((w, h), Image.BILINEAR)
                self.img.paste(spr, (int(p1[0]), int(p1[1])), spr)
            for xl in range(-30, 46, 5):
                self.lamp(xl, 7.45, z, (255, 190, 120), 0.18, 0.6, refl=False)

    def draw_gantry(self, z, k):
        d, P, fogc = self.d, self.P, self.fogc
        wpx = max(1, int(0.3 * self.f / z))
        d.line([P(-6.3, 0, z), P(-6.3, 7.6, z), P(1.6, 7.6, z)], fill=fogc((70, 72, 80), z), width=wpx)
        p1, p2 = P(-5.0, 7.5, z), P(1.2, 5.4, z)
        w, h = int(p2[0] - p1[0]), int(p2[1] - p1[1])
        if w > 4 and h > 2:
            lv = self.gantry_sprites[k]
            spr = lv[min(len(lv) - 1, int((1 - np.exp(-z / 140)) * len(lv)))].resize((w, h), Image.BILINEAR)
            self.img.paste(spr, (int(p1[0]), int(p1[1])), spr)
            self.ld.rectangle([p1[0] / 2, p1[1] / 2, p2[0] / 2, p2[1] / 2], fill=(10, 40, 90))

    def draw_signal(self, z):
        """Horizontal Japanese traffic light over our (left) lanes: 青 / 黄 / 赤."""
        d, P, fogc = self.d, self.P, self.fogc
        wpx = max(1, int(0.25 * self.f / z))
        d.line([P(L_EDGE - 0.8, 0, z), P(L_EDGE - 0.8, 6.0, z), P(-0.6, 6.0, z)], fill=fogc((60, 60, 66), z), width=wpx)
        d.polygon([P(-2.9, 5.95, z), P(-0.7, 5.95, z), P(-0.7, 5.25, z), P(-2.9, 5.25, z)], fill=fogc((30, 30, 34), z))
        state = 0 if (self.t % 40) < 34 else 1
        for i, (xc, col) in enumerate(((-2.45, (0, 255, 190)), (-1.8, (255, 190, 0)), (-1.15, (255, 30, 30)))):
            if i == state:
                self.lamp(xc, 5.6, z, col, 0.3, 1.2)
            else:
                cx, cy = P(xc, 5.6, z)
                rr = 0.2 * self.f / z
                d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], fill=fogc(np.array(col) * 0.15, z))

    def draw_car(self, x, z, col, t, k):
        d, P, fogc = self.d, self.P, self.fogc
        if z < self.znear:
            return
        d.polygon([P(x - 0.85, 0.0, z), P(x + 0.85, 0.0, z), P(x + 0.85, 0.25, z), P(x - 0.85, 0.25, z)], fill=(5, 5, 8))
        d.polygon([P(x - 0.88, 0.22, z), P(x + 0.88, 0.22, z), P(x + 0.88, 0.95, z), P(x - 0.88, 0.95, z)], fill=fogc(col, z))
        d.polygon([P(x - 0.72, 0.95, z), P(x + 0.72, 0.95, z), P(x + 0.56, 1.42, z), P(x - 0.56, 1.42, z)], fill=fogc(col * 0.8, z))
        d.polygon([P(x - 0.62, 1.0, z), P(x + 0.62, 1.0, z), P(x + 0.5, 1.36, z), P(x - 0.5, 1.36, z)], fill=fogc((30, 26, 46), z))
        brake = 1.6 if (np.sin(t * 0.37 + k * 2.1) > 0.85) else 1.0
        for sx in (-0.66, 0.66):
            p1, p2 = P(x + sx - 0.18, 0.84, z), P(x + sx + 0.18, 0.7, z)
            d.rectangle([min(p1[0], p2[0]), p1[1], max(p1[0], p2[0]), p2[1]], fill=(255, int(40 * brake), 40))
            self.lamp(x + sx, 0.77, z, (255, 30, 40), 0.22 * brake, 0.9 * brake)
        p1, p2 = P(x - 0.2, 0.55, z), P(x + 0.2, 0.42, z)  # licence plate
        d.rectangle([p1[0], p1[1], p2[0], p2[1]], fill=fogc((200, 200, 170), z))

    def draw_oncoming(self, x, z):
        d, P, fogc = self.d, self.P, self.fogc
        if z < self.znear:
            return
        d.polygon([P(x - 0.86, 0.2, z), P(x + 0.86, 0.2, z), P(x + 0.86, 0.95, z), P(x - 0.86, 0.95, z)], fill=fogc((18, 16, 26), z))
        for sx in (-0.62, 0.62):
            self.lamp(x + sx, 0.65, z, (255, 245, 215), 0.32, 1.25)

    # ------------------------------------------------------------------ frame
    def frame(self, t, energy=0.0, onset=0.0, bands=None):
        W, H, s = self.W, self.H, self.s
        self.t = t
        self.camz = t * self.speed
        self.kc = 0.00016 * np.sin(TAU * t / 46) + 0.00008 * np.sin(TAU * t / 19 + 1)
        self.hy = self.hy0 + s * (0.8 * np.sin(t * 9.1) + 0.5 * np.sin(t * 5.3))
        base = self.bg.copy()
        L = self.far  # distant skyline follows the curve
        off = int(t * L["speed"] - self.kc * 200 * self.f) % L["L"]
        cols = (np.arange(W) + off) % L["L"]
        ys = max(0, L["y0"])
        sl = slice(ys - L["y0"], self.horizon - L["y0"])
        a = L["a"][sl][:, cols]
        base[ys:self.horizon] = base[ys:self.horizon] * (1 - a) + L["rgb"][sl][:, cols] * a + L["glow"][sl][:, cols] * 0.6

        self.img = Image.fromarray(base.astype(np.uint8))
        self.d = ImageDraw.Draw(self.img)
        self.light = Image.new("RGB", (W // 2, H // 2))
        self.ld = ImageDraw.Draw(self.light)
        self.draw_ground()
        for _, fn, args in self.drawables(t):
            fn(*args)

        img = np.asarray(self.img, np.float32)
        lt = self.light.filter(ImageFilter.GaussianBlur(3 * s))
        wide = self.light.resize((W // 8, H // 8), Image.BILINEAR).filter(ImageFilter.GaussianBlur(4 * s))
        img += np.asarray(lt.resize((W, H), Image.BILINEAR), np.float32) * (0.6 + 0.25 * energy)
        img += np.asarray(wide.resize((W, H), Image.BILINEAR), np.float32) * 0.35
        # falling rain
        R = self.rain
        ry = ((R[:, 1] + t * 900 * s * R[:, 2]) % H).astype(int)
        rx = ((R[:, 0] - t * 140 * s - ry * 0.12) % W).astype(int)
        ln = int(16 * s)
        for k in range(ln):
            img[np.clip(ry + k, 0, H - 1), np.clip(rx - k // 6, 0, W - 1)] += 30 * (1 - k / ln) + 8
        img = self.windshield(img, t)
        img = self.cabin(img, t, energy, bands)
        img = self.text_overlay(img, t, energy)
        return self.post(img, t, onset)

    def windshield(self, img, t):
        P, T = self.wipe_P, self.wipe_T
        c = np.floor(t / P) * P
        u = t - c
        last = np.full(len(self.dr_delay), -1e9)
        for k in range(2):
            uup, udn = self.dr_uup[:, k], T - self.dr_uup[:, k]
            lk = np.where(u >= udn, c + udn, np.where(u >= uup, c + uup, c - P + udn))
            last = np.where(self.dr_cover[:, k], np.maximum(last, lk), last)
        free = ~self.dr_cover.any(1)
        last[free] = np.floor((t + self.dr_phase[free]) / 6) * 6 - self.dr_phase[free]
        alpha = np.clip((t - last - self.dr_delay) / 0.3, 0, 1)[self.dr_id][:, None]
        src = img[self.dr_sy, self.dr_sx] * 1.15 + 10 + self.dr_shade * 50
        img[self.dr_py, self.dr_px] = img[self.dr_py, self.dr_px] * (1 - alpha) + src * alpha
        ang = np.radians(self.wiper_angle(t))
        if np.degrees(ang) < 179.5:
            for (pxv, pyv), ln in zip(self.pivots, self.blade):
                l = np.linspace(0.05, 1, 300) * ln
                xs, ys = (pxv + l * np.cos(ang)).astype(int), (pyv - l * np.sin(ang)).astype(int)
                th = max(1, int(3 * self.s))
                for oy in range(-th, th + 1):
                    for ox in range(-1, 2):
                        img[np.clip(ys + oy, 0, self.H - 1), np.clip(xs + ox, 0, self.W - 1)] = (8, 7, 11)
        return img

    def cabin(self, img, t, energy, bands):
        W, H, s = self.W, self.H, self.s
        d_lamp = (self.camz - 6) % LAMP_GAP
        pulse = np.exp(-(min(d_lamp, LAMP_GAP - d_lamp) / 4.0) ** 2)
        img = img * (1 - self.cabA_a) + self.cabA_rgb * self.cabA_a
        # dynamic: steering wheel (RIGHT side), driver's arms, stereo LCD, mirror headlights
        cab = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
        d = ImageDraw.Draw(cab)
        (cx, cy), (rx, ry) = self.wheel_c, self.wheel_r
        d.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], outline=(16, 12, 20), width=int(15 * s))
        d.arc([cx - rx, cy - ry, cx + rx, cy + ry], 200, 340, fill=(60, 40, 80), width=max(1, int(2 * s)))
        rot = -self.kc * 9.0e4
        for side, (shx, shy) in ((180, (W * 0.655, H * 0.68)), (0, (W * 0.785, H * 0.68))):
            a = np.radians(side + rot + (8 if side == 0 else -8))
            hx, hy = cx + rx * np.cos(a), cy - ry * np.sin(a)
            d.line([(shx, shy), (hx, hy)], fill=(12, 10, 16), width=int(26 * s))
            d.ellipse([hx - 12 * s, hy - 9 * s, hx + 12 * s, hy + 9 * s], fill=(70, 48, 52))
        x0, y0, x1, y1 = self.lcd
        bar_n = 12
        bw = (x1 - x0 - 8 * s) / bar_n
        bands = bands if bands is not None else np.full(bar_n, energy)
        for i in range(bar_n):
            hgt = (y1 - y0) * 0.5 * float(np.clip(bands[i % len(bands)], 0.05, 1))
            bx = x0 + 4 * s + i * bw
            colr = (int(60 + 195 * i / bar_n), int(230 - 150 * i / bar_n), 255 - int(60 * i / bar_n))
            d.rectangle([bx, y1 - 3 * s - hgt, bx + bw * 0.7, y1 - 3 * s], fill=colr)
        msg = f"  ♪ {self.title[1]}  —  {self.title[2]}     "
        scroll = int(t * 4) % len(msg)
        d.text((x0 + 4 * s, y0 + 2 * s), (msg[scroll:] + msg[:scroll])[:13], font=self._lcd_jp, fill=(120, 255, 230))
        m = self.mirror
        mcx, mcy = (m[0] + m[2]) / 2 + 12 * s * np.sin(t * 0.3), (m[1] + m[3]) / 2 + 2 * s
        for dx in (-14 * s, 14 * s):  # car behind us, reflected in the mirror
            d.ellipse([mcx + dx - 4 * s, mcy - 3 * s, mcx + dx + 4 * s, mcy + 3 * s], fill=(255, 245, 220))
        img = np.asarray(cab, np.float32)
        img = img * (1 - self.cabB_a) + self.cabB_rgb * self.cabB_a
        # neon rim light on the driver + street-light wash sweeping through the cabin
        mix = 0.5 + 0.5 * np.sin(t * 0.7)
        rim_col = np.array([255, 60, 170], np.float32) * mix + np.array([60, 220, 255], np.float32) * (1 - mix)
        img += self.rim * rim_col * (0.55 + 0.6 * energy + 0.8 * pulse)
        img += self.cab_mask * np.array([70, 42, 18], np.float32) * pulse * 0.6
        return img
