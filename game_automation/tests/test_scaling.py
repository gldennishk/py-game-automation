from game_automation.core.scaling import logical_to_physical


def test_logical_to_physical():
    x, y = logical_to_physical(100, 200, 1.25)
    assert x == 125
    assert y == 250

