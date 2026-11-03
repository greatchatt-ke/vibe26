"""
대한민국 출생 통계 분석기 (PyQt6)

KOSIS 「출생아수, 합계출산율, 자연증가 등」 엑셀(INH_1B8000F_01)을 불러와 클렌징하고 다각도로 분석한다.
- 상단 요약 카드: 최근 출생아수 · 최대/최저 · 1970년 대비 변화 · 최저 합계출산율 · 자연감소 시작
- 지표 선택 + 연도 구간 선택 시 차트 자동 갱신, 5년 이동평균 토글
- 차트 위 마우스 이동 시 해당 연도 값 표시
- 전년 대비 증감률 · 연대별 분석 · 정제 데이터 · 분석 리포트 · 클렌징 리포트 탭
- 차트 PNG / 정제 데이터 CSV 저장

필요 패키지: pip install PyQt6 pandas matplotlib openpyxl
"""

import io
import sys
from contextlib import redirect_stdout
from pathlib import Path

import matplotlib
matplotlib.use("QtAgg")
import pandas as pd
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from matplotlib.ticker import FuncFormatter
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QHeaderView, QLabel, QMainWindow, QMessageBox, QPlainTextEdit, QPushButton,
    QSpinBox, QTableWidget, QTableWidgetItem, QTabWidget, QVBoxLayout, QWidget,
)

from birth_analysis import DEFAULT_PATH, INDICATORS, analyze, draw_indicator, load_and_clean

BG = "#0f1528"
FG = "#e6e9f5"
MUTED = "#9aa3c0"
UP = "#3987e5"     # 증가
DOWN = "#d95926"   # 감소

CHART_THEME = {"surface": "#121a33", "line": "#3987e5", "ma": "#d95926",
               "ink": FG, "muted": MUTED, "grid": "#25304f"}

STYLE = f"""
* {{ font-family: 'Malgun Gothic', 'Segoe UI'; color: {FG}; font-size: 13px; }}
QMainWindow, #root {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
    stop:0 #0b1020, stop:0.5 #111832, stop:1 #170f2e); }}
#banner {{ border-radius: 16px; background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
    stop:0 #1d4ed8, stop:0.55 #4338ca, stop:1 #db2777); }}
#bannerTitle {{ font-size: 24px; font-weight: 800; color: white; background: transparent; }}
#bannerSub {{ font-size: 13px; color: rgba(255,255,255,0.8); background: transparent; }}
#card {{ background: rgba(255,255,255,0.05); border: 1px solid rgba(255,255,255,0.08);
    border-radius: 14px; }}
#cardTitle {{ font-size: 12px; color: {MUTED}; background: transparent; }}
#cardValue {{ font-size: 21px; font-weight: 700; background: transparent; }}
#cardSub {{ font-size: 11px; color: {MUTED}; background: transparent; }}
#hover {{ color: {MUTED}; background: transparent; }}
QLabel {{ background: transparent; }}
QPushButton {{ background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.15);
    border-radius: 8px; padding: 6px 14px; }}
QPushButton:hover {{ background: rgba(255,255,255,0.16); }}
QComboBox, QSpinBox {{ background: #182142; border: 1px solid rgba(255,255,255,0.15);
    border-radius: 6px; padding: 4px 8px; }}
QComboBox QAbstractItemView {{ background: #182142; selection-background-color: #4338ca; }}
QCheckBox {{ background: transparent; }}
QTabWidget::pane {{ border: 1px solid rgba(255,255,255,0.08); border-radius: 10px;
    background: {CHART_THEME['surface']}; }}
QTabBar::tab {{ background: transparent; padding: 8px 16px; color: {MUTED}; }}
QTabBar::tab:selected {{ color: white; border-bottom: 2px solid #6366f1; }}
QTableWidget {{ background: {CHART_THEME['surface']}; gridline-color: #25304f; border: none;
    alternate-background-color: #162040; }}
QHeaderView::section {{ background: #1a2448; color: {MUTED}; border: none; padding: 6px; }}
QPlainTextEdit {{ background: {CHART_THEME['surface']}; border: none;
    font-family: 'D2Coding', 'Consolas', 'Malgun Gothic'; font-size: 12px; }}
"""

