import scipy
from scipy import sparse
import inspect
import numpy as np
import math as m
from itertools import combinations
from tqdm import tqdm
import pybind.Quant_NBody_accelerate as fast

# =============================================================================
# CORE FUNCTIONS FOR THE BUILDING OF the "A_dagger A" OPERATOR
# =============================================================================

def build_nbody_basis(n_mo, N_electron, S_z_cleaning=False):
    """
    Create a many-body basis formed by a list of slater-determinants
    (i.e. their occupation number)

    Parameters
    ----------
    n_mo         :  Number of molecular orbitals
    N_electron   :  Number of electrons
    S_z_cleaning :  Option if we want to get read of the s_z != 0 states (default is False)

    Returns
    -------
    nbody_basis :  List of many-body states (occupation number states) in the basis (occupation number vectors)
    """
    # Building the N-electron many-body basis
    nbody_basis = []
    for combination in combinations(range(2 * n_mo), N_electron):
        fock_state = [0] * (2 * n_mo)
        for index in list(combination):
            fock_state[index] += 1
        nbody_basis += [fock_state]

        # In case we want to get rid of states with s_z != 0
    if S_z_cleaning:
        nbody_basis_cleaned = nbody_basis.copy()
        for i in range(np.shape(nbody_basis)[0]):
            s_z = check_sz(nbody_basis[i])
            if s_z != 0:
                nbody_basis_cleaned.remove(nbody_basis[i])
        nbody_basis = nbody_basis_cleaned

    return np.array(nbody_basis, dtype=int)


def check_sz(ref_state):
    """
    Return the value fo the S_z operator for a unique slater determinant

    Parameters
    ----------
    ref_state :  Slater determinant (list of occupation numbers)

    Returns
    -------
    s_z_slater_determinant : value of S_z for the given slater determinant
    """
    s_z_slater_determinant = 0
    for elem in range(len(ref_state)):
        if elem % 2 == 0:
            s_z_slater_determinant += + 1 * ref_state[elem] / 2
        else:
            s_z_slater_determinant += - 1 * ref_state[elem] / 2

    return s_z_slater_determinant


def update_a_dagger_a_p_q(ref_state, p, q, mapping_kappa, kappa, a_dagger_a):
    kappa_, p1p2 = fast.update_a_dagger_a_p_q_fast(ref_state, p, q, mapping_kappa)
    print(kappa_, p1p2)
    if (kappa_, p1p2) != (-10, -10):
        a_dagger_a[p, q][kappa_, kappa] = a_dagger_a[q, p][kappa, kappa_] = p1p2


def build_operator_a_dagger_a(nbody_basis, silent=False):
    """
    Create a matrix representation of the a_dagger_a operator
    in the many-body basis

    Parameters
    ----------
    nbody_basis :  List of many-body states (occupation number states) (occupation number states)
    silent      :  If it is True, function doesn't print anything when it generates a_dagger_a
    Returns
    -------
    a_dagger_a :  Matrix representation of the a_dagger_a operator

    """
    # Dimensions of problem
    dim_H = len(nbody_basis)
    n_mo = nbody_basis.shape[1] // 2
    mapping_kappa = fast.build_mapping_fast(nbody_basis)

    a_dagger_a = np.zeros((2 * n_mo, 2 * n_mo), dtype=object)
    for p in range(2 * n_mo):
        for q in range(p, 2 * n_mo):
            a_dagger_a[p, q] = scipy.sparse.lil_matrix((dim_H, dim_H))
            a_dagger_a[q, p] = scipy.sparse.lil_matrix((dim_H, dim_H))

    for MO_q in (range(n_mo)):
        for MO_p in range(MO_q, n_mo):
            for kappa in range(dim_H):
                ref_state = nbody_basis[kappa]

                # Single excitation : spin alpha -- alpha
                update_a_dagger_a_p_q(ref_state, 2 * MO_p, 2 * MO_q, mapping_kappa, kappa, a_dagger_a)
                # Single excitation : spin beta -- beta
                update_a_dagger_a_p_q(ref_state, 2 * MO_p + 1, 2 * MO_q + 1, mapping_kappa, kappa, a_dagger_a)

                if MO_p == MO_q:  # <=== Necessary to build the Spins operator but not really for Hamiltonians

                    # Single excitation : spin beta -- alpha
                    update_a_dagger_a_p_q(ref_state, 2 * MO_p + 1, 2 * MO_p, mapping_kappa, kappa, a_dagger_a)

                    # Single excitation : spin alpha -- beta
                    update_a_dagger_a_p_q(ref_state, 2 * MO_p, 2 * MO_p + 1, mapping_kappa, kappa, a_dagger_a)
    if not silent:
        print()
        print('\t ===========================================')
        print('\t ====  The matrix form of a^a is built  ====')
        print('\t ===========================================')

    return a_dagger_a


