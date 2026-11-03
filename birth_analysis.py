"""대한민국 출생아수·합계출산율 데이터 정제 및 분석 (KOSIS INH_1B8000F_01, 1970~2025)

사용법:
    python birth_analysis.py [엑셀파일경로]
결과물은 birth_output/ 폴더에 저장됩니다.
"""
import re
import sys
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import pandas as pd

DEFAULT_PATH = r"C:\Users\user\AppData\Local\Temp\출생아수__합계출산율__자연증가_등_20260605082440.xlsx"
OUT_DIR = Path(__file__).parent / "birth_output"

COLUMN_MAP = {
    "출생아수(명)": "births",
    "자연증가건수(명)": "natural_increase",
    "조출생률(천명당)": "crude_birth_rate",
    "자연증가율(천명당)": "natural_increase_rate",
    "합계출산율(명)": "tfr",
    "출생성비(명)": "sex_ratio",
}

plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False


# ----------------------------------------------------------------------------
# 1. 데이터 클렌징
# ----------------------------------------------------------------------------
def load_and_clean(path):
    raw = pd.read_excel(path, sheet_name=0, header=None)
    print(f"[원본] shape={raw.shape} (행=지표, 열=연도인 가로형 구조)")

    # 첫 행은 연도 헤더, 첫 열은 지표명 → 전치해서 연도를 행으로
    raw = raw.set_index(0)
    df = raw.T
    df.columns = [str(c).strip() for c in df.columns]
    year_col = df.columns[0]  # '기본항목별'

    # 연도 정제: '2025 p)' 같은 잠정치 표시를 분리
    year_str = df[year_col].astype(str).str.strip()
    df["provisional"] = year_str.str.contains(r"p\)", regex=True)
    df["year"] = year_str.map(lambda s: int(float(re.sub(r"[^0-9.]", "", s))))
    df = df.drop(columns=[year_col])

    # 컬럼명 영문화 + 숫자형 변환 (쉼표·공백·'-' 등 비정상 값은 NaN 처리)
    df = df.rename(columns=COLUMN_MAP)
    for col in COLUMN_MAP.values():
        df[col] = pd.to_numeric(
            df[col].astype(str).str.replace(",", "").str.strip().replace({"-": None, "": None}),
            errors="coerce",
        )
    for col in ["births", "natural_increase"]:
        df[col] = df[col].astype("Int64")

    # 품질 점검
    dup = df["year"].duplicated().sum()
    missing = df.isna().sum()
    expected = set(range(df["year"].min(), df["year"].max() + 1))
    gaps = sorted(expected - set(df["year"]))
    print(f"[점검] 중복 연도={dup}, 누락 연도={gaps or '없음'}, 결측치 합계={int(missing.sum())}")
    print(f"[점검] 잠정치 연도: {df.loc[df['provisional'], 'year'].tolist()}")
    df = df.drop_duplicates("year").sort_values("year").reset_index(drop=True)

    # 파생 변수
    df["deaths"] = df["births"] - df["natural_increase"]          # 사망자수 = 출생 - 자연증가
    df["births_yoy"] = df["births"].astype(float).pct_change() * 100            # 전년 대비 증감률(%)
    df["births_diff"] = df["births"].astype(float).diff()                       # 전년 대비 증감(명)
    df["births_ma5"] = df["births"].astype(float).rolling(5).mean()  # 5년 이동평균
    df["decade"] = (df["year"] // 10 * 10).astype(str) + "년대"

    cols = ["year", "provisional", *COLUMN_MAP.values(), "deaths",
            "births_yoy", "births_diff", "births_ma5", "decade"]
    return df[cols]


# ----------------------------------------------------------------------------
# 2. 다각도 분석
# ----------------------------------------------------------------------------
def section(title):
    print("\n" + "=" * 70 + f"\n{title}\n" + "=" * 70)


def analyze(df):
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 20)
    pd.set_option("display.float_format", lambda v: f"{v:,.2f}")

    section("① 기술통계")
    print(df[list(COLUMN_MAP.values()) + ["deaths"]].describe().T)

    section("② 출생아수 정점·저점 및 장기 변화")
    peak = df.loc[df["births"].idxmax()]
    low = df.loc[df["births"].idxmin()]
    first, last = df.iloc[0], df.iloc[-1]
    n = last["year"] - first["year"]
    cagr = ((last["births"] / first["births"]) ** (1 / n) - 1) * 100
    print(f"최대: {peak['year']}년 {peak['births']:,}명 / 최소: {low['year']}년 {low['births']:,}명")
    print(f"{first['year']}→{last['year']}년: {first['births']:,} → {last['births']:,}명 "
          f"({(last['births'] / first['births'] - 1) * 100:.1f}%, 연평균 {cagr:.2f}%)")

    section("③ 연대별 평균")
    decade = df.groupby("decade").agg(
        출생아수_평균=("births", "mean"),
        합계출산율_평균=("tfr", "mean"),
        조출생률_평균=("crude_birth_rate", "mean"),
        출생성비_평균=("sex_ratio", "mean"),
        자연증가_합계=("natural_increase", "sum"),
    )
    print(decade)

    section("④ 전년 대비 증감률 Top 5 (감소 / 증가)")
    view = df[["year", "births", "births_diff", "births_yoy"]].dropna()
    print("[감소폭 큰 해]\n", view.nsmallest(5, "births_yoy").to_string(index=False))
    print("[증가폭 큰 해]\n", view.nlargest(5, "births_yoy").to_string(index=False))
    streak = (df["births_yoy"] < 0).astype(int)
    runs = streak.groupby((streak != streak.shift()).cumsum()).agg(["sum", "size"])
    longest = runs[runs["sum"] > 0]["size"].max()
    print(f"최장 연속 감소 기간: {longest}년")

    section("⑤ 합계출산율 주요 임계점")
    for label, cond in [("대체출산율(2.1) 미만", df["tfr"] < 2.1),
                        ("초저출산(1.3) 미만", df["tfr"] < 1.3),
                        ("1.0 미만", df["tfr"] < 1.0)]:
        yr = df.loc[cond, "year"].min()
        print(f"{label} 최초 진입: {yr}년 (TFR {df.loc[df['year'] == yr, 'tfr'].iloc[0]})")
    print(f"역대 최저 합계출산율: {df.loc[df['tfr'].idxmin(), 'year']}년 {df['tfr'].min()}")

    section("⑥ 인구 자연감소 (데드크로스)")
    cross = df.loc[df["natural_increase"] < 0, "year"].min()
    print(f"자연증가가 처음 음수로 전환된 해: {cross}년")
    print(df.loc[df["year"] >= cross - 2, ["year", "births", "deaths", "natural_increase"]]
          .to_string(index=False))

    section("⑦ 출생성비 (정상범위 103~107)")
    abnormal = df[df["sex_ratio"] > 107]
    print(f"정상범위 초과 연도 {len(abnormal)}개: {abnormal['year'].tolist()}")
    print(f"최고 출생성비: {df.loc[df['sex_ratio'].idxmax(), 'year']}년 {df['sex_ratio'].max()}")

    section("⑧ 지표 간 상관계수")
    print(df[["births", "crude_birth_rate", "tfr", "natural_increase", "sex_ratio", "deaths"]]
          .astype(float).corr().round(3))

    section("⑨ 최근 반등 (2023→2025)")
    recent = df[df["year"] >= 2021][["year", "provisional", "births", "births_yoy", "tfr"]]
    print(recent.to_string(index=False))

    return decade


