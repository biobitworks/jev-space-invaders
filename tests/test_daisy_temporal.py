from src.daisy.eca_temporal_corpus import H,graph_rows

def test_temporal_rule0_represents_full_action_space():
    rows,summary=graph_rows(0,"single",8)
    assert summary["root_safe_action_strings"]==3**H
    assert summary["state_compression_ratio"]>0.99
    assert rows
    assert all(r["delta_G_star"]=="NOT_COMPUTED" for r in rows)
    assert all("recommended_action" not in r for r in rows)

def test_temporal_graph_is_deterministic():
    assert graph_rows(110,"rand1",4)==graph_rows(110,"rand1",4)