# def build_mapping(nbody_basis):
#     """
#     Function to create a unique mapping between a kappa vector and an occupation
#     number state.
#
#     Parameters
#     ----------
#     nbody_basis :  Many-
#
#     Returns
#     -------
#     mapping_kappa : List of unique values associated to each kappa
#     """
#     num_digits = np.shape(nbody_basis)[1]
#     dim_H = np.shape(nbody_basis)[0]
#     mapping_kappa = np.zeros(2 ** num_digits, dtype=np.int32)
#     for kappa in range(dim_H):
#         ref_state = nbody_basis[kappa]
#         number = 0
#         for digit in range(num_digits):
#             number += ref_state[digit] * 2 ** (num_digits - digit - 1)
#         mapping_kappa[number] = kappa
#
#     return mapping_kappa
#
#
# def make_integer_out_of_bit_vector(ref_state):
#     """
#     Function to translate a slater determinant into an unique integer
#
#     Parameters
#     ----------
#     ref_state : Reference slater determinant to turn out into an integer
#
#     Returns
#     -------
#     number : unique integer referring to the slater determinant
#     """
#     number = 0
#     for digit in range(len(ref_state)):
#         number += ref_state[digit] * 2 ** (len(ref_state) - digit - 1)
#
#     return number
#
#
# def new_state_after_sq_fermi_op(type_of_op, index_mode, ref_fock_state):
#     """
#
#     Parameters
#     ----------
#     type_of_op    :  type of operator to apply (creation of annihilation)
#     index_mode    :  index of the second quantized mode to occupy/empty
#     ref_fock_state :  initial state to be transformed
#
#     Returns
#     -------
#     new_fock_state :  Resulting occupation number form of the transformed state
#     coeff_phase   :  Phase attached to the resulting state
#
#     """
#     new_fock_state = ref_fock_state.copy()
#     coeff_phase = (-1.) ** np.sum(ref_fock_state[0:index_mode])
#     if type_of_op == 'a':
#         new_fock_state[index_mode] += -1
#     elif type_of_op == 'a^':
#         new_fock_state[index_mode] += 1
#
#     return new_fock_state, coeff_phase
#
#
# def build_final_state_ad_a(ref_state, p, q, mapping_kappa):
#     state_one, p1 = new_state_after_sq_fermi_op('a', q, ref_state)
#     state_two, p2 = new_state_after_sq_fermi_op('a^', p, state_one)
#     kappa_ = mapping_kappa[make_integer_out_of_bit_vector(state_two)]
#
#     return kappa_, p1, p2


def my_state(slater_determinant, nbody_basis):
    """
    Translate a Slater determinant (occupation number list) into a many-body
    state referenced into a given Many-body basis.

    Parameters
    ----------
    slater_determinant  : occupation number list
    nbody_basis   : List of many-body states (occupation number states)

    Returns
    -------
    state :  The slater determinant referenced in the many-body basis
    """
    kappa = np.flatnonzero((nbody_basis == slater_determinant).all(1))[0]  # nbody_basis.index(slater_determinant)
    state = np.zeros(np.shape(nbody_basis)[0])
    state[kappa] = 1.

    return state


# =============================================================================
#  MANY-BODY HAMILTONIANS (FERMI HUBBARD AND QUANTUM CHEMISTRY)
# =============================================================================