# ----------------------------------------------------------------------------
# 3. 시각화: 1970~2025 출생아수 라인 그래프
# ----------------------------------------------------------------------------
# 지표별 표시 정보: (한글명, 축 라벨, 축 값 변환, 라벨 값 포맷)
INDICATORS = {
    "births": ("출생아수", "출생아수 (만 명)", lambda v: f"{v / 10000:,.0f}", lambda v: f"{v / 10000:,.1f}만 명"),
    "natural_increase": ("자연증가건수", "자연증가 (만 명)", lambda v: f"{v / 10000:,.0f}", lambda v: f"{v / 10000:,.1f}만 명"),
    "deaths": ("사망자수", "사망자수 (만 명)", lambda v: f"{v / 10000:,.0f}", lambda v: f"{v / 10000:,.1f}만 명"),
    "tfr": ("합계출산율", "합계출산율 (명)", lambda v: f"{v:.1f}", lambda v: f"{v:.3f}명"),
    "crude_birth_rate": ("조출생률", "조출생률 (천명당)", lambda v: f"{v:.0f}", lambda v: f"{v:.1f}"),
    "natural_increase_rate": ("자연증가율", "자연증가율 (천명당)", lambda v: f"{v:.0f}", lambda v: f"{v:.1f}"),
    "sex_ratio": ("출생성비", "출생성비 (여아 100명당)", lambda v: f"{v:.0f}", lambda v: f"{v:.1f}"),
}

LIGHT_THEME = {"surface": "#fcfcfb", "line": "#2a78d6", "ma": "#eb6834",
               "ink": "#0b0b0b", "muted": "#52514e", "grid": "#e6e5e1"}


