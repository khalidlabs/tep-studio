# Adopting the Architecture for Another Process

This guide explains how to apply the architecture described in the paper to a
dynamic model of a process other than the Tennessee Eastman Process (TEP).

You do **not** need to replace a validated simulator, rewrite its equations in
Python, or use the TEP Studio software stack. Retain the existing simulator and
add three elements around it:

```text
Your existing simulator
        |
        v
A small connector that starts, advances, and reads the simulator
        |
        +---- One machine-readable process description
        |
        +---- Online/control interface
        +---- Dataset interface
        +---- Optimization interface
        `---- Agent interface

Validation evidence checks the complete path.
```

All interfaces must use the **same connector** and the **same process
description**. Separate copies of tags, units, limits, or process logic should
not be maintained.

In this guide, “machine-readable” means that reviewed process information is
stored in a structured file, usually JSON, so software can use it without
copying values from a document.

## Workflow overview

1. Choose a small pilot.
2. Describe the process in a spreadsheet.
3. Select an appropriate connection to the existing simulator.
4. Implement five standard operations through that connection.
5. Define the timing, action, termination, and randomness rules.
6. Add the interface required for the pilot.
7. Validate the description and behavior against independent evidence.
8. Publish the description, connector, example, and validation record together.

## Prerequisites

Before starting, you should have:

1. **A working dynamic model.** This may be an FMU, a Python or MATLAB model, a
   Simulink model, or a commercial simulator with an automation interface.
2. **Authoritative process information.** You need enough documentation to
   confirm what each variable means, what is measurable online, and which limits
   and events matter.
3. **Access to the simulator interface.** You must be able to start, advance,
   read, and write the model through its supported interface. The required
   technical work depends on whether that interface is FMI, Python,
   MATLAB/Simulink, or a vendor-supported API.
4. **One pilot use case.** Select one operating mode and one useful task,
   such as generating a training dataset or testing a controller.

TEP Studio is a reference implementation, not a no-code converter. A process
description can be prepared without programming. You must then implement the
connector through an interface supported by the selected simulator.

## Step 1: Choose a small pilot

Begin with a model boundary that can be tested clearly rather than an entire
plant—for example, a reactor and its existing control loops in one operating
mode.

Write a one-page pilot scope that answers:

- Which simulator and model version are authoritative?
- Which operating mode and initial condition will be supported first?
- Which manipulated variables may be requested externally?
- Which measurements are actually available online?
- Which shutdowns, constraints, or completion events end a run?
- Which interface is required first: dataset generation, online control,
  optimization, or agent access?

**Output of this step:** a bounded pilot that can be accepted or rejected using
known scenarios.

## Step 2: Describe the process in a spreadsheet

Complete the
[process-description worksheet](adoption-process-description-template.csv)
using the authoritative tags and definitions for the model. Replace the example
rows with the variables from your process.

Record at least the following:

| What to describe | Questions to answer |
| --- | --- |
| Measurements and states | What is the name, source tag, unit, and physical meaning? Is it available online? Is it continuous, sampled, delayed, or held between samples? |
| Manipulated variables | What can be requested? What range is allowed? Is the reported implemented value a command, setpoint, or actual actuator position? Who has authority in open and closed loop? |
| Disturbances | What changes physically? What range and timing are allowed? Is the physical root cause known or intentionally marked unknown? |
| Events and constraints | What causes shutdown, infeasibility, or task completion? What is merely the end of the requested simulation horizon? |
| Objectives | Which physical or economic quantities should be accumulated, and in what units? |
| Reproducibility | Which model version, solver settings, time unit, initial condition, and random-seed rules identify a run? |

Use stable, readable names. Keep the simulator's original tag or index alongside
each name so the description can be checked against an independent source.
Unknown information should be left unset or marked unknown; it should not be
guessed.

**Output of this step:** one reviewed register of process meaning, converted to
JSON or another structured format that software can read.

## Step 3: Choose how to connect the existing simulator

Use the least invasive supported connection:

| Your current model | Practical starting point |
| --- | --- |
| FMI/FMU | Import the standard variable information and execution calls, then add process-specific fields such as online availability, analyzer delay, action authority, shutdown meaning, and what the random seed controls. |
| Python model | Add a thin wrapper around the existing model functions. Keep the equations in their current module. |
| MATLAB or Simulink | Use the supported engine/API or export an FMU, then wrap the resulting start, step, read, and write operations. |
| Commercial or proprietary simulator | Use a vendor-supported connection, such as an FMU, COM, REST, or OPC interface. Do not duplicate the process equations. |
| Equations only | Implement and validate a numerical model first. This is a larger modeling project, not merely an interface task. |

The connector must translate between the simulator's native tags or arrays and
the names in the process-description worksheet. It must not redefine the
process equations.

**Output of this step:** a documented connection method and an implementation
plan for the connector.

## Step 4: Implement one small simulator contract

Expose five operations through the connector:

| Operation | Purpose |
| --- | --- |
| `reset` | Start a new run from a declared operating mode or initial condition. |
| `advance` | Apply requested inputs and disturbances for one declared interval, advance the model, and return the result. |
| `snapshot` | Save everything required to reproduce the current simulator state. |
| `restore` | Return exactly to a saved state. |
| `validate` | Check the process description against the connected model and report any mismatch. |

Each `advance` result should report:

- interval start, interval end, and interval length;
- requested inputs and the inputs actually passed to the model;
- active disturbances;
- measurements and, where permitted, internal states;
- events, constraint margins, and whether the process terminated;
- solver diagnostics and objective terms used by later interfaces.

This is the only layer that should directly operate the simulator.

**Output of this step:** one successful reset-and-advance example whose results
have clear names and units.

## Step 5: Define four behavior rules

Before building interfaces, define four rules:

1. **Time and availability.** A value is exposed only when it would be available
   in operation. Sampled analyzers retain their sampling, delay, and hold
   behavior.
2. **Requested versus implemented action.** Store what the user requested and
   what the simulator implemented after saturation, rate limits, controllers, or
   overrides. State whether the implemented value is a command or a measured
   actuator position.
3. **Process termination versus experiment end.** A plant shutdown is not the
   same as reaching a requested simulation horizon. Record them separately.
4. **Randomness.** State what the seed controls, whether random mechanisms share
   a stream, and which settings are required for replay.

Put these decisions in the process description. Do not leave them only in a user
manual.

**Output of this step:** a documented interaction contract with no ambiguous
time, action, termination, or random-seed conventions.

## Step 6: Add the required interfaces

Build each interface as a view over the same description and `advance` result:

| Need | Interface to add | What it reuses |
| --- | --- | --- |
| Run the model interactively or from a controller | Online/control interface | Published measurements, permitted actions, limits, events, and time semantics |
| Generate data for ML, monitoring, or system identification | Dataset interface | The same transitions, written as named interval records with units and a record of how the run was produced |
| Evaluate candidate decisions over a horizon | Optimization interface | Snapshot/restore, constraints, objective terms, and deterministic rollout settings |
| Let an AI assistant discover and run the model | Agent interface | The same names, descriptions, allowed ranges, scenario fields, and validation rules |

Start with the core and the interface selected in Step 1. Add other interfaces
only when they are required. The architecture does not require separate
simulator implementations for each interface.

**Output of this step:** the pilot task working through a generated interface,
without a second variable catalog or second copy of the equations.

## Step 7: Validate the implementation

Use independent evidence wherever possible. At minimum, perform these checks:

| Check | Passing result |
| --- | --- |
| Description-to-model audit | Names, source tags, indices, units, bounds, and online availability agree with the authoritative model documentation or interface. |
| Base case | The reset state and reported outputs match a trusted reference within declared tolerances. |
| Dynamic scenario | At least one known input or disturbance produces the expected transient behavior. |
| Action handling | Out-of-range requests, saturation, controller authority, and requested/implemented values behave as documented. |
| Timing and events | Sampled measurements, delays, shutdowns, and horizon endings are reported correctly. |
| Replay | A saved configuration, model version, description hash, solver settings, and seed reproduce the recorded result within tolerance. |
| Cross-interface agreement | Online, dataset, optimization, and agent views use the same names, units, bounds, and termination semantics for every interface that has been implemented. |

A dimension check alone is not sufficient. A wrong unit or description can have
the correct array length and still propagate to every interface.

**Output of this step:** a validation report that states what was tested, the
tolerances, the results, and what remains unvalidated.

## Step 8: Publish a small adoption package

Publish these six items:

1. `process_description.json` — the reviewed process register and interaction
   rules, with a content hash.
2. The connector — code, service, FMU adapter, or vendor integration that exposes
   the five core operations.
3. `example_run.csv` — one named trajectory that users can inspect without
   special software.
4. `run_manifest.json` — model version, description hash, scenario, solver,
   initial condition, seed, and software versions for that run.
5. `validation_report` — reference cases, tolerances, results, and limitations.
6. A short README — how to install or connect, run the example, and interpret the
   result.

For an initial deployment, portable files are sufficient. An external database,
message broker, or cloud platform is optional and should be introduced only when
required by the operating environment.

## Completion criteria

The pilot is complete when another user can:

- read one description and understand the supported variables and rules;
- start and advance the trusted simulator through one connector;
- reproduce the example run from its manifest;
- confirm the validation evidence and its limits; and
- use every implemented interface without learning a different set of names,
  units, bounds, or end-of-run semantics.

## TEP Studio as a worked reference

TEP Studio demonstrates the completed pattern; it is not a required technology
stack for another process.

| Generic adoption artifact | TEP Studio example |
| --- | --- |
| Process description | `TEP_SCHEMA` and `tep describe` |
| Connector and core contract | `TennesseeEastmanProcess.reset/advance/snapshot/restore/validate` |
| Online interface | Gymnasium and the closed-loop scenario runner |
| Dataset interface | `TrajectoryDataset`, `tep run`, and `tep dataset` |
| Optimization interface | `OptimizationAdapter` |
| Agent interface | Six MCP tools served by `tep-mcp` |
| Validation evidence | Schema-conformance tests and generated validation artifacts |

The reference implementation can be installed and its complete description
exported with:

```bash
python3 -m pip install -e .
tep describe --out process_description.json
python3 -m pytest -q src/tep_studio/simulation/tests/test_schema_metadata.py
```

The exported JSON includes the canonical description, its SHA-256 content hash,
and generated checks. The [agent guide](agent.md) and [cookbook](cookbook.md)
provide TEP-specific examples after the process-independent adoption decisions
above have been understood.
