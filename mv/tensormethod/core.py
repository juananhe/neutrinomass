#!/usr/bin/env python


from typing import List, Tuple

import sympy.tensor.tensor as tensor
from basisgen import irrep
from sympy import Rational, flatten

ISOSPIN = tensor.TensorIndexType("Isospin", metric=True, dummy_fmt="I", dim=2)
COLOUR = tensor.TensorIndexType("Colour", metric=None, dummy_fmt="C", dim=3)
GENERATION = tensor.TensorIndexType("Generation", metric=None, dummy_fmt="G", dim=3)
UNDOTTED = tensor.TensorIndexType("Undotted", metric=True, dummy_fmt="U", dim=2)
DOTTED = tensor.TensorIndexType("Dotted", metric=True, dummy_fmt="D", dim=2)


class Index(tensor.TensorIndex):
    def __new__(cls, label: str, *args, **kwargs):
        # deal with negative sign for down index
        is_up = True
        if label[0] == "-":
            is_up = False
            label = label[1:]

        tensor_type = cls.classify_index(label)
        return super(Index, cls).__new__(
            cls, name=label, tensortype=tensor_type, is_up=is_up
        )

    def __init__(self, label, *args, **kwargs):
        self.label = label  # the label that was passed in

    def __neg__(self):
        is_up = self.is_up
        new_label = "-" + self.label if is_up else self.label[1:]
        return Index(label=new_label)

    @property
    def conj(self):
        # conj takes you between dotted and undotted
        if self.index_type in Index.get_lorentz_index_types().values():
            if self.index_type == "Undotted":
                return Index(label=self.label.replace("u", "d"))
            return Index(label=self.label.replace("d", "u"))

        # conj does nothing to isospin indices (implicit epsilon)
        if self.index_type == "Isospin":
            return self

        # generally lower index (only affects colour here)
        return -self

    @property
    def index_type(self):
        return str(self.tensor_index_type)

    @classmethod
    def dynkin(cls, indices):
        """Returns a tuple (# raised, # lowered) indices.

        indices: collection of Index objects

       """
        up, down = 0, 0
        for i in indices:
            if i.is_up:
                up += 1
            else:
                down += 1
        return up, down

    @classmethod
    def get_tensor_index_types(cls):
        return {"u": UNDOTTED, "d": DOTTED, "c": COLOUR, "i": ISOSPIN, "g": GENERATION}

    @classmethod
    def get_index_types(cls):
        return {
            "u": "Undotted",
            "d": "Dotted",
            "c": "Colour",
            "i": "Isospin",
            "g": "Generation",
        }

    @classmethod
    def get_sm_index_types(cls):
        return {"c": "Colour", "i": "Isospin"}

    @classmethod
    def get_lorentz_index_types(cls):
        return {"u": "Undotted", "d": "Dotted"}

    @classmethod
    def classify_index(cls, idx: str) -> tensor.TensorIndexType:
        return Index.get_tensor_index_types()[idx[0]]


class Field:
    def __init__(
        self,
        label: str,
        dynkin: str,
        charges=None,
        is_conj=False,
        comm=0,
        symmetry=None,
        **kwargs,
    ):
        """Field("A", dynkin="1 0 0 1 1", charges={"y": 1})"""

        # Initialise charges
        if charges is None:
            charges = {"y": 0}

        # make sure charges contains hypercharge
        assert "y" in charges.keys()

        # For SU(2) and SU(3), indices will always be symmetric
        if symmetry is None:
            symmetry = [[1]] * len([i for i in dynkin if int(i)])

        self.symmetry = symmetry
        self.charges = charges
        self.label = label
        self.dynkin = dynkin.strip()
        self.comm = comm
        self.is_conj = is_conj

    def __call__(self, indices: str) -> "IndexedField":
        """Returns an IndexedField object.

        Indices must match dynkin structure.

        """
        dynkin_ints = [int(i) for i in self.dynkin]
        su2_plus, su2_minus, su3_up, su3_down, su2 = dynkin_ints
        index_types = (
            [UNDOTTED] * su2_plus
            + [DOTTED] * su2_minus
            + [COLOUR] * (su3_up + su3_down)
            + [ISOSPIN] * su2
        )

        # make sure names of indices are correct (to avoid user confusion)
        assert_consistent_indices(indices.split(), index_types, (su3_up, su3_down))
        return IndexedField(
            label=self.label,
            indices=indices,
            charges=self.charges,
            is_conj=self.is_conj,
            symmetry=self.symmetry,
            comm=self.comm,
        )

    def __repr__(self):
        maybe_conj = "†" if self.is_conj else ""
        return self.label + maybe_conj + f"({self.dynkin})({self.charges['y']})"

    @property
    def y(self):
        """Return the hypercharge as a sympy rational object"""
        return self.charges["y"]

    @property
    def dynkin_ints(self):
        return tuple([int(i) for i in self.dynkin])

    @property
    def lorentz_irrep(self):
        return self.dynkin_ints[:2]

    @property
    def sm_irrep(self):
        return self.dynkin_ints[2:]

    @property
    def colour_irrep(self):
        return self.sm_irrep[:2]

    @property
    def isospin_irrep(self):
        return self.sm_irrep[2:]

    @property
    def quantum_numbers(self):
        return self.sm_irrep + (self.y,)

    @property
    def is_scalar(self):
        return self.lorentz_irrep == (0, 0)

    @property
    def is_left_fermion(self):
        return self.lorentz_irrep == (1, 0)

    @property
    def is_right_fermion(self):
        return self.lorentz_irrep == (0, 1)

    @property
    def is_fermion(self):
        return self.is_left_fermion or self.is_right_fermion

    @property
    def is_vector(self):
        return self.lorentz_irrep == (1, 1)

    def __str__(self):
        return self.__repr__()

    @property
    def _dict(self):
        return (
            self.label,
            self.dynkin,
            self.charges,
            self.is_conj,
            self.comm,
            self.symmetry,
        )

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self._dict == other._dict

    def __mul__(self, other):
        grp = "SU2 x SU2 x SU3 x SU2"
        self_irrep = irrep(grp, self.dynkin)

    @property
    def conj(self):
        dynkin = self.lorentz_irrep[::-1] + self.colour_irrep[::-1] + self.isospin_irrep
        return self.__class__(
            label=self.label,
            dynkin="".join(str(d) for d in dynkin),
            charges={k: -v for k, v in self.charges.items()},
            is_conj=(not self.is_conj),
            symmetry=self.symmetry,
            comm=self.comm,
        )


