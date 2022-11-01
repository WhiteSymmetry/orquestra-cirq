################################################################################
# © Copyright 2021-2022 Zapata Computing Inc.
################################################################################

import sys
from typing import List, Optional, Sequence, cast

import cirq
import numpy as np
from orquestra.quantum.api.wavefunction_simulator import BaseWavefunctionSimulator
from orquestra.quantum.circuits import Circuit, I
from orquestra.quantum.measurements import ExpectationValues, expectation_values_to_real
from orquestra.quantum.operators import PauliRepresentation, get_sparse_operator
from orquestra.quantum.typing import StateVector

from ..conversions import export_to_cirq


class CirqBasedSimulator(BaseWavefunctionSimulator):

    supports_batching = True
    batch_size = sys.maxsize

    def __init__(
        self,
        simulator,
        noise_model: cirq.NOISE_MODEL_LIKE = None,
        param_resolver: cirq.ParamResolverOrSimilarType = None,
        qubit_order=cirq.ops.QubitOrder.DEFAULT,
    ):
        """initializes the parameters for the system or simulator

        Args:
            simulator: qsim or cirq simulator that is defined by the user
            noise_model: optional argument to define the noise model
            param_resolver: Optional arg that defines the parameters
            to run with the program.
            qubit_order: Optional arg that defines the ordering of qubits.
        """
        super().__init__()
        self.noise_model = noise_model
        self.simulator = simulator
        self.param_resolver = param_resolver
        self.qubit_order = qubit_order

    def get_exact_noisy_expectation_values(
        self, circuit: Circuit, qubit_operator: PauliRepresentation
    ) -> ExpectationValues:
        """Compute exact expectation values w.r.t. given operator in presence of noise.

        Note that this method can be used only if simulator's noise_model is not set
        to None.

        Args:
            circuit: the circuit to prepare the state
            qubit_operator: the operator to measure
        Returns:
            the expectation values of each term in the operator
        Raises:
            RuntimeError if this simulator's noise_model is None.
        """
        if self.noise_model is None:
            raise RuntimeError(
                "Please provide noise model to get exact noisy expectation values"
            )

        cirq_circuit = cast(cirq.Circuit, export_to_cirq(circuit))
        values = []

        for pauli_term in qubit_operator.terms:
            sparse_pauli_term_ndarray = get_sparse_operator(
                pauli_term, n_qubits=circuit.n_qubits
            ).toarray()
            if np.size(sparse_pauli_term_ndarray) == 1:
                expectation_value = sparse_pauli_term_ndarray[0][0]
                values.append(expectation_value)

            else:

                noisy_circuit = cirq_circuit.with_noise(self.noise_model)
                rho = self._extract_density_matrix(
                    self.simulator.simulate(noisy_circuit)
                )
                expectation_value = np.real(np.trace(rho @ sparse_pauli_term_ndarray))
                values.append(expectation_value)
        return expectation_values_to_real(ExpectationValues(np.asarray(values)))

    def _get_wavefunction_from_native_circuit(
        self, circuit: Circuit, initial_state: StateVector
    ) -> StateVector:
        # Cirq does not allow inactive qubits so we added identity to our circuits.
        for i in range(circuit.n_qubits):
            circuit += I(i)

        cirq_circuit = cast(cirq.Circuit, export_to_cirq(circuit))

        initial_state = np.array(initial_state, np.complex64)

        simulated_result = self.simulator.simulate(
            cirq_circuit,
            param_resolver=self.param_resolver,
            qubit_order=self.qubit_order,
            initial_state=initial_state,
        )

        return simulated_result.final_state_vector

    def _extract_density_matrix(self, result):
        return result.density_matrix_of()