def draw_indicator(ax, df, col="births", theme=LIGHT_THEME, show_ma=False):
    """ax 위에 지표 하나를 라인으로 그린다 (스크립트와 GUI 공용)."""
    t = theme
    name, ylabel, tick_fmt, label_fmt = INDICATORS[col]
    ax.set_facecolor(t["surface"])

    final = df[~df["provisional"]]
    ax.plot(final["year"], final[col], color=t["line"], linewidth=2, label=name)
    # 잠정치 구간은 점선으로 구분
    if df["provisional"].any() and not final.empty:
        tail = df[df["year"] >= final["year"].max()]
        ax.plot(tail["year"], tail[col], color=t["line"], linewidth=2, linestyle="--")
    if show_ma:
        ma = df[col].astype(float).rolling(5).mean()
        ax.plot(df["year"], ma, color=t["ma"], linewidth=2, alpha=0.9, label="5년 이동평균")
        ax.legend(loc="upper right", frameon=False, labelcolor=t["ink"])

    # 주요 지점만 선택적으로 라벨링: (연도, 라벨, x오프셋, y오프셋, 정렬)
    first_yr, last_yr = df["year"].min(), df["year"].max()
    marks = [
        (df.loc[df[col].idxmax(), "year"], "최대", 8, 8, "left"),
        (df.loc[df[col].idxmin(), "year"], "최저", -12, -4, "right"),
    ]
    if col == "births":
        marks += [(1984, "60만대로 급감", -10, -30, "right"), (2002, "40만대 진입", -10, -30, "right")]
    if last_yr not in {m[0] for m in marks}:
        tag = "최근(잠정)" if df["provisional"].iloc[-1] else "최근"
        marks.append((last_yr, tag, 0, 14, "right"))
    for yr, text, dx, dy, ha in marks:
        if not first_yr <= yr <= last_yr:
            continue
        v = df.loc[df["year"] == yr, col].iloc[0]
        if yr == last_yr and ha == "left":
            dx, ha = -8, "right"
        ax.scatter(yr, v, s=50, color=t["line"], edgecolor=t["surface"], linewidth=2, zorder=3)
        ax.annotate(f"{text}\n{yr}년 {label_fmt(v)}", (yr, v), textcoords="offset points",
                    xytext=(dx, dy), ha=ha, va="top" if -10 < dy < 0 else "baseline",
                    fontsize=9, color=t["ink"])

    ax.set_title(f"대한민국 연도별 {name} ({first_yr}~{last_yr})", fontsize=15, color=t["ink"],
                 loc="left", pad=14)
    ax.set_xlabel("연도", color=t["muted"])
    ax.set_ylabel(ylabel, color=t["muted"])
    ax.yaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: tick_fmt(v)))
    ax.set_xlim(first_yr - 1, last_yr + 1)
    lo, hi = float(df[col].min()), float(df[col].max())
    pad = (hi - lo) * 0.15 or 1
    if lo >= 0 and col in ("births", "deaths", "tfr", "crude_birth_rate"):
        ax.set_ylim(0, hi + pad)
    else:
        ax.set_ylim(lo - pad, hi + pad)
    if lo < 0 < hi:
        ax.axhline(0, color=t["muted"], linewidth=1)
    step = 5 if last_yr - first_yr > 15 else 1
    ax.set_xticks(range(first_yr - first_yr % step + (step if first_yr % step else 0), last_yr + 1, step))
    ax.grid(axis="y", color=t["grid"], linewidth=0.8)
    for side in ["top", "right", "left"]:
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(t["muted"])
    ax.tick_params(colors=t["muted"], length=0)


def plot_births(df, out_path):
    fig, ax = plt.subplots(figsize=(12, 6), facecolor=LIGHT_THEME["surface"])
    draw_indicator(ax, df, "births")
    fig.text(0.01, 0.01, "자료: 통계청 「인구동향조사」(KOSIS). 2025년은 잠정치(점선).",
             fontsize=8, color=LIGHT_THEME["muted"])

    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    print(f"\n그래프 저장: {out_path}")
    plt.show()


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    OUT_DIR.mkdir(exist_ok=True)

    df = load_and_clean(path)
    df.to_csv(OUT_DIR / "births_clean.csv", index=False, encoding="utf-8-sig")
    print(f"정제 데이터 저장: {OUT_DIR / 'births_clean.csv'} ({len(df)}행)")

    decade = analyze(df)
    decade.to_csv(OUT_DIR / "births_by_decade.csv", encoding="utf-8-sig")

    plot_births(df, OUT_DIR / "births_1970_2025.png")


if __name__ == "__main__":
    main()