def build_hamiltonian_quantum_chemistry(h_, g_, nbody_basis, a_dagger_a, S_2=None, S_2_target=None, penalty=100):
    """
    Create a matrix representation of the electronic structure Hamiltonian in any
    extended many-body basis

    Parameters
    ----------
    h_          :  One-body integrals
    g_          :  Two-body integrals
    nbody_basis :  List of many-body states (occupation number states)
    a_dagger_a  :  Matrix representation of the a_dagger_a operator
    S_2         :  Matrix representation of the S_2 operator (default is None)
    S_2_target  :  Value of the S_2 mean value we want to target (default is None)
    penalty     :  Value of the penalty term for state not respecting the spin symmetry (default is 100).

    Returns
    -------
    H_chemistry :  Matrix representation of the electronic structure Hamiltonian

    """
    # Dimension of the problem 
    dim_H = len(nbody_basis)
    n_mo = np.shape(h_)[0]

    # Building the spin-preserving one-body excitation operator  
    E_ = np.empty((2 * n_mo, 2 * n_mo), dtype=object)
    e_ = np.empty((2 * n_mo, 2 * n_mo, 2 * n_mo, 2 * n_mo), dtype=object)
    H_chemistry = scipy.sparse.csr_matrix((dim_H, dim_H))

    for p in range(n_mo):
        for q in range(n_mo):
            E_[p, q] = a_dagger_a[2 * p, 2 * q] + a_dagger_a[2 * p + 1, 2 * q + 1]

    for p in range(n_mo):
        for q in range(n_mo):
            H_chemistry += E_[p, q] * h_[p, q]
            for r in range(n_mo):
                for s in range(n_mo):
                    e_[p, q, r, s] = E_[p, q] @ E_[r, s]
                    if q == r:
                        e_[p, q, r, s] += - E_[p, s]

                    H_chemistry += e_[p, q, r, s] * g_[p, q, r, s] / 2.

    # Reminder : S_2 = S(S+1) and the total spin multiplicity is 2S+1
    # with S = the number of unpaired electrons x 1/2
    # singlet    =>  S=0    and  S_2=0
    # doublet    =>  S=1/2  and  S_2=3/4
    # triplet    =>  S=1    and  S_2=2
    # quadruplet =>  S=3/2  and  S_2=15/4
    # quintet    =>  S=2    and  S_2=6
    if S_2 is not None and S_2_target is not None:
        s_2_minus_target = S_2 - S_2_target * np.eye(dim_H)
        H_chemistry += s_2_minus_target @ s_2_minus_target * penalty

    return H_chemistry


def build_hamiltonian_fermi_hubbard(h_, U_, nbody_basis, a_dagger_a, S_2=None, S_2_target=None, penalty=100):
    """
    Create a matrix representation of the Fermi-Hubbard Hamiltonian in any
    extended many-body basis.

    Parameters
    ----------
    h_          :  One-body integrals
    U_          :  Two-body integrals
    nbody_basis :  List of many-body states (occupation number states)
    a_dagger_a  :  Matrix representation of the a_dagger_a operator
    S_2         :  Matrix representation of the S_2 operator (default is None)
    S_2_target  :  Value of the S_2 mean value we want to target (default is None)
    penalty     :  Value of the penalty term for state not respecting the spin symmetry (default is 100).

    Returns
    -------
    H_fermi_hubbard :  Matrix representation of the Fermi-Hubbard Hamiltonian

    """
    # # Dimension of the problem 
    dim_H = len(nbody_basis)
    n_mo = np.shape(h_)[0]

    # Building the N-electron Fermi-Hubbard matrix hamiltonian (Sparse)
    H_fermi_hubbard = scipy.sparse.csr_matrix((dim_H, dim_H))
    for p in tqdm(range(n_mo)):
        for q in range(n_mo):
            H_fermi_hubbard += (a_dagger_a[2 * p, 2 * q] + a_dagger_a[2 * p + 1, 2 * q + 1]) * h_[p, q]
            for r in range(n_mo):
                for s in range(n_mo):
                    if U_[p, q, r, s] != 0:  # if U is 0, it doesn't make sense to multiply matrices
                        H_fermi_hubbard += a_dagger_a[2 * p, 2 * q] @ a_dagger_a[2 * r + 1, 2 * s + 1] * U_[p, q, r, s]

    # Reminder : S_2 = S(S+1) and the total  spin multiplicity is 2S+1 
    # with S = the number of unpaired electrons x 1/2 
    # singlet    =>  S=0    and  S_2=0 
    # doublet    =>  S=1/2  and  S_2=3/4
    # triplet    =>  S=1    and  S_2=2
    # quadruplet =>  S=3/2  and  S_2=15/4
    # quintet    =>  S=2    and  S_2=6
    if S_2 is not None and S_2_target is not None:
        s_2_minus_target = S_2 - S_2_target * np.eye(dim_H)
        H_fermi_hubbard += s_2_minus_target @ s_2_minus_target * penalty

    return H_fermi_hubbard


