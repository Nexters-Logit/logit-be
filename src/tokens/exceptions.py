class InsufficientTokensError(Exception):
    def __init__(self, current: int, required: int) -> None:
        self.current = current
        self.required = required
        super().__init__(f"토큰 부족: 필요 {required}, 보유 {current}")
