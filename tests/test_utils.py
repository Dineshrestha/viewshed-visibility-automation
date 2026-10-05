import pytest

from src.utils import estimate_tile_count, height_to_meters, safe_name, tile_ranges


def test_safe_name():
    assert safe_name("Site 12 / West") == "Site_12_West"
    assert safe_name("123") == "id_123"


def test_height_to_meters():
    assert height_to_meters(100, "Feet") == pytest.approx(30.48)
    assert height_to_meters(20, "Meters") == pytest.approx(20)


def test_tile_ranges_cover_interval():
    ranges = list(tile_ranges(0, 250, 100))
    assert ranges == [(0, 100), (100, 200), (200, 250)]


def test_estimate_tile_count():
    assert estimate_tile_count(420_000, 210_000, 30, 7000) == 2
