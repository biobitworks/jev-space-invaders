import hashlib

from src.fmo import hp, merkle, mmr_leaf, mmr_root


def test_hp_matches_source_freeze_rule():
    # same byte layout as scripts/verify_source_freeze.py
    expect = hashlib.sha256(b"FMO_LEAF_V1\0a.txt\x003\0abc").digest()
    assert hp("FMO_LEAF_V1", "a.txt", 3, "abc") == expect


def test_merkle_duplicates_last_on_odd():
    a, b, c = (hashlib.sha256(x).digest() for x in (b"a", b"b", b"c"))
    assert merkle([a, b, c]) == merkle([a, b, c, c])


def test_mmr_is_append_consistent():
    leaves = [mmr_leaf(i, f"BP{i}", "00" * 32, "11" * 32) for i in range(7)]
    r7, peaks = mmr_root(leaves)
    assert len(peaks) == 3            # 7 = 4 + 2 + 1
    assert mmr_root(leaves)[0] == r7  # deterministic
    assert mmr_root(leaves[:6])[0] != r7
    assert mmr_root(leaves[:1])[0] == leaves[0].hex()
