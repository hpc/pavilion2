# Pavilion

## What is Pavilion?

Pavilion is a framework for orchestrating the activities involved testing High Performance
Computing (HPC) systems by collecting and structuring those activities into workflows that span the
lifecycles of HPC tests.

| Form of complexity | Example                                                                           | Why it matters                                                                                                 |
| ------------------ | --------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| **Scale**          | Thousands of nodes, tests, or configurations                                      | Engineering practices that work at small scales become impractical, requiring new abstractions and automation. |
| **Heterogeneity**  | Different hardware, software stacks, schedulers, or network architectures         | Tests must remain reliable, correct, and valid across diverse execution environments.                          |
| **Variation**      | Software updates, compiler options, module configurations, and runtime parameters | Tests must continue to produce meaningful results as environments evolve over time and across contexts.        |
| **Distribution**   | Multi-node jobs, distributed applications, and coordinated workflows              | Testing activities must be orchestrated across multiple systems and processes.                                 |

## What does Pavilion do?

Testing HPC systems requires accounting for the complexity that emerges at scale, particularly
across heterogeneous environments. Pavilion accounts for this complexity in four ways:

| Pavilion...      |                          | So that...                                                                |
| ---------------- | ------------------------ | ------------------------------------------------------------------------- |
| **automates**    | repetitive testing tasks | testing tasks become repeatable                                           |
| **generalizes**  | tests                    | tests remain reliable, correct, and valid across environmental boundaries |
| **preserves**    | testing artifacts        | testing workflows become inspectable and verifiable                       |
| **orchestrates** | testing activities       | testing activities form coherent, reusable workflows                      |

Pavilion replaces ad hoc testing practices with systematic workflows that make testing HPC systems
reproducible and tractable.

### Generalization

Generalization preserves three distinct properties of a test. A generalized test must continue to
execute reliably, conform to its specification, and preserve the meaning of its results. These
correspond to reliability, correctness, and validity, respectively. Together, they ensure that a
generalized test continues to justify the same conclusions across the systems to which it is
applied.

| Invariant | Question | Meaning |
| --- | --- | --- |
| **Reliability** | Does the test execute successfully? | The test executes without bugs, runtime errors, or crashes. |
| **Correctness** | Does the test perform the specified procedure? | The implementation carries out the prescribed operations and produces the specified outputs. |
| **Validity** | Does the test have the intended meaning? | The test measures or verifies the intended phenomenon, its outcomes admit the intended interpretation, and those outcomes permit valid inferences. |

The generalized test continues to execute successfully across the systems to which it is applied
without encountering system-specific runtime errors, crashes, or other implementation failures.

Generalization preserves the conditions necessary for valid inference. Whether those inferences are sound depends on assumptions and facts external to the testing framework.

## Why Pavilion?

- Reduce the cost of maintaining tests across heterogeneous HPC systems.
- Make testing workflows reproducible and inspectable.
- Replace ad hoc scripts with reusable testing workflows.
- Scale testing practices from individual tests to coordinated campaigns.
- Pavilion makes the state and history of a testing workflow observable.

## Project Goals:

- End-to-end status tracking
- Simple, powerful test configuration language.
- System-agnostic test configs.
- Hide common platform and environment idiosyncrasies from tests.
- System specific defaults.
- Eliminate unnecessary build repetition.
- Extreme extensibility (plugins everywhere). 

## Where can I learn more?

The [Pavilion documentation](https://pavilion2.readthedocs.io/en/latest/) includes both user
documentation and API documentation.

## How can I contribute?

See [CONTRIBUTING.md](CONTRIBUTING.md) for contributor guidelines.
