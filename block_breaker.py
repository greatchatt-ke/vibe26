import tkinter as tk


WIDTH = 800
HEIGHT = 600
PADDLE_WIDTH = 110
PADDLE_HEIGHT = 14
BALL_SIZE = 16
PADDLE_SPEED = 9
BALL_SPEED = 5
ROWS = 5
COLUMNS = 10
BLOCK_WIDTH = 68
BLOCK_HEIGHT = 22
BLOCK_GAP = 7


class BreakoutGame:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("블록깨기")
        self.root.resizable(False, False)

        self.canvas = tk.Canvas(
            root, width=WIDTH, height=HEIGHT, bg="#101827", highlightthickness=0
        )
        self.canvas.pack()

        self.keys: set[str] = set()
        self.root.bind("<KeyPress-Left>", lambda _event: self.keys.add("Left"))
        self.root.bind("<KeyRelease-Left>", lambda _event: self.keys.discard("Left"))
        self.root.bind("<KeyPress-Right>", lambda _event: self.keys.add("Right"))
        self.root.bind("<KeyRelease-Right>", lambda _event: self.keys.discard("Right"))
        self.root.bind("<space>", self.launch_ball)
        self.root.bind("<KeyPress-r>", self.restart)
        self.root.bind("<KeyPress-R>", self.restart)

        self.reset_game()
        self.update()

    def reset_game(self, _event: tk.Event | None = None) -> None:
        self.canvas.delete("all")
        self.keys.clear()
        self.score = 0
        self.lives = 3
        self.ball_launched = False
        self.game_over = False
        self.ball_dx = 0.0
        self.ball_dy = 0.0

        self.score_text = self.canvas.create_text(
            20, 20, anchor="nw", fill="white", font=("Arial", 16, "bold"),
            text="점수: 0",
        )
        self.lives_text = self.canvas.create_text(
            WIDTH - 20, 20, anchor="ne", fill="white",
            font=("Arial", 16, "bold"), text="남은 목숨: 3",
        )

        center_x = WIDTH / 2
        paddle_y = HEIGHT - 55
        self.paddle = self.canvas.create_rectangle(
            center_x - PADDLE_WIDTH / 2,
            paddle_y,
            center_x + PADDLE_WIDTH / 2,
            paddle_y + PADDLE_HEIGHT,
            fill="#36c5f0",
            outline="",
        )
        self.ball = self.canvas.create_oval(
            0, 0, BALL_SIZE, BALL_SIZE, fill="#ffffff", outline=""
        )
        self.blocks: dict[int, int] = {}
        colors = ["#ff6b6b", "#ff9f43", "#feca57", "#1dd1a1", "#54a0ff"]
        total_width = COLUMNS * BLOCK_WIDTH + (COLUMNS - 1) * BLOCK_GAP
        start_x = (WIDTH - total_width) / 2
        for row in range(ROWS):
            for column in range(COLUMNS):
                x1 = start_x + column * (BLOCK_WIDTH + BLOCK_GAP)
                y1 = 70 + row * (BLOCK_HEIGHT + BLOCK_GAP)
                block = self.canvas.create_rectangle(
                    x1, y1, x1 + BLOCK_WIDTH, y1 + BLOCK_HEIGHT,
                    fill=colors[row], outline="",
                )
                self.blocks[block] = 10 * (ROWS - row)

        self.show_message("스페이스바를 눌러 시작")
        self.place_ball_on_paddle()

    def restart(self, _event: tk.Event | None = None) -> None:
        self.reset_game()

    def launch_ball(self, _event: tk.Event | None = None) -> None:
        if not self.ball_launched and not self.game_over:
            self.ball_launched = True
            self.ball_dx = BALL_SPEED
            self.ball_dy = -BALL_SPEED
            self.canvas.delete("message")

    def show_message(self, message: str) -> None:
        self.canvas.delete("message")
        self.canvas.create_text(
            WIDTH / 2,
            HEIGHT / 2,
            text=message,
            fill="white",
            font=("Arial", 24, "bold"),
            tags="message",
        )

    def place_ball_on_paddle(self) -> None:
        paddle = self.canvas.coords(self.paddle)
        center_x = (paddle[0] + paddle[2]) / 2
        y = paddle[1] - BALL_SIZE
        self.canvas.coords(
            self.ball, center_x - BALL_SIZE / 2, y,
            center_x + BALL_SIZE / 2, y + BALL_SIZE,
        )

    def update(self) -> None:
        if not self.game_over:
            self.move_paddle()
            if self.ball_launched:
                self.move_ball()
            else:
                self.place_ball_on_paddle()
        self.root.after(16, self.update)

    def move_paddle(self) -> None:
        x1, y1, x2, y2 = self.canvas.coords(self.paddle)
        dx = 0
        if "Left" in self.keys:
            dx -= PADDLE_SPEED
        if "Right" in self.keys:
            dx += PADDLE_SPEED
        dx = max(-x1, min(dx, WIDTH - x2))
        self.canvas.move(self.paddle, dx, 0)

    def move_ball(self) -> None:
        self.canvas.move(self.ball, self.ball_dx, self.ball_dy)
        x1, y1, x2, y2 = self.canvas.coords(self.ball)

        if x1 <= 0 or x2 >= WIDTH:
            self.ball_dx *= -1
        if y1 <= 0:
            self.ball_dy = abs(self.ball_dy)
        if y2 >= HEIGHT:
            self.lives -= 1
            self.canvas.itemconfigure(
                self.lives_text, text=f"남은 목숨: {self.lives}"
            )
            if self.lives <= 0:
                self.end_game("게임 오버")
            else:
                self.ball_launched = False
                self.show_message("스페이스바를 눌러 다시 시작")
                self.place_ball_on_paddle()
            return

        self.hit_paddle(x1, y1, x2, y2)
        self.hit_block(x1, y1, x2, y2)

    def hit_paddle(self, x1: float, y1: float, x2: float, y2: float) -> None:
        ball_center_x = (x1 + x2) / 2
        paddle_x1, paddle_y1, paddle_x2, _paddle_y2 = self.canvas.coords(
            self.paddle
        )
        if (
            self.ball_dy > 0
            and y2 >= paddle_y1
            and y1 <= paddle_y1 + PADDLE_HEIGHT
            and x2 >= paddle_x1
            and x1 <= paddle_x2
        ):
            offset = (ball_center_x - (paddle_x1 + paddle_x2) / 2) / (
                PADDLE_WIDTH / 2
            )
            self.ball_dx = offset * BALL_SPEED * 0.9
            self.ball_dy = -max(
                2.5, (BALL_SPEED**2 - self.ball_dx**2) ** 0.5
            )

    def hit_block(self, x1: float, y1: float, x2: float, y2: float) -> None:
        for block, points in list(self.blocks.items()):
            bx1, by1, bx2, by2 = self.canvas.coords(block)
            if x2 < bx1 or x1 > bx2 or y2 < by1 or y1 > by2:
                continue

            overlap_x = min(x2 - bx1, bx2 - x1)
            overlap_y = min(y2 - by1, by2 - y1)
            if overlap_x < overlap_y:
                self.ball_dx *= -1
            else:
                self.ball_dy *= -1
            self.canvas.delete(block)
            del self.blocks[block]
            self.score += points
            self.canvas.itemconfigure(self.score_text, text=f"점수: {self.score}")

            if not self.blocks:
                self.end_game("승리!")
            return

    def end_game(self, message: str) -> None:
        self.game_over = True
        self.show_message(f"{message}\nR 키를 눌러 다시 시작")


def main() -> None:
    root = tk.Tk()
    BreakoutGame(root)
    root.mainloop()


if __name__ == "__main__":
    main()