def fh_get_active_space_integrals(h_, U_, frozen_indices=None, active_indices=None):
    """
        >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        Restricts a Fermi-Hubard at a spatial orbital level to an active space
        This active space may be defined by a list of active indices and
        doubly occupied indices. Note that one_body_integrals and
        two_body_integrals must be defined in an orthonormal basis set (MO like).
        Args:
             - occupied_indices: A list of spatial orbital indices
               indicating which orbitals should be considered doubly occupied.
             - active_indices: A list of spatial orbital indices indicating
               which orbitals should be considered active.
             - 1 and 2 body integrals.
        Returns:
            tuple: Tuple with the following entries:
            **core_constant**: Adjustment to constant shift in Hamiltonian
            from integrating out core orbitals
            **one_body_integrals_new**: one-electron integrals over active space.
            **two_body_integrals_new**: two-electron integrals over active space.
        >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        """
    # Determine core Energy from frozen MOs
    core_energy = 0
    for i in frozen_indices:
        core_energy += 2 * h_[i, i]
        for j in frozen_indices:
            core_energy += U_[i, i, j, j]

            # Modified one-electron integrals
    h_act = h_.copy()
    for t in active_indices:
        for u in active_indices:
            for i in frozen_indices:
                h_act[t, u] += U_[i, i, t, u]

    return (core_energy,
            h_act[np.ix_(active_indices, active_indices)],
            U_[np.ix_(active_indices, active_indices, active_indices, active_indices)])


def qc_get_active_space_integrals(one_body_integrals, two_body_integrals, occupied_indices=None, active_indices=None):
    """
        >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        Restricts a Quantum chemistry Hamiltonian at a spatial orbital level 
        to an active space. This active space may be defined by a list of 
        active indices and doubly occupied indices. Note that one_body_integrals and
        two_body_integrals must be defined in an orthonormal basis set (MO like).
        Args:
             - occupied_indices: A list of spatial orbital indices
               indicating which orbitals should be considered doubly occupied.
             - active_indices: A list of spatial orbital indices indicating
               which orbitals should be considered active.
             - 1 and 2 body integrals.
        Returns:
            tuple: Tuple with the following entries:
            **core_constant**: Adjustment to constant shift in Hamiltonian
            from integrating out core orbitals
            one_body_integrals_new : one-electron integrals over active space.
            two_body_integrals_new : two-electron integrals over active space.
        >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
        """
    # Fix data type for a few edge cases
    occupied_indices = [] if occupied_indices is None else occupied_indices
    if len(active_indices) < 1:
        raise ValueError('Some active indices required for reduction.')

    # Determine core constant
    core_constant = 0.0
    for i in occupied_indices:
        core_constant += 2 * one_body_integrals[i, i]
        for j in occupied_indices:
            core_constant += (2 * two_body_integrals[i, j, i, j] - two_body_integrals[i, j, j, i])

    # Modified one electron integrals
    one_body_integrals_new = np.copy(one_body_integrals)
    for u in active_indices:
        for v in active_indices:
            for i in occupied_indices:
                one_body_integrals_new[u, v] += (2 * two_body_integrals[i, i, u, v]
                                                 - two_body_integrals[i, u, v, i])

    # Restrict integral ranges and change M appropriately
    return (core_constant,
            one_body_integrals_new[np.ix_(active_indices, active_indices)],
            two_body_integrals[np.ix_(active_indices, active_indices, active_indices, active_indices)])


# =============================================================================
#  DIFFERENT TYPES OF SPIN OPERATORS
# =============================================================================

