"""Tests for batch aggregation."""

from datetime import datetime, timedelta
from bioscan.batch.aggregator import BatchAggregator

def test_batch_aggregator() -> None:
    agg = BatchAggregator(["food_organic", "plastic"])
    
    t0 = datetime(2030, 1, 1, 12, 0, 0)
    
    assert not agg.is_ready(window_frames=2)
    
    agg.add_frame({"food_organic": 2.0}, t0)
    assert agg.n_frames == 1
    assert not agg.is_ready(window_frames=2)
    assert not agg.is_ready(window_seconds=2)
    
    agg.add_frame({"food_organic": 3.0, "plastic": 1.0}, t0 + timedelta(seconds=2.5))
    assert agg.n_frames == 2
    
    assert agg.is_ready(window_frames=2)
    assert agg.is_ready(window_seconds=2)
    
    batch = agg.finalize()
    assert batch.n_frames == 2
    assert batch.t_start == t0
    assert batch.t_end == t0 + timedelta(seconds=2.5)
    assert batch.mass_by_class == {"food_organic": 5.0, "plastic": 1.0}
    assert batch.total_mass_kg == 6.0
    
    # Aggregator should be empty now
    assert agg.n_frames == 0

