from src.state import encode_state

def test_delta_indices():
    a = [0] * 128
    b = a.copy()
    b[3] = 9
    b[127] = 1
    s = encode_state(1, 0, b, a, 3)
    assert s["delta_indices"] == [3, 127]
    assert len(s["ram"]) == 128
