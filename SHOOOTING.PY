"""
SKY RAIDER - 종스크롤 슈팅 게임 (pygame)

공중의 적은 '샷'으로, 지상의 적은 '폭탄'으로 공격하는 고전 종스크롤 슈팅 스타일의 오리지널 게임입니다.
모든 그래픽은 코드로 그리므로 이미지/사운드 파일이 필요 없습니다.

설치:  pip install pygame
실행:  python SHOOOTING.PY

조작
  방향키 / WASD : 이동
  Z / J / Space : 공중 샷 (누르고 있으면 연사)
  X / K         : 지상 폭탄 (조준점 위치에 떨어짐)
  P             : 일시정지
  M             : 모든 소리 켜기 / 끄기
  B             : 배경음악만 켜기 / 끄기
  Enter         : 게임 시작 / 재시작
  ESC           : 종료

효과음과 배경음악도 모두 코드로 합성하므로 사운드 파일이 필요 없습니다.

아이템 (벙커, 일부 공중 적, 보스가 떨어뜨림)
  P   파워     : 샷 단계 +1 (최대 3)
  S   스피드   : 이동 속도 +1 (최대 2)
  H   호밍     : 12초 동안 적을 따라가는 유도 미사일 추가 발사
  O   실드     : 한 번 피격을 막아 줌
  C   클리어   : 화면의 적 탄을 모두 지우고 점수로 바꿈, 공중 적에게 피해
  ★   메달     : 보너스 점수 (연속으로 먹을수록 500 → 1000 → ... → 8000)
  1UP 추가 목숨 (희귀)
  이미 최대 단계인 아이템을 먹으면 1000점. 가까이 가면 아이템이 끌려옵니다.

적
  공중 (샷으로 공격)
    다트      : 지그재그 하강, 조준 사격 (3기 편대로도 등장)
    훅        : 내려오다 플레이어 쪽으로 꺾어 이탈
    링        : 멈춰서 회전하며 방사형 탄막
    스위퍼    : 화면 옆에서 4기 편대로 가로지르며 아래로 탄 투하
    지프      : 멈춰서 빨간 경고선으로 조준한 뒤 고속 돌진
    스플리터  : 격추하면 작은 적 3개로 분열
    폭격기    : 크고 단단함(체력 바 표시), 3갈래 탄, 아이템을 잘 떨어뜨림
  지상 (폭탄으로 공격)
    포대      : 고정, 조준 사격
    벙커      : 단단함, 아이템을 자주 떨어뜨림
    탱크      : 좌우로 움직이며 조준 사격
    보트      : 강을 거슬러 올라가며 2갈래 탄
    발사대    : 유도 미사일 발사 (미사일은 샷으로 격추 가능)
    레이더    : 살아 있는 동안 지프를 계속 불러옴, 파괴하면 아이템 확정
"""

import math
import random
import sys
from array import array

import pygame

# ===================== 설정 =====================
W, H = 480, 720
FPS = 60
TERRAIN_H = 2048            # 배경 지형 텍스처 높이 (반복 스크롤)
BASE_SCROLL = 1.2           # 기본 스크롤 속도 (px/frame)
BOSS_TIME = 45 * FPS        # 스테이지 시작 후 보스 등장까지 시간
RETICLE_DIST = 170          # 기체와 폭탄 조준점 사이 거리
START_LIVES = 3

WHITE = (240, 240, 240)
YELLOW = (255, 220, 80)
ORANGE = (255, 140, 40)
RED = (230, 60, 60)
CYAN = (90, 220, 255)
PINK = (255, 110, 200)
GREY = (120, 120, 130)
DARK = (20, 20, 30)


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def dist2(ax, ay, bx, by):
    return (ax - bx) ** 2 + (ay - by) ** 2


def aim(sx, sy, tx, ty, speed):
    ang = math.atan2(ty - sy, tx - sx)
    return math.cos(ang) * speed, math.sin(ang) * speed


# ===================== 배경음악 악보 =====================
# 한 칸 = 8분음표. "-" 는 앞 음 늘이기, "." 는 쉼표.
STAGE_BGM = {
    "bpm": 150,
    "chords": ["Am", "F", "G", "E", "Am", "F", "G", "E"],
    "lead": [
        "A4 . C5 E5 A5 - G5 E5", "F5 - E5 C5 A4 - C5 -",
        "D5 . E5 G5 B5 - A5 G5", "G#5 - - E5 B4 - - .",
        "E5 - A5 - C6 - B5 A5", "C6 - A5 F5 A5 - C6 -",
        "B5 - G5 D5 G5 - B5 D6", "E6 - - D6 B5 G#5 E5 .",
    ],
    "bass_style": "octave",   # 8분음표로 근음-옥타브 반복
    "kick": [0, 8],           # 16분음표 위치 (마디 = 16칸)
    "snare": [4, 12],
    "hat_step": 2,
}
BOSS_BGM = {
    "bpm": 172,
    "chords": ["Dm", "Bb", "C", "A", "Dm", "Bb", "C", "A"],
    "lead": [
        "D5 F5 A5 F5 D5 F5 A5 C6", "D6 - C6 A5 A#5 - A5 F5",
        "E5 G5 C6 G5 E5 G5 C6 E6", "C#6 - - A5 E5 - C#5 E5",
        "A5 - F5 D5 A5 - C6 D6", "F6 - D6 A#5 F5 - A#5 D6",
        "E6 - C6 G5 C6 - E6 G6", "A6 - E6 C#6 A5 E5 C#5 A4",
    ],
    "bass_style": "drive",    # 16분음표로 몰아치는 베이스
    "kick": [0, 4, 8, 12],
    "snare": [4, 12],
    "hat_step": 1,
}
CHORDS = {  # 코드 이름: (근음 MIDI 번호, 구성음 반음 간격)
    "Am": (45, (0, 3, 7)), "F": (41, (0, 4, 7)), "G": (43, (0, 4, 7)), "E": (40, (0, 4, 7)),
    "Dm": (38, (0, 3, 7)), "Bb": (46, (0, 4, 7)), "C": (36, (0, 4, 7)), "A": (45, (0, 4, 7)),
}
NOTE_INDEX = {"C": 0, "C#": 1, "D": 2, "D#": 3, "E": 4, "F": 5, "F#": 6,
              "G": 7, "G#": 8, "A": 9, "A#": 10, "B": 11}


def note_to_midi(name):
    """'C#5' -> 73"""
    return NOTE_INDEX[name[:-1]] + (int(name[-1]) + 1) * 12


def midi_to_freq(m):
    return 440.0 * 2 ** ((m - 69) / 12)