class IndexedField(tensor.Tensor, Field):
    def __new__(cls, label: str, indices: str, symmetry=None, **kwargs):
        if symmetry is None:
            symmetry = [[1]] * len(indices.split())

        # classify index types and indices by name
        # e.g. 'i0' -> isospin, 'c0' -> colour, etc.
        tensor_indices = [Index(i) for i in indices.split()]
        index_types = [i.tensor_index_type for i in tensor_indices]
        tensor_head = tensor.tensorhead(label, index_types, sym=symmetry)

        return super(IndexedField, cls).__new__(cls, tensor_head, tensor_indices)

    def __init__(
        self,
        label,
        indices,
        charges=None,
        is_conj=False,
        symmetry=None,
        comm=0,
        **kwargs,
    ):
        """Initialises IndexedField object.

        label: str
        indices: space separated str or list of str
        charges: dict (must contain "y" as key)
        is_conj: bool

        Dynkin information from Field used to create correct indices for
        IndexedField.

        """
        # Initialise charges again (in case initialised independently)
        if charges is None:
            charges = {"y": 0}
        assert "y" in charges.keys()

        Field.__init__(
            self,
            label=label,
            dynkin=get_dynkin(indices),
            charges=charges,
            is_conj=is_conj,
            symmetry=symmetry,
            comm=comm,
        )

        self.index_labels = indices

    @property
    def field(self):
        return Field(
            self.label,
            self.dynkin,
            self.charges,
            self.is_conj,
            self.symmetry,
            self.comm,
        )

    @property
    def conj(self):
        """Returns a copy of self but conjugated"""
        return self.__class__(
            label=self.label,
            indices=" ".join(i.conj.label for i in self.indices),
            charges={k: -v for k, v in self.charges.items()},
            is_conj=(not self.is_conj),
            symmetry=self.symmetry,
            comm=self.comm,
        )

    @property
    def indices_by_type(self):
        """Returns a dictionary mapping index type to tuple of indices.

        """
        result = {k: [] for k in Index.get_index_types().values()}
        for i in self.indices:
            result[i.index_type].append(i)
        return {k: tuple(v) for k, v in result.items()}

    @property
    def _dynkins(self):
        """Returns a dictionary of 2-tuples of integers mapping index type to (raised,
        lowered) indices.

        """
        return {k: Index.dynkin(v) for k, v in self.indices_by_type.items()}

    @property
    def _dict(self):
        return (
            self.label,
            self.index_labels,
            self.charges,
            self.is_conj,
            self.symmetry,
            self.comm,
        )

    def __mul__(self, other):
        pass

    def __add__(self, other):
        pass

    def __repr__(self):
        sympy_repr = super(self.__class__, self).__repr__()
        if self.is_conj:
            split_sympy_repr = sympy_repr.split("(")
            new_repr = [split_sympy_repr[0] + "†("] + split_sympy_repr[1:]
            return "".join(new_repr)
        return sympy_repr

    def __str__(self):
        return self.__repr__()

    def __eq__(self, other):
        if not isinstance(other, self.__class__):
            return False
        return self._dict == other._dict


class Operator(tensor.TensMul):
    pass


def assert_consistent_indices(
    indices: List[str],
    index_types: List[tensor.TensorIndexType],
    colour: Tuple[int, int],
):
    assert len(indices) == len(index_types)
    up_count, down_count = 0, 0
    for i, t in zip(indices, index_types):
        # make sure index names match
        assert Index(i).tensor_index_type == t

        # keep track of raised and lowered indices for colour
        if t == COLOUR:
            if i[0] == "-":
                down_count += 1
            else:
                up_count += 1
        else:
            # make sure no lowered indices for the SU2s
            assert i[0] != "-"

    assert (up_count, down_count) == colour


def get_dynkin(indices):
    """get_dynkin("u0 c0 -c1 i0") => "1 0 1 1 1"""
    dynkin = {
        "Undotted": {True: 0},
        "Dotted": {True: 0},
        "Colour": {True: 0, False: 0},
        "Isospin": {True: 0},
    }
    for i in indices.split():
        idx = Index(i)
        dynkin[idx.index_type][idx.is_up] += 1

    flat_dynkin = flatten(map(lambda x: list(x.values()), dynkin.values()))
    return "".join(str(x) for x in flat_dynkin)