def build_s2_sz_splus_operator(a_dagger_a):
    """
    Create a matrix representation of the spin operators s_2, s_z and s_plus
    in the many-body basis.

    Parameters
    ----------
    a_dagger_a : matrix representation of the a_dagger_a operator in the many-body basis.

    Returns
    -------
    s_2, s_plus, s_z :  matrix representation of the s_2, s_plus and s_z operators
                        in the many-body basis.
    """
    n_mo = np.shape(a_dagger_a)[0] // 2
    dim_H = np.shape(a_dagger_a[0, 0].A)[0]
    s_plus = scipy.sparse.csr_matrix((dim_H, dim_H))
    s_z = scipy.sparse.csr_matrix((dim_H, dim_H))
    for p in range(n_mo):
        s_plus += a_dagger_a[2 * p, 2 * p + 1]
        s_z += (a_dagger_a[2 * p, 2 * p] - a_dagger_a[2 * p + 1, 2 * p + 1]) / 2.

    s_2 = s_plus @ s_plus.T + s_z @ s_z - s_z

    return s_2, s_plus, s_z


# =============================================================================
#  DIFFERENT TYPES OF REDUCED DENSITY-MATRICES
# =============================================================================

def build_1rdm_alpha(WFT, a_dagger_a):
    """
    Create a spin-alpha 1 RDM out of a given wave function

    Parameters
    ----------
    WFT        :  Wave function for which we want to build the 1-RDM
    a_dagger_a :  Matrix representation of the a_dagger_a operator

    Returns
    -------
    One_RDM_alpha : spin-alpha 1-RDM

    """
    n_mo = np.shape(a_dagger_a)[0] // 2
    one_rdm_alpha = np.zeros((n_mo, n_mo))
    for p in range(n_mo):
        for q in range(p, n_mo):
            one_rdm_alpha[p, q] = WFT.T @ a_dagger_a[2 * p, 2 * q] @ WFT
            one_rdm_alpha[q, p] = one_rdm_alpha[p, q]
    return one_rdm_alpha


def build_1rdm_beta(WFT, a_dagger_a):
    """
    Create a spin-beta 1 RDM out of a given wave function

    Parameters
    ----------
    WFT        :  Wave function for which we want to build the 1-RDM
    a_dagger_a :  Matrix representation of the a_dagger_a operator

    Returns
    -------
    One_RDM_alpha : Spin-beta 1-RDM

    """
    n_mo = np.shape(a_dagger_a)[0] // 2
    one_rdm_beta = np.zeros((n_mo, n_mo))
    for p in range(n_mo):
        for q in range(p, n_mo):
            one_rdm_beta[p, q] = WFT.T @ a_dagger_a[2 * p + 1, 2 * q + 1] @ WFT
            one_rdm_beta[q, p] = one_rdm_beta[p, q]
    return one_rdm_beta


def build_1rdm_spin_free(WFT, a_dagger_a):
    """
    Create a spin-free 1 RDM out of a given wave function

    Parameters
    ----------
    WFT        :  Wave function for which we want to build the 1-RDM
    a_dagger_a :  Matrix representation of the a_dagger_a operator

    Returns
    -------
    One_RDM_alpha : Spin-free 1-RDM

    """
    n_mo = np.shape(a_dagger_a)[0] // 2
    one_rdm = np.zeros((n_mo, n_mo))
    for p in range(n_mo):
        for q in range(p, n_mo):
            E_pq = a_dagger_a[2 * p, 2 * q] + a_dagger_a[2 * p + 1, 2 * q + 1]
            one_rdm[p, q] = WFT.T @ E_pq @ WFT
            one_rdm[q, p] = one_rdm[p, q]
    return one_rdm


def build_2rdm_fh(WFT, a_dagger_a):
    """
    Create a spin-free 2 RDM out of a given Fermi Hubbard wave function

    Parameters
    ----------
    WFT        :  Wave function for which we want to build the 1-RDM
    a_dagger_a :  Matrix representation of the a_dagger_a operator

    Returns
    -------
    One_RDM_alpha : Spin-free 1-RDM

    """
    n_mo = np.shape(a_dagger_a)[0] // 2
    two_rdm_fh = np.zeros((n_mo, n_mo, n_mo, n_mo))
    for p in range(n_mo):
        for q in range(n_mo):
            for r in range(n_mo):
                for s in range(n_mo):
                    two_rdm_fh[p, q, r, s] += WFT.T @ a_dagger_a[2 * p, 2 * q] @ a_dagger_a[2 * r + 1, 2 * s + 1] @ WFT
    return two_rdm_fh


