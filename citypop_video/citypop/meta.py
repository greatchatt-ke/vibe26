"""Title / artist / metadata generation for upload automation."""
import numpy as np

TITLES = [
    ("真夜中のドライブ", "Midnight Drive"), ("湾岸サンセット", "Bayside Sunset"),
    ("東京ムーンライト", "Tokyo Moonlight"), ("ネオンの恋人", "Neon Lover"),
    ("都会のシャワー", "City Shower"), ("サマー・メモリー", "Summer Memory"),
    ("夜明けのハイウェイ", "Highway at Dawn"), ("渋谷レイン", "Shibuya Rain"),
    ("ガラスの街", "Glass City"), ("恋はミラージュ", "Love Is a Mirage"),
    ("銀座ナイトクルーズ", "Ginza Night Cruise"), ("青山ステップ", "Aoyama Step"),
    ("午前零時のダンス", "Dance at Midnight"), ("六本木トワイライト", "Roppongi Twilight"),
    ("シーサイド・ラブ", "Seaside Love"), ("さよならの交差点", "Goodbye Crossing"),
]
ARTISTS = ["サンセット・クラブ", "ネオン・アベニュー", "ミッドナイト・オーケストラ", "湾岸ストリングス",
           "シティ・ライツ", "ムーンライト・パレード", "ガラスの午後", "東京ヴィジョン"]


def make_meta(seed, theme, music_info, duration):
    r = np.random.default_rng(seed + 99)
    jp, en = TITLES[r.integers(len(TITLES))]
    artist = ARTISTS[r.integers(len(ARTISTS))]
    mins, secs = divmod(int(duration), 60)
    yt_title = f"{jp} ({en}) — 80s Tokyo City Pop | シティポップ | 시티팝"
    desc = (
        f"🌃 {jp} / {en}\n♪ {artist}\n\n"
        f"1980년대 도쿄의 밤, 네온과 바다 위 반짝이는 도시의 불빛. 드라이브·공부·작업용 시티팝.\n"
        f"1980年代・東京の夜をイメージしたシティポップ。\n"
        f"An original 1980s Tokyo city pop track — late-night drives, neon skylines, cassette warmth.\n\n"
        f"BPM {music_info.get('bpm', '-')} · Key {music_info.get('key', '-')} · "
        f"{' – '.join(music_info.get('chords', []))}\n"
        f"Length {mins}:{secs:02d}\n\n"
        "#citypop #シティポップ #시티팝 #80s #tokyo #japanesecitypop #lofi #retrowave"
    )
    tags = ["city pop", "シティポップ", "시티팝", "80s japan", "tokyo night", "japanese city pop",
            "retro", "vaporwave", "drive music", "1980s", theme.replace("_", " ")]
    return dict(seed=seed, theme=theme, title_jp=jp, title_en=en, artist=artist,
                youtube_title=yt_title, description=desc, tags=tags, music=music_info,
                duration_sec=round(duration, 2))
