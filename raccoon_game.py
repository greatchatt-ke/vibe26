import time
import tkinter as tk


WIDTH = 800
HEIGHT = 600
PLAYER_WIDTH = 36
PLAYER_HEIGHT = 44
GRAVITY = 0.62
JUMP_SPEED = -12.5
MOVE_SPEED = 4.2

PLATFORMS = [
    (0, 540, WIDTH, 60),
    (70, 450, 300, 18),
    (420, 360, 720, 18),
    (120, 270, 400, 18),
    (430, 180, 700, 18),
    (210, 100, 590, 18),
]

ACORN_STARTS = [
    (170, 424),
    (620, 334),
    (260, 244),
    (560, 154),
    (400, 74),
]


class RaccoonGame:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("너구리 모험")
        self.root.resizable(False, False)
        self.canvas = tk.Canvas(
            root, width=WIDTH, height=HEIGHT, bg="#b9e8ff", highlightthickness=0
        )
        self.canvas.pack()

        self.keys: set[str] = set()
        self.root.bind_all("<KeyPress>", self.on_key_down)
        self.root.bind_all("<KeyRelease>", self.on_key_up)
        self.reset_game()
        self.update()

    def reset_game(self) -> None:
        self.player_x = 35.0
        self.player_y = 496.0
        self.player_vy = 0.0
        self.facing = 1
        self.grounded = False
        self.lives = 3
        self.collected: set[int] = set()
        self.invulnerable_until = 0.0
        self.game_state = "playing"
        self.keys.clear()
        self.acorns = list(ACORN_STARTS)
        self.enemies = [
            {"x": 145.0, "y": 421.0, "left": 85.0, "right": 270.0, "speed": 1.8},
            {"x": 180.0, "y": 241.0, "left": 135.0, "right": 360.0, "speed": 2.2},
            {"x": 490.0, "y": 71.0, "left": 225.0, "right": 560.0, "speed": 1.6},
        ]

    def on_key_down(self, event: tk.Event) -> None:
        key = event.keysym.lower()
        if key == "r" and self.game_state != "playing":
            self.reset_game()
            return
        if key in {"left", "right", "a", "d", "space", "up", "w"}:
            if key not in self.keys and key in {"space", "up", "w"}:
                if self.grounded and self.game_state == "playing":
                    self.player_vy = JUMP_SPEED
                    self.grounded = False
            self.keys.add(key)

    def on_key_up(self, event: tk.Event) -> None:
        self.keys.discard(event.keysym.lower())

    def update(self) -> None:
        if self.game_state == "playing":
            self.move_player()
            self.move_enemies()
            self.collect_acorns()
            self.check_enemy_collision()
            self.check_exit()
        self.draw()
        self.root.after(16, self.update)

    def move_player(self) -> None:
        dx = 0.0
        if "left" in self.keys or "a" in self.keys:
            dx -= MOVE_SPEED
            self.facing = -1
        if "right" in self.keys or "d" in self.keys:
            dx += MOVE_SPEED
            self.facing = 1

        self.player_x = max(0, min(WIDTH - PLAYER_WIDTH, self.player_x + dx))
        old_bottom = self.player_y + PLAYER_HEIGHT
        self.player_vy = min(self.player_vy + GRAVITY, 13)
        self.player_y += self.player_vy
        self.grounded = False

        if self.player_vy >= 0:
            new_bottom = self.player_y + PLAYER_HEIGHT
            player_right = self.player_x + PLAYER_WIDTH
            for px, py, pw, _ph in PLATFORMS:
                overlaps = player_right > px and self.player_x < px + pw
                if overlaps and old_bottom <= py and new_bottom >= py:
                    self.player_y = py - PLAYER_HEIGHT
                    self.player_vy = 0
                    self.grounded = True
                    break

        if self.player_y > HEIGHT:
            self.lose_life()

    def move_enemies(self) -> None:
        for enemy in self.enemies:
            enemy["x"] += enemy["speed"]
            if enemy["x"] < enemy["left"] or enemy["x"] + 34 > enemy["right"]:
                enemy["speed"] *= -1
                enemy["x"] += enemy["speed"] * 2

    def collect_acorns(self) -> None:
        px1 = self.player_x
        py1 = self.player_y
        px2 = px1 + PLAYER_WIDTH
        py2 = py1 + PLAYER_HEIGHT
        for index, (ax, ay) in enumerate(self.acorns):
            if index in self.collected:
                continue
            if px1 < ax + 14 and px2 > ax - 14 and py1 < ay + 14 and py2 > ay - 14:
                self.collected.add(index)

    def check_enemy_collision(self) -> None:
        if time.monotonic() < self.invulnerable_until:
            return
        px1, py1 = self.player_x + 4, self.player_y + 5
        px2, py2 = self.player_x + PLAYER_WIDTH - 4, self.player_y + PLAYER_HEIGHT
        for enemy in self.enemies:
            ex1, ey1 = enemy["x"], enemy["y"]
            if px1 < ex1 + 34 and px2 > ex1 and py1 < ey1 + 28 and py2 > ey1:
                self.lose_life()
                return

    def lose_life(self) -> None:
        self.lives -= 1
        if self.lives <= 0:
            self.game_state = "lost"
            return
        self.player_x = 35.0
        self.player_y = 496.0
        self.player_vy = 0.0
        self.invulnerable_until = time.monotonic() + 1.5

    def check_exit(self) -> None:
        if len(self.collected) == len(self.acorns):
            if self.player_x + PLAYER_WIDTH > 735 and self.player_y + PLAYER_HEIGHT > 480:
                self.game_state = "won"

    def draw(self) -> None:
        self.canvas.delete("all")
        self.draw_background()
        self.draw_platforms()
        self.draw_exit()
        self.draw_acorns()
        self.draw_enemies()
        self.draw_player()
        self.draw_hud()

        if self.game_state == "won":
            self.draw_overlay("모든 도토리를 모았어요!", "R 키를 눌러 다시 하기")
        elif self.game_state == "lost":
            self.draw_overlay("게임 오버", "R 키를 눌러 다시 하기")

    def draw_background(self) -> None:
        self.canvas.create_rectangle(0, 0, WIDTH, HEIGHT, fill="#b9e8ff", outline="")
        self.canvas.create_oval(45, 70, 125, 150, fill="#fff3a6", outline="")
        for x, y in [(160, 115), (545, 65), (700, 245)]:
            self.canvas.create_oval(x, y, x + 80, y + 24, fill="#e9f8ff", outline="")
            self.canvas.create_oval(x + 16, y - 12, x + 52, y + 22, fill="#e9f8ff", outline="")
            self.canvas.create_oval(x + 40, y - 8, x + 70, y + 22, fill="#e9f8ff", outline="")

    def draw_platforms(self) -> None:
        for x, y, width, height in PLATFORMS:
            self.canvas.create_rectangle(
                x, y, x + width, y + height, fill="#8b5a2b", outline="#65401f", width=2
            )
            self.canvas.create_rectangle(
                x, y, x + width, y + 5, fill="#58b947", outline=""
            )
            for mark_x in range(int(x + 18), int(x + width - 8), 36):
                self.canvas.create_line(mark_x, y + 8, mark_x + 8, y + 15, fill="#a96c37")

    def draw_exit(self) -> None:
        color = "#62c370" if len(self.collected) == len(self.acorns) else "#9a7a5a"
        self.canvas.create_rectangle(744, 492, 786, 540, fill=color, outline="#4d3827", width=3)
        self.canvas.create_oval(774, 515, 780, 521, fill="#fff3a6", outline="")
        label = "출구" if len(self.collected) == len(self.acorns) else "도토리!"
        self.canvas.create_text(765, 480, text=label, fill="#234", font=("Arial", 10, "bold"))

    def draw_acorns(self) -> None:
        for index, (x, y) in enumerate(self.acorns):
            if index in self.collected:
                continue
            self.canvas.create_oval(x - 10, y - 9, x + 10, y + 11, fill="#a85b24", outline="#693712")
            self.canvas.create_arc(
                x - 11, y - 13, x + 11, y + 1, start=0, extent=180,
                fill="#7c421d", outline="#693712", width=2,
            )
            self.canvas.create_line(x, y - 12, x + 3, y - 17, fill="#467b35", width=2)

    def draw_enemies(self) -> None:
        for enemy in self.enemies:
            x, y = enemy["x"], enemy["y"]
            self.canvas.create_oval(x, y + 7, x + 34, y + 27, fill="#c94c4c", outline="#7f2929", width=2)
            self.canvas.create_oval(x + 20, y, x + 36, y + 17, fill="#d96858", outline="#7f2929", width=2)
            self.canvas.create_oval(x + 28, y + 5, x + 31, y + 8, fill="white", outline="")
            self.canvas.create_oval(x + 29, y + 6, x + 31, y + 8, fill="#222", outline="")
            self.canvas.create_line(x + 5, y + 24, x + 2, y + 29, fill="#462b28", width=3)
            self.canvas.create_line(x + 24, y + 24, x + 27, y + 29, fill="#462b28", width=3)

    def draw_player(self) -> None:
        if time.monotonic() < self.invulnerable_until and int(time.monotonic() * 10) % 2:
            return
        x, y = self.player_x, self.player_y
        tail_x = x + (30 if self.facing > 0 else 6)
        self.canvas.create_oval(tail_x - 8, y + 22, tail_x + 8, y + 42, fill="#777", outline="#333", width=2)
        self.canvas.create_arc(
            tail_x - 8, y + 24, tail_x + 8, y + 34, start=0, extent=180,
            style=tk.ARC, outline="#eee", width=4,
        )
        self.canvas.create_oval(x + 5, y + 17, x + 31, y + 43, fill="#8d8d8d", outline="#30343b", width=2)
        self.canvas.create_oval(x + 7, y, x + 29, y + 24, fill="#999", outline="#30343b", width=2)
        self.canvas.create_polygon(x + 8, y + 7, x + 9, y - 3, x + 15, y + 3, fill="#777", outline="#30343b")
        self.canvas.create_polygon(x + 21, y + 3, x + 27, y - 3, x + 28, y + 8, fill="#777", outline="#30343b")
        self.canvas.create_oval(x + 6, y + 8, x + 30, y + 17, fill="#30343b", outline="")
        eye_x = x + (23 if self.facing > 0 else 13)
        self.canvas.create_oval(eye_x, y + 8, eye_x + 4, y + 12, fill="white", outline="")
        self.canvas.create_oval(eye_x + 2, y + 9, eye_x + 4, y + 12, fill="#222", outline="")
        self.canvas.create_oval(x + 16, y + 14, x + 21, y + 18, fill="#f3c6a5", outline="")
        self.canvas.create_oval(x + 12, y + 37, x + 18, y + 44, fill="#e7b889", outline="")
        self.canvas.create_oval(x + 22, y + 37, x + 28, y + 44, fill="#e7b889", outline="")

    def draw_hud(self) -> None:
        self.canvas.create_rectangle(0, 0, WIDTH, 38, fill="#203849", outline="")
        self.canvas.create_text(
            16, 19, anchor="w", fill="white", font=("Arial", 13, "bold"),
            text=f"도토리: {len(self.collected)}/{len(self.acorns)}",
        )
        self.canvas.create_text(
            WIDTH - 16, 19, anchor="e", fill="white", font=("Arial", 13, "bold"),
            text=f"목숨: {'♥ ' * self.lives}",
        )
        self.canvas.create_text(
            WIDTH / 2, 19, fill="#eaf7ff", font=("Arial", 10),
            text="이동: ← → 또는 A/D    점프: Space / ↑ / W",
        )

    def draw_overlay(self, title: str, subtitle: str) -> None:
        self.canvas.create_rectangle(150, 220, 650, 360, fill="#172b3d", outline="#fff", width=2)
        self.canvas.create_text(400, 270, text=title, fill="white", font=("Arial", 24, "bold"))
        self.canvas.create_text(400, 315, text=subtitle, fill="#d8efff", font=("Arial", 14))


def main() -> None:
    root = tk.Tk()
    RaccoonGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