def build_2rdm_spin_free(WFT, a_dagger_a):
    """
    Create a spin-free 2 RDM out of a given wave function

    Parameters
    ----------
    WFT        :  Wave function for which we want to build the 1-RDM
    a_dagger_a :  Matrix representation of the a_dagger_a operator

    Returns
    -------
    One_RDM_alpha : Spin-free 1-RDM

    """
    n_mo = np.shape(a_dagger_a)[0] // 2
    two_rdm = np.zeros((n_mo, n_mo, n_mo, n_mo))
    two_rdm[:] = np.nan
    E_ = np.empty((2 * n_mo, 2 * n_mo), dtype=object)
    for p in range(n_mo):
        for q in range(n_mo):
            E_[p, q] = a_dagger_a[2 * p, 2 * q] + a_dagger_a[2 * p + 1, 2 * q + 1]

    for p in range(n_mo):
        for q in range(p, n_mo):
            for r in range(p, n_mo):
                for s in range(p, n_mo):
                    if np.isnan(two_rdm[p, q, r, s]):
                        two_rdm[p, q, r, s] = WFT.T @ E_[p, q] @ E_[r, s] @ WFT
                        if q == r:
                            two_rdm[p, q, r, s] += - WFT.T @ E_[p, s] @ WFT

                        # Symmetry operations:
                        two_rdm[r, s, p, q] = two_rdm[p, q, r, s]
                        two_rdm[q, p, s, r] = two_rdm[p, q, r, s]
                        two_rdm[s, r, q, p] = two_rdm[p, q, r, s]

    return two_rdm


def build_1rdm_and_2rdm_spin_free(WFT, a_dagger_a):
    """
    Create a spin-free 2 RDM out of a given wave function

    Parameters
    ----------
    WFT        :  Wave function for which we want to build the 1-RDM
    a_dagger_a :  Matrix representation of the a_dagger_a operator

    Returns
    -------
    One_RDM_alpha : Spin-free 1-RDM

    """
    n_mo = np.shape(a_dagger_a)[0] // 2
    one_rdm = np.zeros((n_mo, n_mo))
    two_rdm = np.zeros((n_mo, n_mo, n_mo, n_mo))
    two_rdm[:] = np.nan
    E_ = np.empty((2 * n_mo, 2 * n_mo), dtype=object)
    for p in range(n_mo):
        for q in range(n_mo):
            E_[p, q] = a_dagger_a[2 * p, 2 * q] + a_dagger_a[2 * p + 1, 2 * q + 1]

    for p in range(n_mo):
        for q in range(p, n_mo):
            one_rdm[p, q] = WFT.T @ E_[p, q] @ WFT
            one_rdm[q, p] = one_rdm[p, q]
            for r in range(p, n_mo):
                for s in range(p, n_mo):
                    if np.isnan(two_rdm[p, q, r, s]):
                        two_rdm[p, q, r, s] = WFT.T @ E_[p, q] @ E_[r, s] @ WFT
                        if q == r:
                            two_rdm[p, q, r, s] += - WFT.T @ E_[p, s] @ WFT

                        # Symmetry operations:
                        two_rdm[r, s, p, q] = two_rdm[p, q, r, s]
                        two_rdm[q, p, s, r] = two_rdm[p, q, r, s]
                        two_rdm[s, r, q, p] = two_rdm[p, q, r, s]

    return one_rdm, two_rdm


# =============================================================================
#  FUNCTION TO HELP THE VISUALIZATION OF MANY-BODY WAVE FUNCTIONS
# =============================================================================

def visualize_wft(WFT, nbody_basis, cutoff=0.005):
    """
    Print the decomposition of a given input wave function in a many-body basis.
    ----------
    WFT            : Reference wave function
    nbody_basis    : List of many-body states (occupation number states)
    cutoff         : Cut off for the amplitudes retained (default is 0.005)

    Returns
    -------
    Printing in the terminal the wave function

    """
    list_index = np.where(abs(WFT) > cutoff)[0]

    states = []
    coefficients = []
    for index in list_index:
        coefficients += [WFT[index]]
        states += [nbody_basis[index]]

    list_sorted_index = np.flip(np.argsort(np.abs(coefficients)))

    print()
    print('\t ----------- ')
    print('\t Coeff.      N-body state')
    print('\t -------     -------------')
    for index in list_sorted_index[0:8]:
        sign_ = '+'
        if abs(coefficients[index]) != coefficients[index]:
            sign_ = '-'
        print('\t', sign_, '{:1.5f}'.format(abs(coefficients[index])),
              '\t|{}⟩'.format(' '.join([str(elem) for elem in states[index]]).replace(" ", "")))

    return


