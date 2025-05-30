class InMemoryGameRepo:
    """Простое хранилище партий (в памяти процесса)."""

    def __init__(self):
        self.games = {}

    def add(self, game):
        self.games[game.id] = game

    def get(self, game_id):
        return self.games.get(game_id)

    def remove(self, game_id):
        self.games.pop(game_id, None)

    def all(self):
        return list(self.games.values())


# Единственный экземпляр
game_repo = InMemoryGameRepo()
