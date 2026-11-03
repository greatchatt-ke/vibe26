# 🌃 City Pop Video Generator — 1980s Tokyo

명령 한 줄로 **1980년대 도쿄 시티팝 영상**(음악 + 영상 + 썸네일 + 업로드용 메타데이터)을 자동 생성합니다.
외부 API·저작권 음원 없이 **numpy + Pillow + ffmpeg**만으로 전부 절차적으로 만듭니다.

## 설치
```bash
pip install -r requirements.txt
sudo apt install ffmpeg fonts-ipafont-gothic   # macOS: brew install ffmpeg (+ 일본어 폰트 경로 수정)
```

## 사용법
```bash
python citypop_video.py --preview                          # 15초 미리보기
python citypop_video.py --duration 180 --size 1920x1080    # 3분 풀HD 1편
python citypop_video.py --count 10 --duration 240          # 10편 일괄 자동 생성
python citypop_video.py --theme midnight --seed 42         # 테마/시드 고정 (재현 가능)
python citypop_video.py --audio my_track.mp3               # 내 음원(Suno 등)으로 영상만 생성
```

출력 (`output/citypop_<seed>_<theme>/`):
| 파일 | 내용 |
|---|---|
| `video.mp4` | H.264 + AAC, 유튜브 업로드용 |
| `audio.wav` | 생성된 음원 |
| `thumbnail.jpg` | 타이틀이 들어간 썸네일 |
| `metadata.json` | 유튜브 제목·설명(한/일/영)·태그·BPM·코드 진행 |

## 구성
**음악 (`citypop/music.py`)** — 시티팝 코드 진행 5종(Just the Two of Us 진행, 왕도진행 IV-V-iii-vi, ii-V-I 등),
FM 로즈/DX7 일렉트릭 피아노, 슬랩 베이스, 스트링 패드, 신스 리드(AABA 멜로디 + 핑퐁 딜레이),
LinnDrum 스타일 드럼 + 80년대 게이티드 리버브, 코러스, 홀 리버브, 테이프 wow/flutter·히스.
구성: 인트로 → 벌스 → 코러스 → (브레이크) → 아웃트로, 섹션 전환마다 탐 필인.

**영상 (`citypop/visuals.py`)** — 테마 4종 `sunset` / `midnight` / `magic_hour` / `neon_rain`.
줄무늬 80s 석양 또는 초승달, 3겹 패럴랙스 스카이라인(창문 불빛·네온 간판·항공 경고등), 도쿄타워,
도쿄만 수면 반사(물결 왜곡), 보케·빗줄기, 네온 일본어 타이틀.
VHS 후처리: 블룸, 색수차, 크로마 번짐, 스캔라인, 그레인, 비네트, 트래킹 글리치, `PLAY ▶` OSD와 1985년 타임스탬프.
음악의 음량/온셋에 맞춰 석양 글로우·네온·글리치가 반응합니다.

## 커스터마이징
- 제목/아티스트 목록: `citypop/meta.py`의 `TITLES`, `ARTISTS`
- 색감 테마 추가: `citypop/visuals.py`의 `THEMES`
- 코드 진행/리듬: `citypop/music.py`의 `PROGRESSIONS`, `EP_RHYTHMS`, `BASS_PATTERNS`

## 성능
4코어 기준 720p 1분 ≈ 3~4분 렌더 (프레임 병렬 처리, `--workers`로 조정). 1080p는 약 2.3배.