# =============================================================================
# USEFUL TRANSFORMATIONS 
# =============================================================================


def transform_1_2_body_tensors_in_new_basis(h_b1, g_b1, C):
    """
    Transform electronic integrals from an initial basis "B1" to a new basis "B2".
    The transformation is realized thanks to a passage matrix noted "C" linking
    both basis like

            | B2_l > = \\sum_{p} | B1_p >  C_{pl}

    with | B2_l > and | B1_p > are vectors of the basis B1 and B2 respectively

    Parameters
    ----------
    h_b1 : 1-electron integral given in basis B1
    g_b1 : 2-electron integral given in basis B1
    C    : Passage matrix

    Returns
    -------
    h_b2 : 1-electron integral given in basis B2
    g_b2 : 2-electron integral given in basis B2
    """
    h_b2 = np.einsum('pi,qj,pq->ij', C, C, h_b1)
    g_b2 = np.einsum('ap, bq, cr, ds, abcd -> pqrs', C, C, C, C, g_b1)

    return h_b2, g_b2


def householder_transformation(M):
    """
    Householder transformation transforming a squared matrix " M " into a
    block-diagonal matrix " M_BD " such that

                           M_BD = P M P

    where " P " represents the Householder transformation built from the
    vector "v" such that

                         P = Id - 2 * v.v^T

    NB : This returns a 2x2 block on left top corner

    Parameters
    ----------
    M :  Squared matrix to be transformed

    Returns
    -------
    P :  Transformation matrix
    v :  Householder vector

    """
    n = np.shape(M)[0]
    # Build the Householder vector "H_vector" 
    alpha = - np.sign(M[1, 0]) * sum(M[j, 0] ** 2. for j in range(1, n)) ** 0.5
    r = (0.5 * (alpha ** 2. - alpha * M[1, 0])) ** 0.5

    # print("HH param transformation",M,r,alpha)
    vector = np.zeros((n, 1))
    vector[1] = (M[1, 0] - alpha) / (2.0 * r)
    for j in range(2, n):
        vector[j] = M[j, 0] / (2.0 * r)

    # Building the transformation matrix "P" 
    P = np.eye(n) - 2 * vector @ vector.T

    return P, vector


def block_householder_transformation(M, block_size):
    """
    Block Householder transformation transforming a squared matrix ” M ” into a
    block-diagonal matrix ” M_BD ” such that
                           M_BD = P M P
    where ” P ” represents the Householder transformation built from the
    vector “v” such that
                         !!!!!!P = Id - 2 * v.v^T                                TO BE CHANGED !!!
    NB : This returns a 2x2 block on left top corner
    Parameters
    ----------
    M :  Squared matrix to be transformed
    block_size : Size of a block
    Returns
    -------
    P :  Transformation matrix
    v :  Householder vector
    """
    block_size = block_size // 2
    n = np.shape(M)[0]

    """ WILL BE WITH THE INVERSE SIGN OF x """
    a1 = M[:block_size, block_size:2 * block_size]
    a1_inv = np.linalg.inv(a1)
    a2 = M[:block_size, 2 * block_size:]
    a2_a1_inv_tr = np.zeros((block_size, n - 2 * block_size))
    for i in range(n - 2 * block_size):
        for j in range(block_size):
            for k in range(block_size):
                a2_a1_inv_tr[j, i] = a2_a1_inv_tr[j, i] + a2[k, i] * a1_inv[j, k]

    # A2A1_inv = np.transpose(a2_a1_inv_tr)
    a3 = np.eye(block_size) + a2_a1_inv_tr @ a2_a1_inv_tr.T
    w, v = np.linalg.eig(a3)
    eigval = np.diag(w)
    x_d = v.T @ eigval ** 0.5 @ v

    x = a1 @ x_d
    y = a1 + x
    v_tr = np.block([np.zeros((block_size, block_size)), y, M[:block_size, 2 * block_size:]])

    v_tr_v = v_tr @ v_tr.T
    v_tr_v_inv = np.linalg.inv(v_tr_v)
    bh = np.eye(n) - 2. * v_tr.T @ v_tr_v_inv @ v_tr

    return bh


