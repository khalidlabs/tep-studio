# Adopt the Architecture for Your Own Process

This guide is for a process owner who has a dynamic model of a process other
than the Tennessee Eastman Process (TEP) and wants to apply the architecture in
the paper.

You do **not** need to replace your simulator, rewrite its equations in Python,
or use the same software as TEP Studio. You keep the simulator you already trust
and add three things around it:

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

The important rule is that all interfaces use the **same connector** and the
**same process description**. They should not maintain separate copies of tags,
units, limits, or process logic.

Here, “machine-readable” simply means that the reviewed information is also
saved in a structured file, usually JSON, so software can use it without copying
values from a document.

## The whole job at a glance

1. Choose a small pilot.
2. Describe the process in a spreadsheet.
3. Select the safest way to connect the existing simulator.
4. Give that connection five standard operations.
5. Agree on timing, action, ending, and randomness rules.
6. Add the user interface needed for the pilot.
7. Validate the description and behavior against independent evidence.
8. Publish the description, connector, example, and validation record together.

## What you need before starting

Bring together:

1. **A working dynamic model.** This may be an FMU, a Python or MATLAB model, a
   Simulink model, or a commercial simulator with an automation interface.
2. **A process expert.** This person confirms what each variable means, what is
   measurable online, and which limits and events matter.
3. **An implementation partner.** A software engineer, model developer, or
   simulator vendor connects the model to the small interface described below.
4. **One pilot use case.** Start with one operating mode and one useful task,
   such as generating a training dataset or testing a controller.

TEP Studio is a reference implementation, not a no-code converter. A process
expert can complete the description and acceptance decisions without
programming, but someone must implement the connector to the chosen simulator.

## Step 1: Choose a small pilot

Do not begin with an entire plant. Select one model boundary that can be tested
clearly—for example, a reactor and its existing control loops in one operating
mode.

Write a one-page pilot scope that answers:

- Which simulator and model version are authoritative?
- Which operating mode and initial condition will be supported first?
- Which manipulated variables can an external user request?
- Which measurements are actually available online?
- Which shutdowns, constraints, or completion events end a run?
- What first interface is useful: a dataset, online control, optimization, or an
  agent?

**Output of this step:** a bounded pilot that can be accepted or rejected using
known scenarios.

## Step 2: Describe the process in a spreadsheet

Complete the [process-description worksheet](adoption-process-description-template.csv)
with the process expert. The example rows can be replaced with the tags from your
model.

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

**Output of this step:** one reviewed register of process meaning. The technical
team will later convert this worksheet to JSON or another structured file that
software can read.

## Step 3: Choose how to connect the existing simulator

Use the least invasive connection available:

| Your current model | Practical starting point |
| --- | --- |
| FMI/FMU | Import the standard variable information and execution calls, then add process-specific fields such as online availability, analyzer delay, action authority, shutdown meaning, and what the random seed controls. |
| Python model | Add a thin wrapper around the existing model functions. Keep the equations in their current module. |
| MATLAB or Simulink | Use the supported engine/API or export an FMU, then wrap the resulting start, step, read, and write operations. |
| Commercial or proprietary simulator | Use a vendor-supported connection, such as an FMU, COM, REST, or OPC interface. Do not duplicate the process equations. |
| Equations only | Implement and validate a numerical model first. This is a larger modeling project, not merely an interface task. |

The connector should translate between your simulator's native tags or arrays and
the names in the process-description worksheet. It should not redefine the
physics.

**Output of this step:** a documented connection method and a named owner for its
implementation.

## Step 4: Implement one small simulator contract

Ask the implementation partner to expose five operations:

| Operation | Meaning in plain language |
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

## Step 5: Agree on four behavior rules

Before building user interfaces, the process owner and implementer must agree on
four rules:

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

**Output of this step:** an approved interaction contract with no ambiguous time,
action, ending, or random-seed conventions.

## Step 6: Add the interfaces you actually need

Build each interface as a view over the same description and `advance` result:

| Need | Interface to add | What it reuses |
| --- | --- | --- |
| Run the model interactively or from a controller | Online/control interface | Published measurements, allowed actions, limits, events, and time semantics |
| Generate data for ML, monitoring, or system identification | Dataset interface | The same transitions, written as named interval records with units and a record of how the run was produced |
| Evaluate candidate decisions over a horizon | Optimization interface | Snapshot/restore, constraints, objective terms, and deterministic rollout settings |
| Let an AI assistant discover and run the model | Agent interface | The same names, descriptions, allowed ranges, scenario fields, and validation rules |

Start with the core plus the one interface selected in Step 1. Add the others only
when there is a real use case. The architecture does not require four separate
simulator implementations.

**Output of this step:** the pilot task working through a generated interface,
without a second variable catalog or second copy of the equations.

## Step 7: Validate before calling it self-describing

Use independent evidence wherever possible. At minimum, require these checks:

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

Give future users these six items:

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

For an initial deployment, portable files are enough. An external database,
message broker, or cloud platform is optional and should be introduced only when
the operating environment requires it.

## What “done” looks like

Your pilot is complete when a new user can:

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

Developers evaluating the reference implementation can install it and export its
complete description with:

```bash
python3 -m pip install -e .
tep describe --out process_description.json
python3 -m pytest -q src/tep_studio/simulation/tests/test_schema_metadata.py
```

The exported JSON includes the canonical description, its SHA-256 content hash,
and generated checks. The [agent guide](agent.md) and [cookbook](cookbook.md)
provide TEP-specific examples after the process-independent adoption decisions
above have been understood.