TABLE_COLUMNS = [
    ("year", "연도"), ("births", "출생아수"), ("deaths", "사망자수"),
    ("natural_increase", "자연증가"), ("crude_birth_rate", "조출생률"),
    ("natural_increase_rate", "자연증가율"), ("tfr", "합계출산율"),
    ("sex_ratio", "출생성비"), ("births_yoy", "증감률(%)"), ("provisional", "잠정치"),
]


def make_card(title):
    frame = QFrame(objectName="card")
    lay = QVBoxLayout(frame)
    lay.setContentsMargins(14, 10, 14, 10)
    lay.setSpacing(2)
    lay.addWidget(QLabel(title, objectName="cardTitle"))
    value = QLabel("-", objectName="cardValue")
    sub = QLabel("", objectName="cardSub")
    lay.addWidget(value)
    lay.addWidget(sub)
    return frame, value, sub


def fmt_cell(col, v):
    if pd.isna(v):
        return ""
    if col == "provisional":
        return "잠정" if v else ""
    if col == "year":
        return str(int(v))
    if col in ("births", "deaths", "natural_increase"):
        return f"{int(v):,}"
    if col == "tfr":
        return f"{v:.3f}"
    if col == "births_yoy":
        return f"{v:+.2f}"
    return f"{v:.1f}"


class ChartCanvas(FigureCanvasQTAgg):
    def __init__(self):
        self.fig = Figure(figsize=(10, 5.5), facecolor=CHART_THEME["surface"])
        self.ax = self.fig.add_subplot(111)
        super().__init__(self.fig)