# ===================== 효과음 / 배경음악 (코드로 합성) =====================
class SoundFX:
    """파형을 직접 계산해서 효과음과 배경음악을 만든다. 사운드 장치가 없으면 조용히 비활성화."""

    RATE = 22050
    MUSIC_VOLUME = 0.55

    def __init__(self):
        self.enabled = False
        self.muted = False
        self.music_on = True
        self.sounds = {}
        self.music = {}
        self.current_music = None
        self.last_played = {}
        self.frame = 0
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(self.RATE, -16, 1, 512)
            rate, size, channels = pygame.mixer.get_init()
        except pygame.error:
            return
        self.rate, self.channels = rate, channels
        pygame.mixer.set_num_channels(24)
        pygame.mixer.set_reserved(1)                 # 0번 채널은 배경음악 전용
        self.music_channel = pygame.mixer.Channel(0)
        self.music_channel.set_volume(self.MUSIC_VOLUME)
        self.build()
        self.music = {"stage": self.render_song(STAGE_BGM), "boss": self.render_song(BOSS_BGM)}
        self.enabled = True

    # ----- 합성 도구 -----
    def synth(self, dur, f0=440.0, f1=None, wave="square", vol=0.3, noise=0.0,
              lowpass=1.0, decay=2.0):
        """dur초 길이의 소리. f0 -> f1 로 주파수 변화, noise 비율만큼 잡음 섞기."""
        f1 = f1 or f0
        n = int(self.rate * dur)
        out = []
        phase = 0.0
        lp = 0.0
        rnd = random.Random(int(f0 * 1000 + dur * 100))
        attack = max(1, int(self.rate * 0.004))
        for i in range(n):
            t = i / n
            freq = f0 * (f1 / f0) ** t          # 지수적 주파수 변화
            phase = (phase + freq / self.rate) % 1.0
            if wave == "square":
                v = 1.0 if phase < 0.5 else -1.0
            elif wave == "saw":
                v = 2.0 * phase - 1.0
            elif wave == "tri":
                v = 4.0 * abs(phase - 0.5) - 1.0
            else:
                v = math.sin(phase * math.tau)
            if noise:
                v = v * (1 - noise) + rnd.uniform(-1, 1) * noise
            lp += lowpass * (v - lp)                # 간단한 저역 통과 필터
            env = min(1.0, i / attack) * (1 - t) ** decay
            out.append(lp * env * vol)
        return out

    @staticmethod
    def concat(*parts):
        res = []
        for p in parts:
            res.extend(p)
        return res

    @staticmethod
    def mix(*parts):
        n = max(len(p) for p in parts)
        return [sum(p[i] for p in parts if i < len(p)) for i in range(n)]

    def to_sound(self, samples):
        data = array("h")
        for s in samples:
            v = int(max(-1.0, min(1.0, s)) * 32767)
            data.extend([v] * self.channels)
        return pygame.mixer.Sound(buffer=data.tobytes())

    def notes(self, freqs, each=0.08, wave="square", vol=0.18, decay=1.0):
        """음 목록을 이어 붙인 짧은 멜로디. 0 은 쉼표."""
        return self.concat(*[
            self.synth(each, f, wave=wave, vol=vol, decay=decay) if f else [0.0] * int(self.rate * each)
            for f in freqs
        ])

    def build(self):
        s = self.synth
        C5, E5, G5, C6, E6, G6 = 523, 659, 784, 1047, 1319, 1568
        recipes = {
            "shot": s(0.06, 1400, 700, "square", vol=0.07, decay=1.5),
            "bomb_drop": s(0.42, 1500, 350, "sine", vol=0.16, decay=0.6),
            "bomb_hit": self.mix(s(0.35, 110, 40, "sine", vol=0.45, decay=2.0),
                                 s(0.35, 200, 80, "square", vol=0.35, noise=0.9, lowpass=0.25, decay=2.5)),
            "explode": s(0.32, 300, 60, "square", vol=0.4, noise=0.85, lowpass=0.35, decay=2.2),
            "big_explode": self.mix(s(1.1, 90, 30, "sine", vol=0.5, decay=1.6),
                                    s(1.1, 150, 40, "square", vol=0.45, noise=0.95, lowpass=0.12, decay=1.4)),
            "hit": s(0.03, 260, 180, "square", vol=0.06, decay=1.0),
            "enemy_hit": s(0.04, 900, 500, "square", vol=0.06, decay=1.0),
            "powerup": self.notes([C5, E5, G5, C6, E6, G6], each=0.05, vol=0.14),
            "warning": self.concat(*[self.concat(s(0.18, 880, 880, "saw", vol=0.16, decay=0.2),
                                                 s(0.18, 660, 660, "saw", vol=0.16, decay=0.2))
                                     for _ in range(4)]),
            "stage_clear": self.notes([G5, C6, E6, G6, 0, G6, G6], each=0.11, vol=0.15, decay=0.5),
            "game_over": self.notes([G5, E5, C5, 392, 330, 262], each=0.16, wave="tri", vol=0.3, decay=0.6),
            "start": self.notes([C5, G5, C6, G6], each=0.07, vol=0.14),
            "medal": self.notes([1976, 2637], each=0.07, wave="sine", vol=0.22, decay=1.2),
            "oneup": self.notes([E5, G5, E6, C6, 1175, G6], each=0.09, vol=0.16),
            "clear": self.mix(s(0.7, 150, 2400, "saw", vol=0.14, decay=1.0),
                              s(0.7, 400, 80, "square", vol=0.35, noise=0.9, lowpass=0.3, decay=1.4)),
            "shield_break": s(0.3, 2200, 250, "square", vol=0.16, noise=0.35, decay=1.5),
            "missile": s(0.09, 350, 900, "saw", vol=0.05, noise=0.5, lowpass=0.4, decay=1.2),
        }
        self.sounds = {name: self.to_sound(data) for name, data in recipes.items()}

    # ----- 배경음악 -----
    def render_song(self, song):
        """악보(dict)를 리드/아르페지오/베이스/드럼 4개 파트로 합성해서 반복 재생용 Sound 로 만든다."""
        step = 60.0 / song["bpm"] / 4               # 16분음표 길이(초)
        bars = len(song["chords"])
        n = int(step * 16 * bars * self.rate)
        buf = [0.0] * n
        cache = {}

        def add(at_step, length_steps, key, maker):
            if key not in cache:
                cache[key] = maker()
            off = int(at_step * step * self.rate)
            for i, v in enumerate(cache[key]):
                j = off + i
                if j >= n:
                    break
                buf[j] += v

        def tone(freq, steps, wave, vol, decay, lowpass=1.0):
            return lambda: self.synth(steps * step, freq, wave=wave, vol=vol, decay=decay, lowpass=lowpass)

        for bar, chord_name in enumerate(song["chords"]):
            base = bar * 16
            root, intervals = CHORDS[chord_name]

            # 리드 멜로디 (8분음표 단위 악보 해석)
            tokens = song["lead"][bar].split()
            i = 0
            while i < len(tokens):
                tok = tokens[i]
                length = 1
                while i + length < len(tokens) and tokens[i + length] == "-":
                    length += 1
                if tok not in (".", "-"):
                    m = note_to_midi(tok)
                    add(base + i * 2, length * 2, ("lead", m, length),
                        tone(midi_to_freq(m), length * 2 - 0.3, "square", 0.075, 0.7, 0.5))
                i += length

            # 아르페지오 (16분음표, 부드러운 삼각파)
            arp = [root + 24 + iv for iv in intervals] + [root + 36]
            for k in range(16):
                m = arp[(k if k % 8 < 4 else 7 - k % 8) % 4]
                add(base + k, 1, ("arp", m), tone(midi_to_freq(m), 1, "tri", 0.05, 1.5))

            # 베이스
            if song["bass_style"] == "octave":
                for k in range(8):
                    m = root + (12 if k % 2 else 0)
                    add(base + k * 2, 2, ("bass8", m), tone(midi_to_freq(m), 1.8, "square", 0.16, 1.2, 0.18))
            else:
                for k in range(16):
                    m = root + (12 if k % 4 == 2 else 0)
                    add(base + k, 1, ("bass16", m), tone(midi_to_freq(m), 0.9, "saw", 0.17, 1.0, 0.2))

            # 드럼
            for k in song["kick"]:
                add(base + k, 1, ("kick",), lambda: self.synth(0.12, 150, 40, "sine", vol=0.55, decay=2.5))
            for k in song["snare"]:
                add(base + k, 1, ("snare",),
                    lambda: self.synth(0.12, 220, 180, "tri", vol=0.28, noise=0.8, lowpass=0.6, decay=3.0))
            for k in range(0, 16, song["hat_step"]):
                add(base + k, 1, ("hat",),
                    lambda: self.synth(0.03, 8000, 8000, "square", vol=0.07, noise=1.0, decay=3.0))

        peak = max(1e-6, max(abs(v) for v in buf))
        gain = min(1.0, 0.9 / peak)
        return self.to_sound([v * gain for v in buf])

    def play_music(self, name, fade_ms=400):
        """같은 곡이 이미 나오고 있으면 그대로 둔다."""
        if not self.enabled:
            return
        if self.current_music == name and self.music_channel.get_busy():
            return
        self.current_music = name
        self.music_channel.stop()
        if not self.muted and self.music_on:
            self.music_channel.play(self.music[name], loops=-1, fade_ms=fade_ms)

    def stop_music(self, fade_ms=500):
        self.current_music = None
        if self.enabled:
            self.music_channel.fadeout(fade_ms)

    def _resume_music(self):
        name, self.current_music = self.current_music, None
        if name:
            self.play_music(name)

    def toggle_music(self):
        self.music_on = not self.music_on
        if not self.enabled:
            return
        if self.music_on:
            self._resume_music()
        else:
            self.music_channel.stop()

    # ----- 재생 -----
    def tick(self):
        self.frame += 1

    def play(self, name, min_gap=0):
        """min_gap 프레임 이내에 같은 소리를 반복 재생하지 않음 (소리 뭉개짐 방지)."""
        if not self.enabled or self.muted:
            return
        if self.frame - self.last_played.get(name, -10 ** 9) < min_gap:
            return
        self.last_played[name] = self.frame
        self.sounds[name].play()

    def toggle_mute(self):
        self.muted = not self.muted
        if not self.enabled:
            return
        if self.muted:
            pygame.mixer.stop()
        else:
            self._resume_music()


# ===================== 배경 지형 =====================
def build_terrain():
    """위아래가 자연스럽게 이어지는 지형 텍스처 생성 (숲, 강, 도로)."""
    surf = pygame.Surface((W, TERRAIN_H))
    surf.fill((62, 120, 58))
    rng = random.Random(7)

    # 밝은 풀밭 얼룩
    for _ in range(260):
        x, y, r = rng.randint(0, W), rng.randint(0, TERRAIN_H), rng.randint(10, 40)
        for oy in (-TERRAIN_H, 0, TERRAIN_H):
            pygame.draw.circle(surf, (78, 138, 66), (x, y + oy), r)

    # 숲 (짙은 녹색 원 뭉치)
    for _ in range(70):
        cx, cy = rng.randint(0, W), rng.randint(0, TERRAIN_H)
        for _ in range(14):
            x = cx + rng.randint(-45, 45)
            y = cy + rng.randint(-45, 45)
            r = rng.randint(8, 18)
            for oy in (-TERRAIN_H, 0, TERRAIN_H):
                pygame.draw.circle(surf, (30, 82, 40), (x, y + oy), r)
                pygame.draw.circle(surf, (40, 98, 48), (x - 3, y - 3 + oy), r // 2)

    # 도로 (가로)
    for y in range(180, TERRAIN_H, 520):
        pygame.draw.rect(surf, (150, 140, 110), (0, y, W, 26))
        for x in range(0, W, 40):
            pygame.draw.rect(surf, (220, 210, 160), (x, y + 12, 20, 3))

    # 강 (구불구불, 주기가 TERRAIN_H 의 약수라 이음새가 없음)
    k = 2 * math.pi / TERRAIN_H
    for y in range(0, TERRAIN_H, 2):
        cx = river_x(y)
        width = 46 + math.sin(y * k * 5) * 10
        pygame.draw.rect(surf, (200, 180, 120), (cx - width / 2 - 6, y, width + 12, 2))  # 모래톱
        pygame.draw.rect(surf, (50, 100, 190), (cx - width / 2, y, width, 2))
        pygame.draw.rect(surf, (80, 140, 220), (cx - width / 6, y, width / 4, 2))
    return surf


# ===================== 이펙트 =====================
class Particle:
    def __init__(self, x, y, color, speed=3.0, life=30, size=3):
        ang = random.uniform(0, math.tau)
        sp = random.uniform(0.3, 1.0) * speed
        self.x, self.y = x, y
        self.vx, self.vy = math.cos(ang) * sp, math.sin(ang) * sp
        self.life = self.max_life = random.randint(life // 2, life)
        self.color = color
        self.size = size

    def update(self):
        self.x += self.vx
        self.y += self.vy
        self.vx *= 0.94
        self.vy *= 0.94
        self.life -= 1

    def draw(self, surf):
        r = max(1, int(self.size * self.life / self.max_life))
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), r)


