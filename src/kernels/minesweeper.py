"""Minesweeper over a fully determined hidden board: exact local-constraint inference.

The board is fixed at generation (no ontic randomness afterwards). Uncertainty is
epistemic only: which of the worlds consistent with the revealed clues is the true one.

Kernel (native, clean-room): frontier components are enumerated exactly; components are
combined with the global mine-count constraint by polynomial convolution and binomial
weights for unconstrained interior cells. Output per hidden cell: exact mine probability
and a label SAFE / UNSAFE / UNKNOWN.

Oracle (independent): python-sat cardinality encoding; a cell is SAFE if "mine" is UNSAT,
UNSAFE if "safe" is UNSAT, else UNKNOWN.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from fractions import Fraction

MAX_COMPONENT_VARS = 28


@dataclass
class Board:
    h: int
    w: int
    mines: frozenset
    seed: int

    def neigh(self, c):
        y, x = c
        return [(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1)
                if (dy or dx) and 0 <= y + dy < self.h and 0 <= x + dx < self.w]

    def clue(self, c) -> int:
        return sum(n in self.mines for n in self.neigh(c))

    def cells(self):
        return [(y, x) for y in range(self.h) for x in range(self.w)]


def generate(h: int, w: int, n_mines: int, seed: int, safe_start: tuple[int, int]) -> Board:
    rng = random.Random(seed)
    b0 = Board(h, w, frozenset(), seed)
    forbidden = {safe_start, *b0.neigh(safe_start)}
    pool = [c for c in b0.cells() if c not in forbidden]
    return Board(h, w, frozenset(rng.sample(pool, n_mines)), seed)


@dataclass
class View:
    board: Board
    revealed: dict = field(default_factory=dict)   # cell -> clue

    def reveal(self, c) -> bool:
        """Reveal with zero-flood. Returns False if c is a mine."""
        if c in self.board.mines:
            return False
        stack = [c]
        while stack:
            cur = stack.pop()
            if cur in self.revealed:
                continue
            k = self.board.clue(cur)
            self.revealed[cur] = k
            if k == 0:
                stack += [n for n in self.board.neigh(cur) if n not in self.revealed]
        return True

    def hidden(self):
        return [c for c in self.board.cells() if c not in self.revealed]

    def signature(self) -> list:
        return sorted([y, x, k] for (y, x), k in self.revealed.items())


def _constraints(view: View, extra: dict | None = None):
    b = view.board
    rev = dict(view.revealed)
    if extra:
        rev.update(extra)
    hidden = [c for c in b.cells() if c not in rev]
    cons = []
    for c, k in rev.items():
        hs = [n for n in b.neigh(c) if n not in rev]
        if hs:
            cons.append((hs, k))
        elif k != 0 and sum(1 for n in b.neigh(c) if n not in rev) == 0 and k > 0:
            cons.append(([], k))  # impossible unless k == 0
    return hidden, cons


def _components(cons):
    parent = {}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for hs, _ in cons:
        for c in hs:
            parent.setdefault(c, c)
        for c in hs[1:]:
            parent[find(c)] = find(hs[0])
    groups = {}
    for c in parent:
        groups.setdefault(find(c), []).append(c)
    comps = []
    for vars_ in groups.values():
        vs = set(vars_)
        comps.append((sorted(vars_), [(hs, k) for hs, k in cons if hs and hs[0] in vs]))
    return comps


def _enumerate(vars_, cons):
    """Exact enumeration -> {m: (count, {var: count_with_mine})}."""
    idx = {v: i for i, v in enumerate(vars_)}
    cons_i = [([idx[v] for v in hs], k) for hs, k in cons]
    by_var = [[] for _ in vars_]
    for j, (vs, _) in enumerate(cons_i):
        for v in vs:
            by_var[v].append(j)
    assign = [None] * len(vars_)
    out: dict[int, list] = {}

    def ok(j):
        vs, k = cons_i[j]
        s = sum(1 for v in vs if assign[v] == 1)
        u = sum(1 for v in vs if assign[v] is None)
        return s <= k <= s + u

    def rec(i):
        if i == len(vars_):
            m = sum(assign)
            e = out.setdefault(m, [0, [0] * len(vars_)])
            e[0] += 1
            for v, a in enumerate(assign):
                e[1][v] += a
            return
        for val in (0, 1):
            assign[i] = val
            if all(ok(j) for j in by_var[i]):
                rec(i + 1)
        assign[i] = None

    rec(0)
    return {m: (c, dict(zip(vars_, per))) for m, (c, per) in out.items()}


def _polymul(a: dict, b: dict) -> dict:
    out = {}
    for i, x in a.items():
        for j, y in b.items():
            out[i + j] = out.get(i + j, 0) + x * y
    return out


def infer(view: View, n_mines: int, extra: dict | None = None) -> dict:
    """Exact posterior over consistent worlds. Returns {'worlds', 'p': {cell: Fraction}, 'status'}."""
    hidden, cons = _constraints(view, extra)
    if any(not hs and k != 0 for hs, k in cons):
        return {"worlds": 0, "p": {}, "status": "INCONSISTENT"}
    comps = _components([c for c in cons if c[0]])
    if any(len(v) > MAX_COMPONENT_VARS for v, _ in comps):
        return {"worlds": None, "p": {}, "status": "BUDGET_EXCEEDED"}
    frontier = {v for vs, _ in comps for v in vs}
    interior = [c for c in hidden if c not in frontier]
    enums = [_enumerate(vs, cs) for vs, cs in comps]
    polys = [{m: e[0] for m, e in en.items()} for en in enums]
    if any(not p for p in polys):
        return {"worlds": 0, "p": {}, "status": "INCONSISTENT"}
    nI = len(interior)

    def total(poly):
        return sum(c * math.comb(nI, n_mines - m) for m, c in poly.items() if 0 <= n_mines - m <= nI)

    full = {0: 1}
    for p in polys:
        full = _polymul(full, p)
    W = total(full)
    if W == 0:
        return {"worlds": 0, "p": {}, "status": "INCONSISTENT"}
    p = {}
    for ci, en in enumerate(enums):
        others = {0: 1}
        for cj, q in enumerate(polys):
            if cj != ci:
                others = _polymul(others, q)
        for v in comps[ci][0]:
            num = 0
            for m, (_, per) in en.items():
                for mo, co in others.items():
                    rem = n_mines - m - mo
                    if 0 <= rem <= nI:
                        num += per[v] * co * math.comb(nI, rem)
            p[v] = Fraction(num, W)
    if nI:
        # expected interior mines / nI
        num = sum(c * math.comb(nI, n_mines - m) * (n_mines - m)
                  for m, c in full.items() if 0 <= n_mines - m <= nI)
        pi = Fraction(num, W * nI)
        for c in interior:
            p[c] = pi
    return {"worlds": W, "p": p, "status": "OK"}


def labels(post: dict) -> dict:
    return {c: ("SAFE" if q == 0 else "UNSAFE" if q == 1 else "UNKNOWN") for c, q in post["p"].items()}


def oracle_labels(view: View, n_mines: int) -> dict:
    from pysat.card import CardEnc, EncType
    from pysat.formula import IDPool
    from pysat.solvers import Minisat22

    b = view.board
    hidden = view.hidden()
    pool = IDPool()
    var = {c: pool.id(("x",) + c) for c in hidden}
    clauses = []
    for c, k in view.revealed.items():
        hs = [var[n] for n in b.neigh(c) if n in var]
        if hs:
            clauses += CardEnc.equals(lits=hs, bound=k, vpool=pool, encoding=EncType.seqcounter).clauses
    clauses += CardEnc.equals(lits=list(var.values()), bound=n_mines, vpool=pool,
                              encoding=EncType.totalizer).clauses
    out = {}
    with Minisat22(bootstrap_with=clauses) as s:
        for c in hidden:
            can_mine = s.solve(assumptions=[var[c]])
            can_safe = s.solve(assumptions=[-var[c]])
            out[c] = "SAFE" if not can_mine else "UNSAFE" if not can_safe else "UNKNOWN"
    return out


def outcome_distribution(view: View, n_mines: int, c, base: dict) -> dict:
    """P(outcome) for probing c: 'mine' or clue value 0..8 (exact, by conditioning)."""
    W = base["worlds"]
    dist = {"mine": base["p"][c]}
    for k in range(0, 9):
        post = infer(view, n_mines, extra={c: k})
        if post["status"] == "OK" and post["worlds"]:
            dist[str(k)] = Fraction(post["worlds"], W)
    return dist


def entropy_bits(dist: dict) -> float:
    return -sum(float(q) * math.log2(float(q)) for q in dist.values() if q > 0)