class BirthAnalyzer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("대한민국 출생 통계 분석기")
        self.resize(1320, 900)
        self.full = None       # 정제된 전체 데이터
        self.view = None       # 연도 구간이 적용된 데이터
        self.clean_log = ""
        self.vline = None
        self._build_ui()

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        root = QWidget(objectName="root")
        self.setCentralWidget(root)
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(12)

        banner = QFrame(objectName="banner")
        b = QHBoxLayout(banner)
        b.setContentsMargins(22, 14, 22, 14)
        texts = QVBoxLayout()
        texts.addWidget(QLabel("대한민국 출생 통계 분석기", objectName="bannerTitle"))
        self.source_label = QLabel("KOSIS 인구동향조사 · 파일을 불러오세요", objectName="bannerSub")
        texts.addWidget(self.source_label)
        b.addLayout(texts, 1)
        for text, slot in [("엑셀 열기", self.open_file), ("차트 PNG 저장", self.save_png),
                           ("정제 CSV 저장", self.save_csv)]:
            btn = QPushButton(text)
            btn.clicked.connect(slot)
            b.addWidget(btn)
        outer.addWidget(banner)

        cards = QHBoxLayout()
        cards.setSpacing(10)
        self.cards = {}
        for key, title in [("recent", "최근 출생아수"), ("peak", "최대 출생아수"),
                           ("low", "최저 출생아수"), ("change", "기간 변화율"),
                           ("tfr", "최저 합계출산율"), ("cross", "자연감소 시작")]:
            frame, value, sub = make_card(title)
            self.cards[key] = (value, sub)
            cards.addWidget(frame)
        outer.addLayout(cards)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("지표"))
        self.indicator = QComboBox()
        for key, info in INDICATORS.items():
            self.indicator.addItem(info[0], key)
        self.indicator.currentIndexChanged.connect(self.refresh_charts)
        controls.addWidget(self.indicator)
        controls.addSpacing(16)
        controls.addWidget(QLabel("기간"))
        self.start_year, self.end_year = QSpinBox(), QSpinBox()
        for spin in (self.start_year, self.end_year):
            spin.setRange(1900, 2100)
            spin.valueChanged.connect(self.apply_range)
            controls.addWidget(spin)
        controls.insertWidget(controls.count() - 1, QLabel("~"))
        reset = QPushButton("전체 기간")
        reset.clicked.connect(self.reset_range)
        controls.addWidget(reset)
        controls.addSpacing(16)
        self.ma_check = QCheckBox("5년 이동평균")
        self.ma_check.toggled.connect(self.refresh_charts)
        controls.addWidget(self.ma_check)
        controls.addStretch(1)
        self.hover_label = QLabel("차트 위에 마우스를 올리면 연도별 값이 표시됩니다", objectName="hover")
        controls.addWidget(self.hover_label)
        outer.addLayout(controls)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs, 1)

        # 추이 차트
        tab = QWidget()
        lay = QVBoxLayout(tab)
        self.canvas = ChartCanvas()
        self.canvas.mpl_connect("motion_notify_event", self.on_hover)
        toolbar = NavigationToolbar2QT(self.canvas, tab)
        toolbar.setStyleSheet("background: #e6e9f5; border-radius: 6px;")
        lay.addWidget(toolbar)
        lay.addWidget(self.canvas)
        self.tabs.addTab(tab, "추이 차트")

        # 전년 대비 증감률
        self.yoy_canvas = ChartCanvas()
        self.tabs.addTab(self.yoy_canvas, "전년 대비 증감률")

        self.decade_table = QTableWidget()
        self.tabs.addTab(self.decade_table, "연대별 분석")
        self.data_table = QTableWidget()
        self.tabs.addTab(self.data_table, "정제 데이터")

        self.report_text = QPlainTextEdit(readOnly=True)
        self.tabs.addTab(self.report_text, "분석 리포트")
        self.clean_text = QPlainTextEdit(readOnly=True)
        self.tabs.addTab(self.clean_text, "클렌징 리포트")

        for table in (self.decade_table, self.data_table):
            table.setAlternatingRowColors(True)
            table.verticalHeader().setVisible(False)
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    # ------------------------------------------------------------ 데이터
    def open_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "KOSIS 출생 통계 엑셀 선택", "",
                                              "Excel (*.xlsx *.xls)")
        if path:
            self.load(path)

    def load(self, path):
        buf = io.StringIO()
        try:
            with redirect_stdout(buf):
                df = load_and_clean(path)
        except Exception as e:  # 형식이 다른 파일
            QMessageBox.critical(self, "불러오기 실패", f"파일을 처리하지 못했습니다.\n\n{e}")
            return
        self.full = df
        self.clean_log = buf.getvalue()
        self.source_label.setText(f"{Path(path).name} · {df['year'].min()}~{df['year'].max()}년 "
                                  f"· {len(df)}개 연도")
        for spin in (self.start_year, self.end_year):
            spin.blockSignals(True)
            spin.setRange(int(df["year"].min()), int(df["year"].max()))
        self.start_year.setValue(int(df["year"].min()))
        self.end_year.setValue(int(df["year"].max()))
        for spin in (self.start_year, self.end_year):
            spin.blockSignals(False)
        self.apply_range()

    def reset_range(self):
        if self.full is not None:
            self.start_year.setValue(self.start_year.minimum())
            self.end_year.setValue(self.end_year.maximum())

    def apply_range(self):
        if self.full is None:
            return
        lo, hi = self.start_year.value(), self.end_year.value()
        if hi - lo < 2:
            return
        self.view = self.full[(self.full["year"] >= lo) & (self.full["year"] <= hi)]
        self.refresh_cards()
        self.refresh_charts()
        self.refresh_tables()
        self.refresh_reports()

    # ------------------------------------------------------------ 갱신
    def refresh_cards(self):
        df = self.view
        last, first = df.iloc[-1], df.iloc[0]
        peak, low = df.loc[df["births"].idxmax()], df.loc[df["births"].idxmin()]
        tfr = df.loc[df["tfr"].idxmin()]
        neg = df.loc[df["natural_increase"] < 0, "year"]
        change = (last["births"] / first["births"] - 1) * 100

        def set_card(key, value, sub):
            self.cards[key][0].setText(value)
            self.cards[key][1].setText(sub)

        set_card("recent", f"{last['births']:,}명",
                 f"{last['year']}년{' (잠정)' if last['provisional'] else ''} · "
                 f"전년비 {last['births_yoy']:+.1f}%")
        set_card("peak", f"{peak['births']:,}명", f"{peak['year']}년")
        set_card("low", f"{low['births']:,}명", f"{low['year']}년")
        set_card("change", f"{change:+.1f}%", f"{first['year']}년 → {last['year']}년")
        set_card("tfr", f"{tfr['tfr']:.3f}명", f"{tfr['year']}년")
        set_card("cross", f"{neg.min()}년" if not neg.empty else "없음",
                 "사망자수 > 출생아수" if not neg.empty else "선택 기간 내 자연증가")
        color = UP if change >= 0 else DOWN
        self.cards["change"][0].setStyleSheet(f"color: {color};")

    def refresh_charts(self):
        if self.view is None:
            return
        col = self.indicator.currentData()
        ax = self.canvas.ax
        ax.clear()
        draw_indicator(ax, self.view, col, CHART_THEME, self.ma_check.isChecked())
        self.vline = ax.axvline(self.view["year"].iloc[0], color=MUTED, linewidth=1,
                                linestyle=":", visible=False)
        self.canvas.fig.tight_layout()
        self.canvas.draw_idle()
        self.draw_yoy()

    def draw_yoy(self):
        df = self.view.dropna(subset=["births_yoy"])
        ax = self.yoy_canvas.ax
        ax.clear()
        ax.set_facecolor(CHART_THEME["surface"])
        colors = [UP if v >= 0 else DOWN for v in df["births_yoy"]]
        ax.bar(df["year"], df["births_yoy"], color=colors, width=0.75,
               edgecolor=CHART_THEME["surface"], linewidth=1)
        ax.axhline(0, color=MUTED, linewidth=1)
        lo, hi = min(df["births_yoy"].min(), 0), max(df["births_yoy"].max(), 0)
        ax.set_ylim(lo - (hi - lo) * 0.15, hi + (hi - lo) * 0.12)  # 라벨 여백
        for _, r in pd.concat([df.nsmallest(3, "births_yoy"), df.nlargest(3, "births_yoy")]).iterrows():
            v = r["births_yoy"]
            ax.annotate(f"{int(r['year'])}\n{v:+.1f}%", (r["year"], v), textcoords="offset points",
                        xytext=(0, 6 if v >= 0 else -26), ha="center", fontsize=8, color=FG)
        ax.set_title("출생아수 전년 대비 증감률 (파랑: 증가 · 주황: 감소)", fontsize=14, color=FG,
                     loc="left", pad=12)
        ax.set_ylabel("증감률 (%)", color=MUTED)
        ax.yaxis.set_major_formatter(FuncFormatter(lambda v, _: f"{v:+.0f}"))
        ax.grid(axis="y", color=CHART_THEME["grid"], linewidth=0.8)
        ax.set_axisbelow(True)
        for side in ["top", "right", "left"]:
            ax.spines[side].set_visible(False)
        ax.spines["bottom"].set_color(MUTED)
        ax.tick_params(colors=MUTED, length=0)
        self.yoy_canvas.fig.tight_layout()
        self.yoy_canvas.draw_idle()

    def refresh_tables(self):
        df = self.view
        t = self.data_table
        t.setRowCount(len(df))
        t.setColumnCount(len(TABLE_COLUMNS))
        t.setHorizontalHeaderLabels([h for _, h in TABLE_COLUMNS])
        for r, (_, row) in enumerate(df.iterrows()):
            for c, (col, _) in enumerate(TABLE_COLUMNS):
                item = QTableWidgetItem(fmt_cell(col, row[col]))
                item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                if col in ("births_yoy", "natural_increase") and pd.notna(row[col]) and row[col] < 0:
                    item.setForeground(QColor(DOWN))
                t.setItem(r, c, item)

        dec = df.groupby("decade").agg(
            births=("births", "mean"), tfr=("tfr", "mean"), cbr=("crude_birth_rate", "mean"),
            sex=("sex_ratio", "mean"), ni=("natural_increase", "sum"), n=("year", "size"),
        )
        headers = ["연대", "연도 수", "평균 출생아수", "평균 합계출산율", "평균 조출생률",
                   "평균 출생성비", "자연증가 합계"]
        d = self.decade_table
        d.setRowCount(len(dec))
        d.setColumnCount(len(headers))
        d.setHorizontalHeaderLabels(headers)
        for r, (name, row) in enumerate(dec.iterrows()):
            values = [name, f"{int(row['n'])}", f"{row['births']:,.0f}", f"{row['tfr']:.2f}",
                      f"{row['cbr']:.1f}", f"{row['sex']:.1f}", f"{int(row['ni']):,}"]
            for c, v in enumerate(values):
                item = QTableWidgetItem(v)
                item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                d.setItem(r, c, item)

    def refresh_reports(self):
        buf = io.StringIO()
        with redirect_stdout(buf):
            analyze(self.view.reset_index(drop=True))
        lo, hi = self.view["year"].min(), self.view["year"].max()
        self.report_text.setPlainText(f"[분석 기간] {lo}~{hi}년\n" + buf.getvalue())
        self.clean_text.setPlainText(
            self.clean_log
            + "\n[처리 내역]\n"
            "- 가로형(행=지표, 열=연도) 표를 연도별 행 구조로 전치\n"
            "- '2025 p)' 형태의 잠정치 연도 표기를 정수 연도 + provisional 플래그로 분리\n"
            "- 한글 지표명을 영문 컬럼명으로 변환, 쉼표/'-' 등 비정상 값은 숫자 변환 시 결측 처리\n"
            "- 중복 연도 제거 후 연도순 정렬\n"
            "- 파생 변수: 사망자수(출생-자연증가), 전년 대비 증감/증감률, 5년 이동평균, 연대\n"
        )

    # ------------------------------------------------------------ 상호작용
    def on_hover(self, event):
        if self.view is None or event.inaxes is not self.canvas.ax or event.xdata is None:
            return
        year = int(round(event.xdata))
        row = self.view[self.view["year"] == year]
        if row.empty:
            return
        r = row.iloc[0]
        col = self.indicator.currentData()
        name, _, _, label_fmt = INDICATORS[col]
        yoy = f" · 출생 전년비 {r['births_yoy']:+.1f}%" if pd.notna(r["births_yoy"]) else ""
        self.hover_label.setText(f"{year}년{' (잠정)' if r['provisional'] else ''} · "
                                 f"{name} {label_fmt(r[col])}{yoy}")
        self.vline.set_xdata([year, year])
        self.vline.set_visible(True)
        self.canvas.draw_idle()

    def save_png(self):
        if self.view is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "차트 저장", "births_chart.png", "PNG (*.png)")
        if path:
            canvas = self.canvas if self.tabs.currentIndex() != 1 else self.yoy_canvas
            canvas.fig.savefig(path, dpi=150, facecolor=CHART_THEME["surface"])

    def save_csv(self):
        if self.view is None:
            return
        path, _ = QFileDialog.getSaveFileName(self, "정제 데이터 저장", "births_clean.csv", "CSV (*.csv)")
        if path:
            self.view.to_csv(path, index=False, encoding="utf-8-sig")


def main():
    app = QApplication(sys.argv)
    app.setStyleSheet(STYLE)
    win = BirthAnalyzer()
    win.show()
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_PATH
    if Path(path).exists():
        win.load(path)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
