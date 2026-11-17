# ENERGY_MANAGER

- **Department:** `it_infrastructure`
- **Status (static inventory):** `real`
- **Source:** `departments/it_infrastructure/ENERGY_MANAGER/main.py` (72 lines)

## Purpose

ENERGY_MANAGER: decide how hard to work given the machine's power source.

advise() reads the battery and mains state (psutil) and picks a profile:

    on mains, or no battery present            performance
    on battery, charge >  low_battery          balanced
    on battery, charge <= low_battery          saver

should_run() applies it: "heavy" jobs wait unless the profile is performance,
"normal" jobs wait only in saver, "critical" jobs always run. estimate_energy()
is plain arithmetic over figures the caller supplies.

It advises; it never changes a power setting, a governor or another process.

## Class `ENERGY_MANAGERAgent`

- `__init__(name)`
- `health_check()`
- `set_low_battery(percent)`
- `advise(sample)`
- `should_run(job_class, sample)`
- `estimate_energy(cpu_seconds, watts_per_core)` — Energy for `cpu_seconds` of one core at `watts_per_core`: Wh = seconds * watts / 3600.

## Depends on

- `velaris.agentkit`
- `velaris.agentkit.checks`
- `velaris.agentkit.results`
- `velaris.agentkit.state`

## State and configuration

- keeps no files of its own

## Called by

- **other agents:** none found
- **platform modules:** none found
- **tests:** `velaris/tests/test_dept_it_infrastructure_stubs_2.py`, `velaris/tests/test_layer8_gro.py`