def explode(particles, x, y, n=20, big=False):
    colors = (YELLOW, ORANGE, RED, WHITE)
    for _ in range(n):
        particles.append(
            Particle(x, y, random.choice(colors), speed=6 if big else 3.5,
                     life=50 if big else 30, size=6 if big else 4)
        )


# ===================== 플레이어 =====================
class Player:
    def __init__(self):
        self.x, self.y = W / 2, H - 110
        self.r = 10                 # 피격 판정 반경 (보이는 것보다 작게)
        self.speed = 4.6
        self.shot_cd = 0
        self.bomb_cd = 0
        self.power = 1
        self.invuln = 120
        self.speed_lv = 0           # S 아이템 (0~2)
        self.shield = False         # O 아이템
        self.homing = 0             # H 아이템 남은 시간(프레임)
        self.missile_cd = 0

    @property
    def reticle(self):
        return self.x, self.y - RETICLE_DIST

    def update(self, keys):
        dx = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
        dy = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
        if dx and dy:
            dx, dy = dx * 0.7071, dy * 0.7071
        spd = self.speed + 0.9 * self.speed_lv
        self.x = clamp(self.x + dx * spd, 18, W - 18)
        self.y = clamp(self.y + dy * spd, RETICLE_DIST + 20, H - 24)
        self.shot_cd = max(0, self.shot_cd - 1)
        self.bomb_cd = max(0, self.bomb_cd - 1)
        self.invuln = max(0, self.invuln - 1)
        self.homing = max(0, self.homing - 1)
        self.missile_cd = max(0, self.missile_cd - 1)

    def fire_missiles(self, missiles):
        """호밍 아이템 효과 중이면 양쪽 날개에서 유도 미사일 발사. 발사했으면 True."""
        if not self.homing or self.missile_cd:
            return False
        self.missile_cd = 22
        missiles += [Missile(self.x - 16, self.y, -1), Missile(self.x + 16, self.y, 1)]
        return True

    def shoot(self, shots):
        """발사했으면 True."""
        if self.shot_cd:
            return False
        self.shot_cd = 6
        x, y = self.x, self.y - 18
        if self.power == 1:
            shots.append(Shot(x, y, 0))
        elif self.power == 2:
            shots += [Shot(x - 7, y, 0), Shot(x + 7, y, 0)]
        else:
            shots += [Shot(x, y, 0), Shot(x - 8, y, -1.6), Shot(x + 8, y, 1.6)]
        return True

    def drop_bomb(self, bombs):
        """투하했으면 True."""
        if self.bomb_cd or any(not b.done for b in bombs):
            return False
        self.bomb_cd = 18
        bombs.append(Bomb(self.x, self.y, *self.reticle))
        return True

    def draw(self, surf, frame):
        if self.invuln and (frame // 4) % 2:
            return
        x, y = int(self.x), int(self.y)
        # 그림자 (반투명)
        shadow = pygame.Surface((22, 10), pygame.SRCALPHA)
        pygame.draw.ellipse(shadow, (0, 0, 0, 70), shadow.get_rect())
        surf.blit(shadow, (x + 4, y + 14))
        # 날개
        pygame.draw.polygon(surf, (170, 180, 200), [(x, y - 6), (x - 22, y + 12), (x - 6, y + 10),
                                                    (x + 6, y + 10), (x + 22, y + 12)])
        # 동체
        pygame.draw.polygon(surf, (230, 235, 245), [(x, y - 22), (x - 7, y + 14), (x + 7, y + 14)])
        pygame.draw.polygon(surf, CYAN, [(x, y - 10), (x - 3, y), (x + 3, y)])
        # 엔진 불꽃
        flame = 6 + (frame % 6)
        pygame.draw.polygon(surf, ORANGE, [(x - 4, y + 14), (x + 4, y + 14), (x, y + 14 + flame)])
        # 호밍 미사일 포드
        if self.homing:
            for dx in (-16, 16):
                pygame.draw.rect(surf, (230, 110, 40), (x + dx - 3, y + 2, 6, 10))
        # 실드
        if self.shield:
            r = 24 + int(2 * math.sin(frame * 0.2))
            ring = pygame.Surface((r * 2 + 4, r * 2 + 4), pygame.SRCALPHA)
            pygame.draw.circle(ring, (90, 220, 255, 60), (r + 2, r + 2), r)
            pygame.draw.circle(ring, (150, 240, 255, 200), (r + 2, r + 2), r, 2)
            surf.blit(ring, (x - r - 2, y - r - 2))


class Shot:
    dmg = 1

    def __init__(self, x, y, vx):
        self.x, self.y, self.vx, self.vy = x, y, vx, -13
        self.dead = False

    def update(self):
        self.x += self.vx
        self.y += self.vy
        if self.y < -20:
            self.dead = True

    def draw(self, surf):
        pygame.draw.rect(surf, YELLOW, (int(self.x) - 2, int(self.y) - 8, 4, 14))
        pygame.draw.rect(surf, WHITE, (int(self.x) - 1, int(self.y) - 6, 2, 10))


class Bomb:
    """기체에서 조준점(지상)으로 포물선을 그리며 떨어지는 폭탄."""
    DURATION = 26

    def __init__(self, sx, sy, tx, ty):
        self.sx, self.sy, self.tx, self.ty = sx, sy, tx, ty
        self.t = 0
        self.done = False
        self.landed = False   # 이번 프레임에 착탄했는지

    def update(self, scroll):
        self.ty += scroll      # 지상 목표는 스크롤과 함께 움직임
        self.t += 1
        if self.t >= self.DURATION:
            self.done = True
            self.landed = True

    @property
    def pos(self):
        p = self.t / self.DURATION
        return self.sx + (self.tx - self.sx) * p, self.sy + (self.ty - self.sy) * p

    def draw(self, surf):
        x, y = self.pos
        r = max(2, int(6 - 4 * self.t / self.DURATION))
        pygame.draw.circle(surf, (40, 40, 40), (int(x), int(y)), r + 1)
        pygame.draw.circle(surf, ORANGE, (int(x), int(y)), r)


class EnemyBullet:
    """적 탄. homing > 0 이면 그 프레임 수만큼 플레이어를 따라가는 미사일 (shootable 이면 샷으로 요격 가능)."""

    def __init__(self, x, y, vx, vy, target=None, homing=0, shootable=False):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.r = 5 if shootable else 4
        self.dead = False
        self.target = target
        self.homing = homing
        self.shootable = shootable

    def update(self):
        if self.homing > 0 and self.target:
            self.homing -= 1
            sp = math.hypot(self.vx, self.vy)
            ang = math.atan2(self.vy, self.vx)
            want = math.atan2(self.target.y - self.y, self.target.x - self.x)
            ang += clamp((want - ang + math.pi) % math.tau - math.pi, -0.035, 0.035)
            self.vx, self.vy = math.cos(ang) * sp, math.sin(ang) * sp
        self.x += self.vx
        self.y += self.vy
        if not (-20 < self.x < W + 20 and -20 < self.y < H + 20):
            self.dead = True

    def draw(self, surf, frame):
        if self.shootable:   # 적 유도 미사일
            ang = math.atan2(self.vy, self.vx)
            bx, by = self.x - math.cos(ang) * 11, self.y - math.sin(ang) * 11
            pygame.draw.line(surf, (200, 40, 40), (int(bx), int(by)), (int(self.x), int(self.y)), 5)
            pygame.draw.circle(surf, WHITE, (int(self.x), int(self.y)), 2)
            pygame.draw.circle(surf, ORANGE if (frame // 3) % 2 else YELLOW, (int(bx), int(by)), 3)
            return
        c = PINK if (frame // 4) % 2 else WHITE
        pygame.draw.circle(surf, RED, (int(self.x), int(self.y)), self.r + 1)
        pygame.draw.circle(surf, c, (int(self.x), int(self.y)), self.r - 1)


class Missile:
    """호밍 아이템의 유도 미사일. 가장 가까운 공중 적(또는 보스)을 향해 방향을 튼다."""
    dmg = 2
    TURN = 0.11

    def __init__(self, x, y, side):
        self.x, self.y = x, y
        self.angle = -math.pi / 2 + side * 0.9    # 처음엔 바깥쪽으로 벌어지며 출발
        self.speed = 4.0
        self.t = 0
        self.dead = False

    def update(self, targets):
        self.t += 1
        self.speed = min(9.0, self.speed + 0.3)
        if targets:
            tx, ty = min(targets, key=lambda p: dist2(p[0], p[1], self.x, self.y))
            want = math.atan2(ty - self.y, tx - self.x)
            diff = (want - self.angle + math.pi) % math.tau - math.pi
            self.angle += clamp(diff, -self.TURN, self.TURN)
        self.x += math.cos(self.angle) * self.speed
        self.y += math.sin(self.angle) * self.speed
        if self.t > 150 or not (-30 < self.x < W + 30 and -30 < self.y < H + 30):
            self.dead = True

    def draw(self, surf):
        bx = self.x - math.cos(self.angle) * 9
        by = self.y - math.sin(self.angle) * 9
        pygame.draw.line(surf, (255, 170, 60), (int(bx), int(by)), (int(self.x), int(self.y)), 4)
        pygame.draw.circle(surf, WHITE, (int(self.x), int(self.y)), 2)
        pygame.draw.circle(surf, YELLOW, (int(bx), int(by)), 2)


# kind: (화면 표시 글자, 색, 등장 가중치)
ITEM_TYPES = {
    "P": ("P", (40, 80, 210), 30),
    "S": ("S", (30, 160, 80), 15),
    "H": ("H", (215, 100, 30), 15),
    "O": ("O", (40, 160, 210), 14),
    "C": ("C", (190, 40, 160), 9),
    "*": ("", (235, 185, 40), 14),
    "1UP": ("1UP", (40, 140, 40), 3),
}


def random_item_kind():
    kinds = list(ITEM_TYPES)
    return random.choices(kinds, weights=[ITEM_TYPES[k][2] for k in kinds])[0]


class Item:
    MAGNET = 80      # 이 거리 안에 들어오면 플레이어 쪽으로 끌려옴

    def __init__(self, x, y, kind=None):
        self.kind = kind or random_item_kind()
        self.x, self.y = x, y
        self.dead = False
        self.t = 0

    def update(self, scroll, player):
        self.t += 1
        d = math.hypot(player.x - self.x, player.y - self.y)
        if d < self.MAGNET:
            pull = 6 * (1 - d / self.MAGNET) + 1
            self.x += (player.x - self.x) / max(d, 1) * pull
            self.y += (player.y - self.y) / max(d, 1) * pull
        else:
            self.y += scroll + 0.6
            self.x += math.sin(self.t * 0.08) * 0.8
        if self.y > H + 20:
            self.dead = True

    def draw(self, surf, font, frame):
        x, y = int(self.x), int(self.y)
        label, color, _ = ITEM_TYPES[self.kind]
        if self.kind == "*":   # 회전하는 별 모양 메달
            a0 = frame * 0.06
            pts = []
            for i in range(10):
                r = 12 if i % 2 == 0 else 5
                a = a0 + i * math.pi / 5
                pts.append((x + math.cos(a) * r, y + math.sin(a) * r))
            pygame.draw.polygon(surf, color, pts)
            pygame.draw.polygon(surf, WHITE, pts, 1)
            return
        if self.kind == "1UP":
            rect = pygame.Rect(x - 17, y - 10, 34, 20)
            pygame.draw.rect(surf, color, rect, border_radius=9)
            pygame.draw.rect(surf, WHITE if (frame // 8) % 2 else YELLOW, rect, 2, border_radius=9)
        else:
            pygame.draw.circle(surf, color, (x, y), 11)
            pygame.draw.circle(surf, WHITE, (x, y), 11, 2)
        txt = font.render(label, True, WHITE)
        surf.blit(txt, txt.get_rect(center=(x, y + 1)))


class Popup:
    """아이템 획득 시 잠깐 떠오르는 글자."""

    def __init__(self, text, x, y, color=WHITE):
        self.text, self.x, self.y, self.color = text, x, y, color
        self.life = 50

    def update(self):
        self.y -= 0.8
        self.life -= 1


# ===================== 적 =====================
class AirEnemy:
    """공중 적: 샷(과 유도 미사일)으로만 격추 가능."""
    STATS = {  # kind: (hp, score, radius)
        "dart": (1, 100, 12),       # 지그재그 하강 + 조준 사격
        "hook": (2, 200, 14),       # 내려오다 꺾어서 위로 이탈
        "ring": (6, 500, 18),       # 멈춰서 회전하며 방사형 탄
        "sweeper": (2, 200, 13),    # 화면 옆에서 편대로 가로지르며 아래로 탄을 떨굼
        "zip": (1, 150, 11),        # 멈춰서 조준(경고선) 후 플레이어에게 돌진
        "splitter": (4, 400, 17),   # 격추되면 작은 적 3개로 분열
        "mini": (1, 50, 8),         # 분열된 작은 적
        "bomber": (16, 1500, 30),   # 크고 단단한 폭격기, 3갈래 탄
    }

    def __init__(self, kind, x, y, stage, vx=0.0, vy=0.0):
        self.kind = kind
        self.x, self.y = x, y
        hp, self.score, self.r = self.STATS[kind]
        if kind == "bomber":
            hp += stage * 3
        elif kind != "mini":
            hp += stage // 3
        self.hp = self.max_hp = hp
        self.stage = stage
        self.t = 0
        self.dead = False
        self.entered = False        # 한 번이라도 화면 안에 들어왔는지
        self.vx, self.vy = vx, vy
        self.base_y = y
        self.phase = 0
        self.flash = 0
        self.angle = math.pi / 2
        self.stop_y = random.randint(140, 260)
        self.fire_cd = random.randint(40, 100)

    def update(self, game):
        self.t += 1
        self.flash = max(0, self.flash - 1)
        p = game.player
        bspeed = 3.0 + 0.3 * self.stage
        k = self.kind

        if k == "dart":
            self.y += 3.2 + 0.2 * self.stage
            self.x += math.sin(self.t * 0.06) * 2.2
            self.fire_cd -= 1
            if self.fire_cd <= 0 and self.y < H * 0.6:
                game.enemy_fire(self.x, self.y, *aim(self.x, self.y, p.x, p.y, bspeed))
                self.fire_cd = random.randint(90, 160)

        elif k == "hook":
            if self.phase == 0:
                self.y += 4.0
                if self.y > H * 0.38:
                    self.phase = 1
                    self.vx = 4.2 if p.x > self.x else -4.2
                    self.vy = 0.0
                    game.enemy_fire(self.x, self.y, *aim(self.x, self.y, p.x, p.y, bspeed + 0.5))
            else:
                self.vy = max(self.vy - 0.12, -5)
                self.x += self.vx
                self.y += self.vy

        elif k == "ring":
            if self.phase == 0:
                self.y += (self.stop_y - self.y) * 0.04 + 0.3
                if self.y >= self.stop_y - 2:
                    self.phase, self.t = 1, 0
            elif self.phase == 1:
                if self.t % 45 == 20:
                    n = 8 + self.stage
                    off = self.t * 0.05
                    for i in range(n):
                        a = off + math.tau * i / n
                        game.enemy_fire(self.x, self.y, math.cos(a) * bspeed * 0.8,
                                        math.sin(a) * bspeed * 0.8)
                if self.t > 200:
                    self.phase = 2
            else:
                self.y += 5

        elif k == "sweeper":
            self.x += self.vx
            self.y = self.base_y + math.sin(self.t * 0.07) * 24
            self.fire_cd -= 1
            if self.fire_cd <= 0 and 0 < self.x < W:
                game.enemy_fire(self.x, self.y, 0, bspeed * 0.9)
                self.fire_cd = random.randint(60, 110)

        elif k == "zip":
            if self.phase == 0:         # 등장
                target_y = self.stop_y * 0.5
                self.y += (target_y - self.y) * 0.08 + 0.5
                self.angle = math.atan2(p.y - self.y, p.x - self.x)
                if self.y >= target_y - 3:
                    self.phase, self.t = 1, 0
            elif self.phase == 1:       # 조준 (경고선 표시)
                self.angle = math.atan2(p.y - self.y, p.x - self.x)
                if self.t >= 45:
                    self.phase = 2
                    sp = 8 + 0.5 * self.stage
                    self.vx, self.vy = math.cos(self.angle) * sp, math.sin(self.angle) * sp
            else:                       # 돌진
                self.x += self.vx
                self.y += self.vy

        elif k == "splitter":
            self.y += 1.6
            self.x += math.sin(self.t * 0.03) * 1.2
            self.fire_cd -= 1
            if self.fire_cd <= 0 and self.y < H * 0.6:
                game.enemy_fire(self.x, self.y, *aim(self.x, self.y, p.x, p.y, bspeed))
                self.fire_cd = random.randint(70, 110)

        elif k == "mini":
            self.x += self.vx
            self.y += self.vy

        elif k == "bomber":
            self.y += 0.7 if self.y < H * 0.45 else 1.4
            self.x += math.sin(self.t * 0.015) * 0.6
            self.fire_cd -= 1
            if self.fire_cd <= 0 and self.y > 20:
                base = math.atan2(p.y - self.y, p.x - self.x)
                for i in (-1, 0, 1):
                    a = base + i * 0.3
                    game.enemy_fire(self.x, self.y + 20, math.cos(a) * bspeed, math.sin(a) * bspeed)
                self.fire_cd = max(40, 75 - self.stage * 5)

        on_screen = -40 < self.x < W + 40 and -40 < self.y < H + 40
        self.entered = self.entered or on_screen
        if (self.entered and not on_screen) or self.t > 1800:
            self.dead = True

    def draw(self, surf, frame):
        x, y = int(self.x), int(self.y)
        white = self.flash > 0
        k = self.kind
        if k == "dart":
            pygame.draw.polygon(surf, WHITE if white else (200, 70, 70),
                                [(x, y + 14), (x - 12, y - 10), (x, y - 4), (x + 12, y - 10)])
            pygame.draw.circle(surf, YELLOW, (x, y), 3)
        elif k == "hook":
            pygame.draw.polygon(surf, WHITE if white else (210, 140, 50),
                                [(x, y + 14), (x - 15, y), (x - 8, y - 12), (x + 8, y - 12), (x + 15, y)])
            pygame.draw.circle(surf, (80, 30, 20), (x, y), 5)
        elif k == "ring":
            a = frame * 0.08
            pygame.draw.circle(surf, WHITE if white else (150, 90, 210), (x, y), self.r)
            pygame.draw.circle(surf, DARK, (x, y), self.r - 6)
            for i in range(4):
                ang = a + i * math.pi / 2
                px, py = x + math.cos(ang) * (self.r - 3), y + math.sin(ang) * (self.r - 3)
                pygame.draw.circle(surf, PINK, (int(px), int(py)), 3)
        elif k == "sweeper":
            body = WHITE if white else (40, 170, 160)
            pygame.draw.polygon(surf, body, [(x - 17, y - 5), (x + 17, y - 5), (x + 8, y + 7), (x - 8, y + 7)])
            pygame.draw.circle(surf, (20, 70, 70), (x, y), 5)
            pygame.draw.circle(surf, CYAN, (x, y), 2)
        elif k == "zip":
            a = self.angle
            pts = [(x + math.cos(a) * 15, y + math.sin(a) * 15),
                   (x + math.cos(a + 2.5) * 11, y + math.sin(a + 2.5) * 11),
                   (x + math.cos(a + math.pi) * 4, y + math.sin(a + math.pi) * 4),
                   (x + math.cos(a - 2.5) * 11, y + math.sin(a - 2.5) * 11)]
            blink = self.phase == 1 and (frame // 4) % 2
            pygame.draw.polygon(surf, WHITE if (white or blink) else (190, 220, 60), pts)
            if self.phase == 1:     # 돌진 경고선
                ex, ey = x + math.cos(a) * 90, y + math.sin(a) * 90
                pygame.draw.line(surf, RED, (x, y), (int(ex), int(ey)), 1)
        elif k == "splitter":
            a = frame * 0.05
            col = WHITE if white else (230, 100, 60)
            for i in range(3):
                ang = a + i * math.tau / 3
                pygame.draw.circle(surf, col, (int(x + math.cos(ang) * 7), int(y + math.sin(ang) * 7)), 9)
            pygame.draw.circle(surf, YELLOW, (x, y), 4)
        elif k == "mini":
            pygame.draw.polygon(surf, WHITE if white else (230, 100, 60),
                                [(x, y + 8), (x - 7, y - 6), (x + 7, y - 6)])
        elif k == "bomber":
            hull = WHITE if white else (110, 120, 95)
            pygame.draw.polygon(surf, hull, [(x - 46, y - 6), (x + 46, y - 6), (x + 30, y + 8), (x - 30, y + 8)])
            pygame.draw.ellipse(surf, hull, (x - 10, y - 30, 20, 60))
            pygame.draw.polygon(surf, hull, [(x - 18, y - 26), (x + 18, y - 26), (x + 10, y - 18), (x - 10, y - 18)])
            for dx in (-26, 26):
                pygame.draw.rect(surf, (60, 65, 55), (x + dx - 5, y - 2, 10, 16))
                pygame.draw.circle(surf, ORANGE, (x + dx, y + 15), 3)
            pygame.draw.circle(surf, (40, 60, 90), (x, y + 18), 5)
            if self.hp < self.max_hp:
                pygame.draw.rect(surf, DARK, (x - 25, y - 40, 50, 5))
                pygame.draw.rect(surf, RED, (x - 25, y - 40, int(50 * self.hp / self.max_hp), 5))


def river_x(terrain_y):
    """지형 텍스처 좌표 y 에서 강 중심의 x 좌표 (build_terrain 과 같은 식)."""
    k = 2 * math.pi / TERRAIN_H
    return W / 2 + math.sin(terrain_y * k * 2) * 130 + math.sin(terrain_y * k * 7) * 30


class GroundEnemy:
    """지상 적: 폭탄으로만 파괴 가능. 지형과 함께 스크롤된다."""
    STATS = {  # kind: (hp, score, radius)
        "turret": (1, 300, 14),     # 고정 포대, 조준 사격
        "bunker": (2, 600, 18),     # 단단한 벙커, 아이템을 자주 떨어뜨림
        "tank": (1, 400, 14),       # 좌우로 움직이며 조준 사격
        "launcher": (2, 700, 16),   # 유도 미사일 발사 (샷으로 요격 가능)
        "radar": (2, 1000, 18),     # 살아 있는 동안 돌진형 적(zip)을 불러옴, 파괴하면 아이템 확정
        "boat": (1, 500, 13),       # 강을 거슬러 올라가며 2갈래 탄
    }

    def __init__(self, kind, x, stage):
        self.kind = kind
        self.x, self.y = x, -30
        self.hp, self.score, self.r = self.STATS[kind]
        self.stage = stage
        self.dead = False
        self.destroyed = False
        self.flash = 0
        self.t = 0
        self.fire_cd = random.randint(60, 120)
        self.gun_angle = math.pi / 2
        self.spin = 0.0
        self.vx = random.choice((-1, 1)) * (0.6 + 0.1 * stage) if kind == "tank" else 0.0

    def update(self, game):
        self.t += 1
        self.y += game.scroll
        self.flash = max(0, self.flash - 1)
        if self.y > H + 40:
            self.dead = True
        if self.destroyed:
            return
        p = game.player
        k = self.kind

        if k == "boat":   # 강을 따라 상류로 이동
            self.y -= 0.5
            self.x = river_x((self.y - game.scroll_y) % TERRAIN_H)

        if k in ("turret", "tank"):
            if k == "tank":
                self.x += self.vx
                if not 25 < self.x < W - 25:
                    self.vx = -self.vx
            self.gun_angle = math.atan2(p.y - self.y, p.x - self.x)
            self.fire_cd -= 1
            if self.fire_cd <= 0 and 20 < self.y < p.y - 80:
                sp = 2.6 + 0.3 * self.stage
                game.enemy_fire(self.x, self.y, math.cos(self.gun_angle) * sp, math.sin(self.gun_angle) * sp)
                self.fire_cd = max(50, random.randint(100, 150) - self.stage * 8)

        elif k == "launcher":
            self.fire_cd -= 1
            if self.fire_cd <= 0 and 30 < self.y < p.y - 150:
                game.enemy_fire(self.x, self.y, *aim(self.x, self.y, p.x, p.y, 2.0),
                                homing=100, shootable=True)
                game.sfx.play("missile", min_gap=10)
                self.fire_cd = max(110, 200 - self.stage * 15)

        elif k == "radar":
            self.spin += 0.06
            self.fire_cd -= 1
            if self.fire_cd <= 0 and 0 < self.y < H * 0.6:
                game.air.append(AirEnemy("zip", random.randint(40, W - 40), -20, self.stage))
                self.fire_cd = 200

        elif k == "boat":
            self.fire_cd -= 1
            if self.fire_cd <= 0 and 20 < self.y < p.y - 80:
                base = math.atan2(p.y - self.y, p.x - self.x)
                sp = 2.6 + 0.2 * self.stage
                for d in (-0.3, 0.3):
                    game.enemy_fire(self.x, self.y, math.cos(base + d) * sp, math.sin(base + d) * sp)
                self.fire_cd = max(70, 120 - self.stage * 8)

    def draw(self, surf):
        x, y = int(self.x), int(self.y)
        if self.destroyed:   # 파괴된 잔해
            pygame.draw.circle(surf, (40, 35, 30), (x, y), self.r)
            pygame.draw.circle(surf, (70, 60, 50), (x - 3, y - 2), self.r // 2)
            return
        flash = self.flash > 0
        k = self.kind
        if k == "turret":
            pygame.draw.circle(surf, WHITE if flash else (110, 110, 120), (x, y), self.r)
            pygame.draw.circle(surf, (70, 70, 80), (x, y), self.r - 5)
            ex = x + math.cos(self.gun_angle) * 16
            ey = y + math.sin(self.gun_angle) * 16
            pygame.draw.line(surf, (40, 40, 45), (x, y), (int(ex), int(ey)), 5)
        elif k == "bunker":
            rect = pygame.Rect(x - self.r, y - self.r, self.r * 2, self.r * 2)
            pygame.draw.rect(surf, WHITE if flash else (150, 130, 90), rect)
            pygame.draw.rect(surf, (90, 75, 50), rect, 3)
            pygame.draw.rect(surf, RED, (x - 4, y - 4, 8, 8))
        elif k == "tank":
            pygame.draw.rect(surf, (45, 50, 35), (x - 15, y - 12, 30, 5))       # 궤도
            pygame.draw.rect(surf, (45, 50, 35), (x - 15, y + 7, 30, 5))
            pygame.draw.rect(surf, WHITE if flash else (120, 130, 70), (x - 13, y - 8, 26, 16))
            ex = x + math.cos(self.gun_angle) * 17
            ey = y + math.sin(self.gun_angle) * 17
            pygame.draw.line(surf, (40, 45, 30), (x, y), (int(ex), int(ey)), 4)
            pygame.draw.circle(surf, (90, 100, 50), (x, y), 6)
        elif k == "launcher":
            rect = pygame.Rect(x - 15, y - 15, 30, 30)
            pygame.draw.rect(surf, WHITE if flash else (100, 100, 110), rect, border_radius=4)
            ready = self.fire_cd < 30 and (self.t // 4) % 2
            for dx in (-6, 6):
                pygame.draw.rect(surf, (50, 50, 55), (x + dx - 4, y - 10, 8, 20))
                pygame.draw.circle(surf, YELLOW if ready else RED, (x + dx, y - 8), 3)
        elif k == "radar":
            pygame.draw.circle(surf, WHITE if flash else (130, 140, 150), (x, y), self.r)
            pygame.draw.circle(surf, (80, 90, 100), (x, y), self.r - 4)
            a = self.spin
            dish = [(x + math.cos(a + d) * 16, y + math.sin(a + d) * 16) for d in (-0.7, -0.3, 0.3, 0.7)]
            pygame.draw.polygon(surf, (220, 225, 230), [(x, y)] + dish)
            pygame.draw.circle(surf, RED if (self.t // 15) % 2 else (120, 30, 30), (x, y), 3)
        elif k == "boat":
            for i in range(1, 4):   # 물결 자국
                pygame.draw.line(surf, (200, 225, 255), (x - 4 - i * 2, y + 14 + i * 5), (x + 4 + i * 2, y + 14 + i * 5), 1)
            hull = [(x, y - 17), (x - 8, y - 5), (x - 8, y + 14), (x + 8, y + 14), (x + 8, y - 5)]
            pygame.draw.polygon(surf, WHITE if flash else (150, 150, 160), hull)
            pygame.draw.polygon(surf, (70, 70, 80), hull, 2)
            pygame.draw.circle(surf, (60, 60, 70), (x, y + 2), 5)


class Boss:
    """스테이지 끝에 등장하는 공중 요새. 샷으로 공격."""

    def __init__(self, stage):
        self.stage = stage
        self.x, self.y = W / 2, -90
        self.max_hp = self.hp = 120 + stage * 60
        self.r = 46
        self.t = 0
        self.flash = 0
        self.dead = False
        self.pattern = 0

    def update(self, game):
        self.t += 1
        self.flash = max(0, self.flash - 1)
        if self.y < 130:
            self.y += 1.2
            return
        self.x = W / 2 + math.sin(self.t * 0.012) * 150
        p = game.player
        sp = 2.8 + 0.3 * self.stage
        cycle = self.t % 480
        self.pattern = cycle // 160
        if self.pattern == 0 and self.t % 50 == 0:        # 조준 부채꼴
            base = math.atan2(p.y - self.y, p.x - self.x)
            for i in range(-2, 3):
                a = base + i * 0.22
                game.enemy_fire(self.x, self.y + 30, math.cos(a) * sp, math.sin(a) * sp)
        elif self.pattern == 1 and self.t % 7 == 0:       # 나선
            for k in (0, math.pi):
                a = self.t * 0.13 + k
                game.enemy_fire(self.x, self.y, math.cos(a) * sp * 0.8, math.sin(a) * sp * 0.8)
        elif self.pattern == 2 and self.t % 40 == 0:      # 원형 탄막
            n = 14 + self.stage * 2
            for i in range(n):
                a = math.tau * i / n + (self.t % 80) * 0.02
                game.enemy_fire(self.x, self.y, math.cos(a) * sp * 0.7, math.sin(a) * sp * 0.7)

    def draw(self, surf, frame):
        x, y = int(self.x), int(self.y)
        hull = WHITE if self.flash else (90, 95, 120)
        pygame.draw.polygon(surf, hull, [(x - 80, y - 10), (x - 40, y - 40), (x + 40, y - 40),
                                         (x + 80, y - 10), (x + 50, y + 30), (x - 50, y + 30)])
        pygame.draw.polygon(surf, (60, 62, 85), [(x - 60, y - 8), (x - 32, y - 28), (x + 32, y - 28),
                                                 (x + 60, y - 8), (x + 38, y + 18), (x - 38, y + 18)])
        for dx in (-55, 55):
            pygame.draw.circle(surf, (50, 50, 60), (x + dx, y + 4), 10)
            pygame.draw.circle(surf, ORANGE, (x + dx, y + 4), 4)
        glow = 120 + int(100 * abs(math.sin(frame * 0.08)))
        pygame.draw.circle(surf, (glow, 30, 60), (x, y), 16)
        pygame.draw.circle(surf, WHITE, (x, y), 16, 2)


# ===================== 게임 =====================
class Game:
    def __init__(self):
        pygame.mixer.pre_init(SoundFX.RATE, -16, 1, 512)   # 효과음 지연을 줄이기 위해 작은 버퍼
        pygame.init()
        self.sfx = SoundFX()
        pygame.display.set_caption("SKY RAIDER")
        self.screen = pygame.display.set_mode((W, H))
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 26)
        self.big_font = pygame.font.Font(None, 64)
        self.small_font = pygame.font.Font(None, 22)
        self.terrain = build_terrain()
        self.overlay = pygame.Surface((W, H), pygame.SRCALPHA)
        self.hi_score = 0
        self.state = "title"
        self.frame = 0
        self.new_game()

    # ----- 상태 초기화 -----
    def new_game(self):
        self.score = 0
        self.lives = START_LIVES
        self.stage = 1
        self.player = Player()
        self.powerups = []          # 스테이지가 바뀌어도 화면의 아이템은 유지
        self.medal_value = 500
        self.start_stage()

    def start_stage(self):
        self.scroll = BASE_SCROLL + (self.stage - 1) * 0.25
        self.scroll_y = 0.0
        self.stage_timer = 0
        self.shots, self.bombs, self.ebullets = [], [], []
        self.air, self.ground, self.particles = [], [], []
        self.missiles, self.popups = [], []
        self.flash = 0      # 클리어 아이템 화면 번쩍임
        self.boss = None
        self.boss_defeated_timer = 0
        self.air_cd = 90
        self.ground_cd = 60
        self.banner = 150   # "STAGE N" 표시 시간
        self.paused = False
        self.sfx.play_music("stage")

    def enemy_fire(self, x, y, vx, vy, **kw):
        self.ebullets.append(EnemyBullet(x, y, vx, vy, target=self.player, **kw))

    # (종류, 가중치, 등장 시작 스테이지) — 가중치가 클수록 자주 나옴
    AIR_SPAWN = [("dart", 5, 1), ("hook", 3, 1), ("sweeper", 3, 1), ("zip", 2, 1),
                 ("splitter", 2, 1), ("ring", 1, 1), ("bomber", 1, 1)]
    GROUND_SPAWN = [("turret", 5, 1), ("tank", 3, 1), ("bunker", 2, 1), ("boat", 2, 1),
                    ("launcher", 2, 1), ("radar", 1, 1)]

    @staticmethod
    def pick(table, stage, bonus=None):
        bonus = bonus or {}
        rows = [(k, w + bonus.get(k, 0)) for k, w, min_stage in table if stage >= min_stage]
        return random.choices([k for k, _ in rows], weights=[w for _, w in rows])[0]

    # ----- 스폰 -----
    def spawn(self):
        s = self.stage
        if self.boss is None and self.stage_timer >= BOSS_TIME:
            self.boss = Boss(s)
            self.banner = 0
            self.sfx.stop_music(300)
            self.sfx.play("warning")
            return
        boss_active = self.boss is not None

        self.air_cd -= 1
        if self.air_cd <= 0:
            if boss_active:
                self.air_cd = 160
                kind = "dart"
            else:
                self.air_cd = max(22, 70 - s * 8) + random.randint(0, 30)
                kind = self.pick(self.AIR_SPAWN, s, {"ring": s // 2, "bomber": s // 3})
                if kind == "bomber" and any(e.kind == "bomber" for e in self.air):
                    kind = "dart"       # 폭격기는 한 번에 한 대만
            if kind == "dart" and random.random() < 0.5:   # 3기 편대
                x = random.randint(60, W - 60)
                for i in range(3):
                    self.air.append(AirEnemy("dart", x + (i - 1) * 34, -20 - abs(i - 1) * 30, s))
            elif kind == "sweeper":                         # 옆에서 4기 편대
                side = random.choice((-1, 1))
                base_y = random.randint(70, 220)
                for i in range(4):
                    x = -20 - i * 40 if side < 0 else W + 20 + i * 40
                    self.air.append(AirEnemy("sweeper", x, base_y, s, vx=-side * (2.4 + 0.2 * s)))
            elif kind == "bomber":
                self.air.append(AirEnemy("bomber", random.randint(90, W - 90), -40, s))
            else:
                self.air.append(AirEnemy(kind, random.randint(40, W - 40), -30, s))

        if not boss_active:
            self.ground_cd -= 1
            if self.ground_cd <= 0:
                self.ground_cd = max(50, 120 - s * 10) + random.randint(0, 40)
                kind = self.pick(self.GROUND_SPAWN, s, {"launcher": s - 1})
                if kind == "radar" and any(g.kind == "radar" and not g.destroyed for g in self.ground):
                    kind = "turret"     # 레이더는 한 번에 하나만
                if kind == "boat":      # 보트는 강 위에 배치
                    x = river_x((-30 - self.scroll_y) % TERRAIN_H)
                else:
                    x = random.randint(30, W - 30)
                self.ground.append(GroundEnemy(kind, x, s))

    # ----- 피격 -----
    def hit_player(self):
        p = self.player
        if p.invuln:
            return
        if p.shield:        # 실드가 대신 맞아 줌
            p.shield = False
            p.invuln = 90
            self.sfx.play("shield_break")
            for _ in range(24):
                self.particles.append(Particle(p.x, p.y, CYAN, 5, 30, 3))
            for bl in self.ebullets:
                if dist2(bl.x, bl.y, p.x, p.y) < 90 ** 2:
                    bl.dead = True
            return
        p.homing = 0
        p.speed_lv = max(0, p.speed_lv - 1)
        self.medal_value = 500
        explode(self.particles, p.x, p.y, 40, big=True)
        self.sfx.play("big_explode")
        self.lives -= 1
        if self.lives <= 0:
            self.state = "gameover"
            self.hi_score = max(self.hi_score, self.score)
            self.sfx.stop_music(300)
            self.sfx.play("game_over")
            return
        p.x, p.y = W / 2, H - 110
        p.invuln = 150
        p.power = max(1, p.power - 1)
        self.ebullets.clear()

    def add_score(self, n):
        self.score += n
        self.hi_score = max(self.hi_score, self.score)

    # ----- 업데이트 -----
    def update(self):
        keys = pygame.key.get_pressed()
        p = self.player
        self.stage_timer += 1
        self.banner = max(0, self.banner - 1)
        self.scroll_y = (self.scroll_y + self.scroll) % TERRAIN_H

        p.update(keys)
        if keys[pygame.K_z] or keys[pygame.K_j] or keys[pygame.K_SPACE]:
            if p.shoot(self.shots):
                self.sfx.play("shot")
            if p.fire_missiles(self.missiles):
                self.sfx.play("missile")
        if keys[pygame.K_x] or keys[pygame.K_k]:
            if p.drop_bomb(self.bombs):
                self.sfx.play("bomb_drop")

        self.spawn()

        for o in self.shots + self.ebullets:
            o.update()
        targets = [(e.x, e.y) for e in self.air if e.y > 0]
        if self.boss and self.boss.y > 0:
            targets.append((self.boss.x, self.boss.y))
        for m in self.missiles:
            m.update(targets)
        for pp in self.popups:
            pp.update()
        self.flash = max(0, self.flash - 1)
        for b in self.bombs:
            b.update(self.scroll)
        for e in self.air + self.ground:
            e.update(self)
        for pu in self.powerups:
            pu.update(self.scroll, p)
        if self.boss:
            self.boss.update(self)
            if self.boss.t == 90:          # 경보음이 끝나면 보스 음악 시작
                self.sfx.play_music("boss", fade_ms=200)
        for pt in self.particles:
            pt.update()

        self.collisions()

        # 보스 격파 후 다음 스테이지
        if self.boss_defeated_timer:
            self.boss_defeated_timer -= 1
            if self.boss_defeated_timer == 110:
                self.sfx.play("stage_clear")
            if self.boss_defeated_timer == 0:
                self.stage += 1
                self.start_stage()
                return

        self.shots = [o for o in self.shots if not o.dead]
        self.missiles = [o for o in self.missiles if not o.dead]
        self.popups = [o for o in self.popups if o.life > 0]
        self.ebullets = [o for o in self.ebullets if not o.dead]
        self.bombs = [b for b in self.bombs if not b.done]
        self.air = [e for e in self.air if not e.dead]
        self.ground = [e for e in self.ground if not e.dead]
        self.powerups = [o for o in self.powerups if not o.dead]
        self.particles = [o for o in self.particles if o.life > 0]

    def collisions(self):
        p = self.player

        # 샷 / 유도 미사일 vs 공중 적 / 보스
        for s in self.shots + self.missiles:
            for e in self.air:
                if not e.dead and dist2(s.x, s.y, e.x, e.y) < (e.r + 4) ** 2:
                    s.dead = True
                    self.hurt_air(e, s.dmg)
                    break
            b = self.boss
            if not s.dead and b and not b.dead and b.y > 0 and abs(s.x - b.x) < 75 and abs(s.y - b.y) < 35:
                s.dead = True
                if random.random() < 0.3:
                    self.particles.append(Particle(s.x, s.y, YELLOW, 2, 12, 3))
                self.hurt_boss(s.dmg)

        # 폭탄 착탄 vs 지상 적
        for bomb in self.bombs:
            if not bomb.landed:
                continue
            tx, ty = bomb.tx, bomb.ty
            self.sfx.play("bomb_hit")
            for _ in range(12):
                self.particles.append(Particle(tx, ty, random.choice((ORANGE, GREY, YELLOW)), 3, 25, 5))
            for g in self.ground:
                if not g.destroyed and dist2(tx, ty, g.x, g.y) < (g.r + 20) ** 2:
                    g.hp -= 1
                    g.flash = 6
                    if g.hp <= 0:
                        g.destroyed = True
                        self.add_score(g.score)
                        explode(self.particles, g.x, g.y, 26)
                        self.sfx.play("explode", min_gap=3)
                        if random.random() < self.GROUND_DROP_CHANCE.get(g.kind, 0):
                            self.powerups.append(Item(g.x, g.y))

        # 샷 / 유도 미사일로 적 미사일 요격
        for s in self.shots + self.missiles:
            if s.dead:
                continue
            for bl in self.ebullets:
                if bl.shootable and not bl.dead and dist2(s.x, s.y, bl.x, bl.y) < 12 ** 2:
                    s.dead = bl.dead = True
                    self.add_score(30)
                    explode(self.particles, bl.x, bl.y, 8)
                    break

        # 플레이어 피격
        if not p.invuln:
            for bl in self.ebullets:
                if dist2(bl.x, bl.y, p.x, p.y) < (bl.r + p.r - 4) ** 2:
                    bl.dead = True
                    self.hit_player()
                    return
            for e in self.air:
                if dist2(e.x, e.y, p.x, p.y) < (e.r + p.r) ** 2:
                    if e.kind != "bomber":     # 폭격기는 부딪혀도 부서지지 않음
                        e.dead = True
                        explode(self.particles, e.x, e.y, 20)
                        self.sfx.play("explode")
                    self.hit_player()
                    return
            b = self.boss
            if b and abs(p.x - b.x) < 70 and abs(p.y - b.y) < 30:
                self.hit_player()
                return

        # 아이템 획득
        for pu in self.powerups:
            if not pu.dead and dist2(pu.x, pu.y, p.x, p.y) < 24 ** 2:
                pu.dead = True
                self.collect(pu)

    # 공중 적이 격추될 때 아이템을 떨어뜨릴 확률
    AIR_DROP_CHANCE = {"dart": 0.03, "hook": 0.08, "ring": 0.35, "sweeper": 0.05, "zip": 0.04,
                       "splitter": 0.15, "mini": 0.0, "bomber": 0.7}
    GROUND_DROP_CHANCE = {"bunker": 0.6, "radar": 1.0, "launcher": 0.2, "tank": 0.05}

    def hurt_air(self, e, dmg):
        e.hp -= dmg
        e.flash = 4
        if e.hp > 0:
            self.sfx.play("enemy_hit", min_gap=4)
            return
        e.dead = True
        self.add_score(e.score)
        explode(self.particles, e.x, e.y, 40 if e.kind == "bomber" else 22, big=e.kind == "bomber")
        self.sfx.play("big_explode" if e.kind == "bomber" else "explode", min_gap=3)
        if e.kind == "splitter":    # 분열: 작은 적 3개가 아래쪽 부채꼴로 흩어짐
            for a in (math.pi / 2 - 0.7, math.pi / 2, math.pi / 2 + 0.7):
                self.air.append(AirEnemy("mini", e.x, e.y, e.stage,
                                         vx=math.cos(a) * 3.2, vy=math.sin(a) * 3.2))
        if random.random() < self.AIR_DROP_CHANCE[e.kind] and 0 < e.y < H - 60:
            self.powerups.append(Item(e.x, e.y))

    def hurt_boss(self, dmg):
        b = self.boss
        b.hp -= dmg
        b.flash = 3
        self.sfx.play("hit", min_gap=5)
        if b.hp <= 0:
            self.defeat_boss()

    def collect(self, item):
        p, k = self.player, item.kind
        bonus = None
        if k == "P":
            if p.power < 3:
                p.power += 1
                text = "POWER UP"
            else:
                bonus = 1000
        elif k == "S":
            if p.speed_lv < 2:
                p.speed_lv += 1
                text = "SPEED UP"
            else:
                bonus = 1000
        elif k == "H":
            p.homing = 12 * FPS
            text = "HOMING MISSILE"
        elif k == "O":
            if not p.shield:
                p.shield = True
                text = "SHIELD"
            else:
                bonus = 1000
        elif k == "C":
            self.clear_screen()
            text = "CLEAR!"
        elif k == "*":
            bonus = self.medal_value
            self.medal_value = min(8000, self.medal_value * 2)
        else:  # 1UP
            self.lives = min(9, self.lives + 1)
            text = "1UP!"

        if bonus is not None:
            self.add_score(bonus)
            text = f"+{bonus}"
        sound = {"*": "medal", "1UP": "oneup", "C": "clear"}.get(k, "powerup")
        if bonus is not None and k != "*":
            sound = "medal"
        self.sfx.play(sound)
        self.popups.append(Popup(text, item.x, item.y - 16, ITEM_TYPES[k][1] if k != "*" else YELLOW))

    def clear_screen(self):
        """클리어 아이템: 적 탄을 모두 점수로 바꾸고 공중 적에게 피해."""
        self.flash = 18
        for bl in self.ebullets:
            self.particles.append(Particle(bl.x, bl.y, YELLOW, 1.5, 20, 3))
            self.add_score(10)
        self.ebullets.clear()
        for e in self.air:
            if not e.dead and e.y > 0:
                self.hurt_air(e, 5)
        if self.boss and self.boss.y > 0:
            self.hurt_boss(20)

    def defeat_boss(self):
        b = self.boss
        b.dead = True
        self.add_score(5000 * self.stage)
        # 보스 보상 아이템 3개
        rewards = ["P", "1UP" if random.random() < 0.35 else "*", random_item_kind()]
        for dx, kind in zip((-45, 0, 45), rewards):
            self.powerups.append(Item(b.x + dx, b.y + 20, kind))
        self.sfx.stop_music(800)
        self.sfx.play("big_explode")
        for i in range(6):
            explode(self.particles, b.x + random.randint(-60, 60), b.y + random.randint(-25, 25), 30, big=True)
        self.boss = None
        self.ebullets.clear()
        self.stage_timer = -10 ** 9   # 다음 스테이지 전까지 보스 재등장 방지
        self.boss_defeated_timer = 180

    # ----- 그리기 -----
    def draw_background(self):
        y0 = int(self.scroll_y)
        self.screen.blit(self.terrain, (0, y0 - TERRAIN_H))
        self.screen.blit(self.terrain, (0, y0))

    def draw_text(self, text, font, color, center):
        img = font.render(text, True, color)
        self.screen.blit(img, img.get_rect(center=center))

    def draw_hud(self):
        self.draw_text(f"SCORE {self.score:08d}", self.font, WHITE, (110, 18))
        self.draw_text(f"HI {self.hi_score:08d}", self.font, YELLOW, (W - 100, 18))
        for i in range(self.lives - 1):
            x, y = 18 + i * 22, H - 18
            pygame.draw.polygon(self.screen, WHITE, [(x, y - 9), (x - 8, y + 7), (x + 8, y + 7)])
        self.draw_text(f"STAGE {self.stage}   PWR {'I' * self.player.power}", self.small_font,
                       WHITE, (W - 90, H - 16))
        if self.sfx.muted:
            self.draw_text("SOUND OFF", self.small_font, GREY, (W // 2, H - 16))
        elif not self.sfx.music_on:
            self.draw_text("MUSIC OFF", self.small_font, GREY, (W // 2, H - 16))

        # 활성화된 아이템 효과 표시
        p = self.player
        x = 12
        status = []
        if p.speed_lv:
            status.append((f"SPD {'I' * p.speed_lv}", ITEM_TYPES["S"][1]))
        if p.shield:
            status.append(("SHIELD", ITEM_TYPES["O"][1]))
        if p.homing:
            status.append((f"HOMING {p.homing // FPS + 1}s", ITEM_TYPES["H"][1]))
        for text, color in status:
            img = self.small_font.render(text, True, WHITE)
            box = pygame.Rect(x, H - 50, img.get_width() + 10, 18)
            pygame.draw.rect(self.screen, color, box, border_radius=4)
            self.screen.blit(img, (x + 5, H - 48))
            x += box.width + 6
        if self.boss:
            ratio = self.boss.hp / self.boss.max_hp
            pygame.draw.rect(self.screen, DARK, (40, 38, W - 80, 10))
            pygame.draw.rect(self.screen, RED, (40, 38, int((W - 80) * ratio), 10))
            pygame.draw.rect(self.screen, WHITE, (40, 38, W - 80, 10), 1)
        if self.banner:
            self.draw_text(f"STAGE {self.stage}", self.big_font, WHITE, (W // 2, H // 2 - 40))
            self.draw_text("Z: SHOT (AIR)    X: BOMB (GROUND)", self.small_font, WHITE, (W // 2, H // 2 + 10))
        if self.boss_defeated_timer:
            self.draw_text("STAGE CLEAR!", self.big_font, YELLOW, (W // 2, H // 2 - 40))

    def draw_reticle(self):
        rx, ry = self.player.reticle
        on_target = any(not g.destroyed and dist2(rx, ry, g.x, g.y) < (g.r + 20) ** 2 for g in self.ground)
        color = RED if on_target and (self.frame // 5) % 2 else WHITE
        r = 14
        pygame.draw.circle(self.screen, color, (int(rx), int(ry)), r, 2)
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            pygame.draw.line(self.screen, color, (rx + dx * (r - 5), ry + dy * (r - 5)),
                             (rx + dx * (r + 5), ry + dy * (r + 5)), 2)

    def draw_world(self):
        self.draw_background()
        for g in self.ground:
            g.draw(self.screen)
        for pu in self.powerups:
            pu.draw(self.screen, self.small_font, self.frame)
        if self.state == "play":
            self.draw_reticle()
        for b in self.bombs:
            b.draw(self.screen)
        if self.boss:
            self.boss.draw(self.screen, self.frame)
        for e in self.air:
            e.draw(self.screen, self.frame)
        for s in self.shots + self.missiles:
            s.draw(self.screen)
        if self.state == "play":
            self.player.draw(self.screen, self.frame)
        for pt in self.particles:
            pt.draw(self.screen)
        for bl in self.ebullets:
            bl.draw(self.screen, self.frame)
        for pp in self.popups:
            img = self.small_font.render(pp.text, True, pp.color)
            outline = self.small_font.render(pp.text, True, DARK)
            r = img.get_rect(center=(int(pp.x), int(pp.y)))
            self.screen.blit(outline, r.move(1, 1))
            self.screen.blit(img, r)
        if self.flash:
            self.overlay.fill((255, 255, 255, self.flash * 12))
            self.screen.blit(self.overlay, (0, 0))

    def dim(self, alpha=150):
        self.overlay.fill((0, 0, 0, alpha))
        self.screen.blit(self.overlay, (0, 0))

    def draw(self):
        self.draw_world()
        if self.state == "title":
            self.dim(120)
            self.draw_text("SKY RAIDER", self.big_font, CYAN, (W // 2, H // 5))
            lines = ["ARROWS / WASD : MOVE", "Z / SPACE : SHOT  (air enemies)",
                     "X : BOMB  (ground targets)", "P : PAUSE   ESC : QUIT", "M : ALL SOUND   B : MUSIC", "",
                     "PRESS ENTER TO START"]
            for i, line in enumerate(lines):
                col = YELLOW if "ENTER" in line and (self.frame // 30) % 2 else WHITE
                self.draw_text(line, self.font, col, (W // 2, H // 5 + 80 + i * 30))
            # 아이템 설명 (실제 아이템 그림과 함께)
            legend = [("P", "POWER UP SHOT"), ("S", "SPEED UP"), ("H", "HOMING MISSILES (12s)"),
                      ("O", "SHIELD (blocks 1 hit)"), ("C", "CLEAR ENEMY BULLETS"),
                      ("*", "MEDAL (bonus doubles)"), ("1UP", "EXTRA LIFE")]
            top = H // 5 + 80 + len(lines) * 30 + 10
            self.draw_text("- ITEMS -", self.font, YELLOW, (W // 2, top))
            for i, (kind, desc) in enumerate(legend):
                y = top + 32 + i * 28
                Item(W // 2 - 110, y, kind).draw(self.screen, self.small_font, self.frame)
                img = self.small_font.render(desc, True, WHITE)
                self.screen.blit(img, (W // 2 - 80, y - img.get_height() // 2))
        elif self.state == "gameover":
            self.draw_hud()
            self.dim()
            self.draw_text("GAME OVER", self.big_font, RED, (W // 2, H // 2 - 40))
            self.draw_text(f"SCORE {self.score}", self.font, WHITE, (W // 2, H // 2 + 10))
            self.draw_text("PRESS ENTER TO RETRY", self.font, YELLOW, (W // 2, H // 2 + 50))
        else:
            self.draw_hud()
            if self.paused:
                self.dim(100)
                self.draw_text("PAUSED", self.big_font, WHITE, (W // 2, H // 2))
        pygame.display.flip()

    # ----- 메인 루프 -----
    def run(self):
        while True:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return
                    if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.state != "play":
                        self.new_game()
                        self.state = "play"
                        self.sfx.play("start")
                    elif event.key == pygame.K_p and self.state == "play":
                        self.paused = not self.paused
                        if self.sfx.enabled:
                            if self.paused:
                                pygame.mixer.pause()
                            else:
                                pygame.mixer.unpause()
                    elif event.key == pygame.K_m:
                        self.sfx.toggle_mute()
                    elif event.key == pygame.K_b:
                        self.sfx.toggle_music()

            self.frame += 1
            self.sfx.tick()
            if self.state == "play" and not self.paused:
                self.update()
            elif self.state != "play":
                # 타이틀/게임오버 화면에서도 배경과 이펙트는 움직임
                self.scroll_y = (self.scroll_y + self.scroll) % TERRAIN_H
                for pt in self.particles:
                    pt.update()
                self.particles = [o for o in self.particles if o.life > 0]
                for o in self.ebullets:
                    o.update()
                self.ebullets = [o for o in self.ebullets if not o.dead]

            self.draw()
            self.clock.tick(FPS)


def main():
    Game().run()
    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