# =============================================================================
#  MISCELLANEOUS
# =============================================================================

def build_mo_1rdm_and_2rdm(Psi_A, active_indices, n_mo, E_precomputed, e_precomputed):
    """
    >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    Function to build the MO 1/2-ELECTRON DENSITY MATRICES from a 
    reference wavefunction expressed in the computational basis
    >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
    """
    one_rdm_a = np.zeros((n_mo, n_mo))
    two_rdm_a = np.zeros((n_mo, n_mo, n_mo, n_mo))
    first_act_index = active_indices[0]
    # Creating RDMs elements only within the frozen space
    if first_act_index > 0:
        for i in range(first_act_index):
            for j in range(first_act_index):
                one_rdm_a[i, j] = 2. * delta(i, j)
                for k in range(first_act_index):
                    for l in range(first_act_index):
                        # State A
                        two_rdm_a[i, j, k, l] = 4. * delta(i, j) * delta(k, l) - 2. * delta(i, l) * delta(j, k)

                        # Creating RDMs elements in the the active/frozen spaces
    for p in active_indices:
        for q in active_indices:
            # Shifting the indices
            p_ = p - first_act_index
            q_ = q - first_act_index
            # 1-RDM elements only within the active space
            # State A
            one_rdm_a[p, q] = (np.conj(Psi_A.T) @ E_precomputed[p_, q_] @ Psi_A).real

            # 2-RDM elements only within the active space
            for r in active_indices:
                for s in active_indices:
                    # Shifting the indices
                    r_ = r - first_act_index
                    s_ = s - first_act_index
                    # State A
                    two_rdm_a[p, q, r, s] = (np.conj(Psi_A.T) @ e_precomputed[p_, q_, r_, s_] @ Psi_A).real

            if first_act_index > 0:
                # 2-RDM elements between the active and frozen spaces
                for i in range(first_act_index):
                    for j in range(first_act_index):
                        # State A
                        two_rdm_a[i, j, p, q] = two_rdm_a[p, q, i, j] = 2. * delta(i, j) * one_rdm_a[p, q]
                        two_rdm_a[p, i, j, q] = two_rdm_a[j, q, p, i] = - delta(i, j) * one_rdm_a[p, q]

    return one_rdm_a, two_rdm_a


def generate_h_chain_geometry(N_atoms, dist_HH):
    """
    A function to build a Hydrogen chain geometry (on the x-axis)

                   H - H - H - H

    N_atoms :: Total number of Hydrogen atoms
    dist_HH :: the interatomic distance
    """
    h_chain_geometry = 'H 0. 0. 0.'  # Define the position of the first atom
    for n in range(1, N_atoms):
        h_chain_geometry += '\nH {} 0. 0.'.format(n * dist_HH)

    return h_chain_geometry


def generate_h_ring_geometry(N_atoms, radius):
    """
    A function to build a Hydrogen ring geometry (in the x-y plane)
                         H - H
                        /     \\
                       H       H
                        \\     /
                         H - H
    N_atoms  :: Total number of Hydrogen atoms
    radius   :: Radius of the ring
    """
    theta_hh = 2 * m.pi / N_atoms  # Angle separating two consecutive H atoms (homogeneous distribution)
    theta_ini = 0.0
    h_ring_geometry = '\nH {:.16f} {:.16f} 0.'.format(radius * m.cos(theta_ini), radius * m.sin(
        theta_ini))  # 'H {:.16f} 0. 0.'.format( radius )  # Define the position of the first atom
    for n in range(1, N_atoms):
        angle_h = theta_ini + theta_hh * n
        h_ring_geometry += '\nH {:.16f} {:.16f} 0.'.format(radius * m.cos(angle_h), radius * m.sin(angle_h))

    return h_ring_geometry


def delta(index_1, index_2):
    """
    Function delta kronecker
    """
    d = 0.0
    if index_1 == index_2:
        d = 1.0
    return d

if __name__ == '__main__':
    nbody_basis = build_nbody_basis(2, 2)
    a_dagger_a = build_operator_a_dagger_a(nbody_basis)