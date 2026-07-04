from dataclasses import dataclass
from math import cos, sin


CARD_WIDTH = 250
CARD_HEIGHT = 170
TERRITORY_W = 258
TERRITORY_H = 184


@dataclass(frozen=True)
class Rect:
    left: int
    top: int
    right: int
    bottom: int


@dataclass(frozen=True)
class PlacedCard:
    id: str
    x: int
    y: int
    width: int = CARD_WIDTH
    height: int = CARD_HEIGHT


def territory(x: int, y: int) -> Rect:
    half_w = TERRITORY_W // 2
    half_h = TERRITORY_H // 2
    return Rect(left=x - half_w, top=y - half_h, right=x + half_w, bottom=y + half_h)


def collides(a: Rect, b: Rect) -> bool:
    return a.left < b.right and a.right > b.left and a.top < b.bottom and a.bottom > b.top


def is_legal(x: int, y: int, cards: list[PlacedCard], canvas_width: int, ignore_id: str | None = None) -> bool:
    if x < CARD_WIDTH // 2 or x > canvas_width - CARD_WIDTH // 2:
        return False
    if y < CARD_HEIGHT // 2:
        return False
    rect = territory(x, y)
    for card in cards:
        if ignore_id and card.id == ignore_id:
            continue
        if collides(rect, territory(card.x, card.y)):
            return False
    return True


def find_nearest_legal(
    x: int,
    y: int,
    cards: list[PlacedCard],
    canvas_width: int,
    ignore_id: str | None = None,
    step: int = 20,
    max_radius: int = 300,
) -> tuple[int, int]:
    x = max(CARD_WIDTH // 2, min(x, canvas_width - CARD_WIDTH // 2))
    y = max(CARD_HEIGHT // 2, y)
    if is_legal(x, y, cards, canvas_width, ignore_id=ignore_id):
        return x, y

    samples_per_ring = 24
    for radius in range(step, max_radius + step, step):
        for idx in range(samples_per_ring):
            angle = idx / samples_per_ring * 6.28318530718
            cx = round(x + cos(angle) * radius)
            cy = round(y + sin(angle) * radius)
            if is_legal(cx, cy, cards, canvas_width, ignore_id=ignore_id):
                return cx, cy

    lowest = max((card.y for card in cards if not ignore_id or card.id != ignore_id), default=CARD_HEIGHT)
    cy = lowest + CARD_HEIGHT
    cx = x
    while True:
        if is_legal(cx, cy, cards, canvas_width, ignore_id=ignore_id):
            return cx, cy
        cy += step
