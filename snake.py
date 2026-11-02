"""뱀 게임 (Snake Game) - 사람 vs AI 대결, tkinter 사용 (추가 설치 불필요)

사람(초록 뱀)과 AI(파란 뱀)가 같은 사과를 놓고 경쟁합니다.
- 벽, 자기 몸, 상대 몸에 부딪히면 죽고 상대가 승리합니다.
- 머리끼리 정면 충돌하면 둘 다 죽고, 점수가 높은 쪽이 승리합니다.
- 먼저 WIN_SCORE 점에 도달해도 승리합니다.

조작법:
  방향키 / WASD : 이동
  Space         : 일시정지 / 재개
  R             : 게임 오버 후 다시 시작
"""
import random
import tkinter as tk
from collections import deque

CELL = 20          # 칸 크기(px)
COLS = 30          # 가로 칸 수
ROWS = 24          # 세로 칸 수
START_SPEED = 130  # 시작 속도(ms, 작을수록 빠름)
MIN_SPEED = 60     # 최고 속도
WIN_SCORE = 200    # 이 점수에 먼저 도달하면 승리
AI_MISTAKE = 0.05  # AI가 최적 경로 대신 아무 안전한 칸으로 갈 확률 (난이도 조절)

DIRECTIONS = {
    "Up": (0, -1), "w": (0, -1),
    "Down": (0, 1), "s": (0, 1),
    "Left": (-1, 0), "a": (-1, 0),
    "Right": (1, 0), "d": (1, 0),
}
MOVES = [(0, -1), (0, 1), (-1, 0), (1, 0)]

COLORS = {
    "player": ("#a6e3a1", "#40a02b"),  # (머리, 몸통)
    "ai": ("#89b4fa", "#1e66f5"),
}


def in_bounds(p):
    return 0 <= p[0] < COLS and 0 <= p[1] < ROWS


class Snake:
    def __init__(self, name, body, direction):
        self.name = name
        self.body = body
        self.direction = direction
        self.next_direction = direction
        self.score = 0
        self.alive = True

    @property
    def head(self):
        return self.body[0]


