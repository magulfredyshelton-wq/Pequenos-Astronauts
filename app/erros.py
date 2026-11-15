class Erro(ValueError):
    def __init__(self, status, mensagem):
        super().__init__(mensagem)
        self.status = status
