#!/usr/bin/env python3

"""Provides the Lagrangian class and associated functions for symmetry
finding.

"""

from itertools import combinations_with_replacement
from alive_progress import alive_bar
from multiset import Multiset
from sympy import Matrix
from sympy.tensor.tensor import tensorhead
from collections import Counter
import numpy as np
from typing import List

from neutrinomass.tensormethod.contract import invariants, unsimplified_invariants
from neutrinomass.completions.utils import remove_equivalent
from neutrinomass.tensormethod.core import (
    Operator,
    GENERATION,
    Index,
    decompose_product,
    Prod,
    Field,
)

from neutrinomass.tensormethod.sm import L, Q, db, H, ub, eb


def make_coupling(symbol: str, indices: str, sym=None):
    indices_list = indices.split()
    if sym is None:
        sym = [[1]] * len(indices_list)
    return tensorhead(symbol, [Index(i) for i in indices_list], sym)


def npoint_fieldstrings(n, fields=(L, eb, Q, db, ub, H), derivs=False, func=None):
    L.charges["l"] = 1
    eb.charges["l"] = -1
    Q.charges["l"] = 0
    ub.charges["l"] = 0
    db.charges["l"] = 0
    H.charges["l"] = 0

    conjs = tuple([f.conj for f in fields])
    if derivs:
        T = Field("D", "11000", charges={"y": 0, "3b": 0, "l": 0})
        fields += (T,)

    combos = list(combinations_with_replacement(fields + conjs, n))
    terms = []
    with alive_bar(len(combos)) as bar:
        while combos:
            combo = combos.pop(0)

            if func is not None:
                if not func(combo):
                    bar()
                    continue

            prods = decompose_product(*combo)
            singlets = [i for i in prods if i.is_singlet]
            if singlets:
                terms += [singlets[0]]
            bar()

    for f in fields:
        del f.charges["l"]

    return terms


def prod_mass_dim(prod: Prod) -> int:
    """Returns the mass dimension of a Prod object"""
    out = []
    while True:
        irrep, left, right = prod
        out.append(right)

        if not isinstance(left, Prod):
            out.append(left)
            return sum(map(lambda x: x.mass_dim, out))

        prod = left


def generate_fieldstrings(max_dim, fields, derivs=True):
    """Returns a product of fields of maximum dimension `max_dim` built out of
    `fields`.

    """
    out = []
    for n_fields in range(2, max_dim + 1):
        for fieldstring in npoint_fieldstrings(n_fields, fields, derivs=derivs):
            if prod_mass_dim(fieldstring.walked()) <= max_dim:
                out.append(fieldstring)

    return out


def npoint_terms(n, fields, nf=3):
    conjs = [f.conj for f in fields]
    combos = combinations_with_replacement([*fields, *conjs], n)
    terms = []
    for combo in combos:
        invs = unsimplified_invariants(*combo, ignore=[])
        terms += invs

    return terms


class Lagrangian:
    def __init__(self, exotics, terms):
        self.exotics = exotics
        self.terms = terms

    def u1_symmetries(self):
        exotics = [f.field for f in self.exotics]
        extra_0s = [0 for _ in range(len(exotics))]

        #            H  Q  ub db L eb
        yukawas = [[1, 1, 1, 0, 0, 0], [-1, 1, 0, 1, 0, 0], [-1, 0, 0, 0, 1, 1]]
        new_yukawas = [list(yuk) + extra_0s for yuk in yukawas]

        exotic_indices_nonconj = {k: v for k, v in zip(exotics, range(0, len(exotics)))}
        exotic_indices_conj = {
            k: v for k, v in zip([f.conj for f in exotics], range(0, len(exotics)))
        }
        exotic_indices = {**exotic_indices_conj, **exotic_indices_nonconj}

        matrix = []
        for term in self.terms:
            if contains(term, exotics):
                matrix += [term_to_row(term, exotics, exotic_indices)]

        matrix += new_yukawas
        X = Matrix(matrix)
        return X.nullspace()

    def num_u1_symmetries(self):
        return len(self.u1_symmetries())

    def generate_full(self):
        terms = generate_uv_terms(self.exotics)
        return Lagrangian(self.exotics, terms)


def term_to_row(term, exotics, exotic_indices):
    sm_matter = (H, Q, ub, db, L, eb)
    sm_matter_conj = [f.conj for f in sm_matter]
    index_dict_nonconj = dict(zip(sm_matter, range(6)))
    index_dict_conj = dict(zip(sm_matter_conj, range(6)))
    index_dict = {**index_dict_conj, **index_dict_nonconj}
    n_fields = len(exotics) + 6
    row = np.zeros(n_fields)
    for field, mult in Counter(term.fields).items():
        if field in [*sm_matter, *sm_matter_conj]:
            row[index_dict[field]] += mult if not field.is_conj else -mult
        else:
            row[6 + exotic_indices[field]] += mult if not field.is_conj else -mult

    return [int(i) for i in row]


def generate_uv_terms(fields: set):
    sm_matter = [H, Q, ub, db, L, eb]
    all_fields = sm_matter + [f.field for f in fields]

    cubic_terms = npoint_terms(3, all_fields)
    quartic_terms = npoint_terms(4, all_fields)

    out = []
    for term in [*cubic_terms, *quartic_terms]:
        if term.mass_dim <= 4:
            out.append(term)

    eq = lambda x, y: x.nocoeff.simplify() == y.nocoeff.simplify()
    remove_equivalent(out, eq_func=eq)
    # only keep terms that contain exotic fields
    return [i for i in out if i != 0 and contains(i, [f.field for f in fields])]


def contains(term: Operator, fields: List[Field]):
    term_fields = term.fields
    for f in fields:
        if f in term_fields or f.conj in term_fields:
            return True

    return False