class SnakeGame:
    def __init__(self, root: tk.Tk):
        self.root = root
        root.title("Snake Game - 사람 vs AI")
        root.resizable(False, False)

        self.score_label = tk.Label(root, font=("Consolas", 14), anchor="w")
        self.score_label.pack(fill="x", padx=8, pady=4)

        self.canvas = tk.Canvas(
            root, width=COLS * CELL, height=ROWS * CELL,
            bg="#1e1e2e", highlightthickness=0,
        )
        self.canvas.pack()

        self.wins = {"player": 0, "ai": 0}
        root.bind("<Key>", self.on_key)
        self.after_id = None
        self.reset()

    # ------------------------------------------------------------ 게임 상태
    def reset(self):
        py, ay = ROWS // 3, ROWS - ROWS // 3
        self.player = Snake("player", [(5, py), (4, py), (3, py)], (1, 0))
        self.ai = Snake("ai", [(COLS - 6, ay), (COLS - 5, ay), (COLS - 4, ay)], (-1, 0))
        self.speed = START_SPEED
        self.paused = False
        self.game_over = False
        self.result = ""
        self.food = self.spawn_food()
        self.update_label()
        if self.after_id:
            self.root.after_cancel(self.after_id)
        self.tick()

    @property
    def snakes(self):
        return (self.player, self.ai)

    def spawn_food(self):
        occupied = set(self.player.body) | set(self.ai.body)
        free = [(x, y) for x in range(COLS) for y in range(ROWS)
                if (x, y) not in occupied]
        return random.choice(free) if free else None

    # ------------------------------------------------------------ 입력
    def on_key(self, event):
        key = event.keysym if event.keysym in DIRECTIONS else event.keysym.lower()
        if key in DIRECTIONS:
            dx, dy = DIRECTIONS[key]
            d = self.player.direction
            # 반대 방향으로는 바로 돌 수 없음
            if (dx, dy) != (-d[0], -d[1]):
                self.player.next_direction = (dx, dy)
        elif key == "space" and not self.game_over:
            self.paused = not self.paused
            if self.paused:
                self.draw()
            else:
                self.tick()
        elif key == "r" and self.game_over:
            self.reset()

    # ------------------------------------------------------------ AI
    def ai_choose_direction(self):
        me, other = self.ai, self.player
        # 다음 턴에 비어 있을 칸: 꼬리는 움직이므로 제외
        blocked = set(me.body[:-1]) | set(other.body[:-1])
        # 상대 머리가 다음 턴에 들어올 수 있는 칸 (정면 충돌 위험)
        danger = {(other.head[0] + dx, other.head[1] + dy) for dx, dy in MOVES}

        candidates = []
        for d in MOVES:
            if d == (-me.direction[0], -me.direction[1]):
                continue
            nxt = (me.head[0] + d[0], me.head[1] + d[1])
            if not in_bounds(nxt) or nxt in blocked:
                continue
            # 이 칸으로 간 뒤의 장애물(내 몸이 한 칸 앞으로 이동)
            after = blocked | {me.head}
            space = self.flood_fill(nxt, after, limit=len(me.body) * 2 + 10)
            dist = self.bfs_distance(nxt, self.food, after)
            candidates.append((d, nxt, space, dist))

        if not candidates:
            return me.direction  # 갈 곳이 없음

        if random.random() < AI_MISTAKE:
            return random.choice(candidates)[0]

        need = len(me.body) + 1

        def score(c):
            d, nxt, space, dist = c
            trapped = space < need          # 갇힐 위험
            risky = nxt in danger           # 상대 머리와 부딪힐 위험
            reachable = dist is not None
            return (trapped, risky, not reachable,
                    dist if reachable else 0, -space)

        return min(candidates, key=score)[0]

    @staticmethod
    def flood_fill(start, blocked, limit):
        """start에서 갈 수 있는 칸 수 (limit까지만 셈)"""
        seen = {start}
        q = deque([start])
        while q and len(seen) < limit:
            x, y = q.popleft()
            for dx, dy in MOVES:
                n = (x + dx, y + dy)
                if in_bounds(n) and n not in blocked and n not in seen:
                    seen.add(n)
                    q.append(n)
        return len(seen)

    @staticmethod
    def bfs_distance(start, goal, blocked):
        if goal is None:
            return None
        if start == goal:
            return 0
        seen = {start}
        q = deque([(start, 0)])
        while q:
            (x, y), dist = q.popleft()
            for dx, dy in MOVES:
                n = (x + dx, y + dy)
                if n == goal:
                    return dist + 1
                if in_bounds(n) and n not in blocked and n not in seen:
                    seen.add(n)
                    q.append((n, dist + 1))
        return None

    # ------------------------------------------------------------ 진행
    def tick(self):
        if self.paused or self.game_over:
            return
        self.step()
        self.draw()
        if not self.game_over:
            self.after_id = self.root.after(self.speed, self.tick)

    def step(self):
        self.ai.next_direction = self.ai_choose_direction()

        # 두 뱀의 새 머리 위치를 동시에 계산
        new_heads = {}
        ate = {}
        for s in self.snakes:
            s.direction = s.next_direction
            new_heads[s.name] = (s.head[0] + s.direction[0], s.head[1] + s.direction[1])
            ate[s.name] = new_heads[s.name] == self.food

        # 이동 후 남아 있을 몸통 (먹지 않으면 꼬리가 빠짐)
        bodies = {s.name: (s.body if ate[s.name] else s.body[:-1]) for s in self.snakes}
        occupied = set(bodies["player"]) | set(bodies["ai"])

        for s in self.snakes:
            h = new_heads[s.name]
            if not in_bounds(h) or h in occupied:
                s.alive = False
        if new_heads["player"] == new_heads["ai"]:  # 정면 충돌
            self.player.alive = self.ai.alive = False

        if not (self.player.alive and self.ai.alive):
            self.finish()
            return

        for s in self.snakes:
            s.body.insert(0, new_heads[s.name])
            if ate[s.name]:
                s.score += 10
                self.speed = max(MIN_SPEED, self.speed - 2)
            else:
                s.body.pop()

        if any(ate.values()):
            self.food = self.spawn_food()

        if self.player.score >= WIN_SCORE or self.ai.score >= WIN_SCORE or self.food is None:
            self.finish()
        self.update_label()

    def finish(self):
        self.game_over = True
        p, a = self.player, self.ai
        if p.alive and not a.alive:
            winner = "player"
        elif a.alive and not p.alive:
            winner = "ai"
        elif p.score != a.score:
            winner = "player" if p.score > a.score else "ai"
        else:
            winner = None

        if winner:
            self.wins[winner] += 1
            self.result = "당신의 승리!" if winner == "player" else "AI 승리!"
        else:
            self.result = "무승부"
        self.update_label()

    # ------------------------------------------------------------ 화면
    def update_label(self):
        self.score_label.config(
            text=(f"나(초록): {self.player.score:>3}   AI(파랑): {self.ai.score:>3}"
                  f"   목표: {WIN_SCORE}   전적 {self.wins['player']}:{self.wins['ai']}"))

    def draw(self):
        c = self.canvas
        c.delete("all")

        if self.food:
            fx, fy = self.food
            c.create_oval(fx * CELL + 3, fy * CELL + 3,
                          (fx + 1) * CELL - 3, (fy + 1) * CELL - 3,
                          fill="#f38ba8", outline="")
            c.create_line(fx * CELL + CELL / 2, fy * CELL + 2,
                          fx * CELL + CELL / 2 + 3, fy * CELL - 2,
                          fill="#a6e3a1", width=2)

        for s in self.snakes:
            head_color, body_color = COLORS[s.name]
            if not s.alive:
                head_color = body_color = "#6c7086"
            for i, (x, y) in enumerate(s.body):
                c.create_rectangle(x * CELL + 1, y * CELL + 1,
                                   (x + 1) * CELL - 1, (y + 1) * CELL - 1,
                                   fill=head_color if i == 0 else body_color,
                                   outline="")

        w, h = COLS * CELL, ROWS * CELL
        if self.game_over:
            c.create_text(w / 2, h / 2 - 20, text=self.result,
                          fill="white", font=("Consolas", 32, "bold"))
            c.create_text(w / 2, h / 2 + 20, text="R 키를 눌러 다시 시작",
                          fill="#cdd6f4", font=("Consolas", 14))
        elif self.paused:
            c.create_text(w / 2, h / 2, text="일시정지 (Space)",
                          fill="white", font=("Consolas", 24, "bold"))


if __name__ == "__main__":
    root = tk.Tk()
    SnakeGame(root)
    root.mainloop()
