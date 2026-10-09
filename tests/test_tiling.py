"""Tests for the tiling module."""

import numpy as np

from bioscan.config_loader import GridConfig
from bioscan.ingest.tiling import TileClassification, Tile, aggregate_tile_classifications, tile_frame


def test_tile_frame() -> None:
    # 500x500 frame, 224x224 tiles with 224 stride
    frame = np.zeros((500, 500, 3), dtype=np.uint8)
    grid_cfg = GridConfig(tile_size=224, stride=224, min_belt_coverage=0.3)
    
    tiles = tile_frame(frame, grid_cfg)
    
    # Grid should be:
    # row 0: x=0, x=224 (x=448 is 52px wide, 52*224 = 11648 px. 30% of 224^2 is 15052.8 px. So x=448 is discarded)
    # wait. tile_size = 224, 0 to 224, 224 to 448. (448 to 500 is 52 pixels wide). coverage = 52/224 = 0.23 < 0.3.
    # so we expect 2 rows and 2 cols = 4 tiles.
    
    assert len(tiles) == 4
    for t in tiles:
        assert t.image.shape == (224, 224, 3)

def test_aggregate_tile_classifications() -> None:
    energy_classes = ["food_organic", "plastic", "metal"]
    
    # 2 food, 1 plastic, 1 hazard
    classifications = [
        TileClassification(Tile(0, 0, np.zeros((1,1,3), dtype=np.uint8), 0, 0), "food_organic", 0.9),
        TileClassification(Tile(0, 1, np.zeros((1,1,3), dtype=np.uint8), 0, 0), "food_organic", 0.8),
        TileClassification(Tile(1, 0, np.zeros((1,1,3), dtype=np.uint8), 0, 0), "plastic", 0.7),
        TileClassification(Tile(1, 1, np.zeros((1,1,3), dtype=np.uint8), 0, 0), "_hazard_battery", 0.99, hazard_flag="battery"),
    ]
    
    comp = aggregate_tile_classifications(classifications, energy_classes)
    
    # hazard is excluded from shares
    assert comp.n_tiles == 3
    assert comp.tile_shares["food_organic"] == 2/3
    assert comp.tile_shares["plastic"] == 1/3
    assert comp.tile_shares["metal"] == 0.0
    
    assert "battery" in comp.hazard_flags
    assert comp.avg_confidence == (0.9 + 0.8 + 0.7) / 3

