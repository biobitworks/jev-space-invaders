import random

import numpy as np
import pytest

from src.kernels import life, minesweeper as ms
from src.kernels.address import address_str, parse_address, rank, state_content_id, unrank
from src.kernels.eca import eca_step
from src.s01.protocol import make_packet, validate


def test_address_roundtrip_and_not_hash():
    rng = random.Random(0)
    for k, n in [(2, 10), (26, 7), (256, 5)]:
        s = [rng.randrange(k) for _ in range(n)]
        a = rank(s, k)
        assert unrank(*parse_address(address_str(a, k, n))) == s
        assert address_str(a, k, n) != state_content_id(s, k)


def test_eca_rule30_known_step():
    row = [0] * 7
    row[3] = 1
    assert eca_step(row, 30) == [0, 0, 1, 1, 1, 0, 0]
    assert eca_step(row, 90) == [0, 0, 1, 0, 1, 0, 0]


def test_life_glider_moves_and_is_classified():
    g = life.place(life.parse(life.CATALOGUE_CELLS["glider"]), 16, 16, 2, 2)
    g4 = g
    for _ in range(4):
        g4 = life.step(g4)
    assert np.array_equal(np.roll(np.roll(g, 1, 0), 1, 1), g4)
    assert life.objects(g4) == ["glider"]


def test_minesweeper_kernel_matches_sat_oracle():
    for seed in range(10):
        b = ms.generate(9, 9, 10, seed, (4, 4))
        v = ms.View(b)
        v.reveal((4, 4))
        post = ms.infer(v, 10)
        assert ms.labels(post) == ms.oracle_labels(v, 10)
        assert not any(c in b.mines and lab == "SAFE" for c, lab in ms.labels(post).items())


def test_packet_refuses_recommended_move_and_validates():
    q = {"type": "choice", "instructions": "x"}
    p = make_packet("eca", [], {"a": 1}, ["L", "R"], q, {"name": "public-ref", "version": "1"}, 0.1)
    validate(p, "S01_CONTEXT_PACKET_V1")
    with pytest.raises(ValueError):
        make_packet("eca", [], {"hint": {"recommended_move": "L"}}, ["L", "R"], q, {"name": "x", "version": "1"}, 0.1)
