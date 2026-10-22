# Component Guide Template

Copy this structure for every component guide. Sections are required; a section marked N/A must say why.

---

# <Component>

Status: DRAFT | REVIEWED | ACCEPTED
Owner: <team>
Last reviewed: <YYYY-MM-DD>
Applies to version: <pinned version>
Source of truth: <official documentation URL + check date>

## A. Purpose and architecture

- **Purpose**: what problem it solves here.
- **Architecture**: how it is arranged (diagram if useful).
- **Dependencies**: what it needs, and what it must not depend on.
- **Deployment location**: which role/cluster it runs in.
- **Recommended production model**: the configuration used in production.
- **Alternatives and decision criteria**: what else was considered and when the alternative would win. Link the ADR.

## B. Requirements and compatibility

| Item | Requirement |
|---|---|
| OS | |
| Version | |
| CPU | |
| RAM | |
| Storage | |
| Network | |
| Dependencies | |
| Licensing | |
| Compatibility constraints | |

Compatibility table with the check date and the source URL. Anything not verified is marked UNVERIFIED with the verification procedure.

## C. Offline preparation

- **Official sources**: URLs.
- **Packages**: names and versions.
- **Images**: full image paths and tags.
- **Charts**: chart and version.
- **Plugins**: names and versions.
- **Transitive dependencies**: the full closure.
- **Internal repository mapping**: source -> internal path.
- **Integrity verification**: the exact command.
- **Required client configuration**: the files that change.

## D. Installation

- **Prerequisites**.
- **Execution context**: which host/cluster the commands run on.
- **Privileges**: required capabilities.
- **Ordered commands**: numbered, runnable.
- **File paths**: every file that is written.
- **Configuration examples**: the actual YAML/values, with a sanitized example.
- **Parameter explanations**: what each key does.
- **Environment-specific values**: which values change per environment.

## E. Integration

| Dimension | How |
|---|---|
| Identity | |
| TLS | |
| Secrets | |
| Network | |
| Storage | |
| Monitoring | |
| Logging | |
| Security | |
| Automation | |
| GitOps | |

State explicitly who owns this component's configuration and who must not write to it.

## F. Validation

- **Health checks**: the commands and the expected output.
- **Expected outputs**: literal examples.
- **Functional tests**.
- **Failure tests**: what happens when a dependency is down.
- **Performance tests**: the benchmark and the numbers to beat.
- **Automated validation**: the script and where it runs.

## G. Operations

- **Maintenance**: the routine tasks and their frequency.
- **Scaling**: how to grow it.
- **Troubleshooting**: link to the runbook.
- **Backup**: what is backed up and how.
- **Restore**: the tested procedure.
- **Upgrades**: link to the upgrade runbook.
- **Rollback**: what can be rolled back and what cannot.
- **Disaster recovery**: the scenario and the procedure.

## H. Best practices

### Mandatory production controls

Each with a rationale and the operational impact.

### Strongly recommended

Each with a rationale and the operational impact.

### Optional or workload-dependent

Each with the condition under which it applies.

---

## Version record

| Date | Version | Change | Author |
|---|---|---|---|
