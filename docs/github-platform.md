# GitHub Platform Usage

This document defines the durable policy for how repositories under `luceat-lux-vestra` use GitHub platform capabilities.

The execution tracker for the current rollout is [GitHub platform capabilities audit and adoption](../issues/5).

## Source-of-truth model

### Engineering Portfolio

The permanent GitHub Project for cross-repository engineering management.

It owns the current operational view of:
- repositories/products
- status and priority
- current production PR
- release target
- campaign or milestone
- blockers
- target dates
- maintenance state

This project is long-lived.

### GitHub Platform Adoption

A temporary rollout GitHub Project used to:
- inventory current capability usage
- make Adopt / Skip / Later decisions
- track repository-specific rollout work
- validate actual usage after enablement

When the rollout is complete, archive/freeze this project rather than deleting it so that the decision history remains available.

## Capability responsibilities

### GitHub Projects

Use Projects for cross-repository planning and state tracking.

Projects are not a replacement for Issues or PRs. They provide the portfolio/initiative view over executable work.

### Issues and pull requests

Use Issues for actionable engineering work and PRs for proposed repository changes.

Repository-specific capability rollout must follow the same fail-closed development and merge policy as any other production change.

### Milestones

Use milestones for bounded delivery goals such as a release or other concrete outcome.

Examples:
- MarkFlow 1.0.0
- zMyBatis 1.0.0
- oxide-batch 1.0 milestone

Do not use milestones as a substitute for the permanent portfolio view.

### Releases

Public repositories that ship user-consumable artifacts should use GitHub Releases as the canonical human-facing release record when practical.

A release may include:
- release notes
- compatibility/breaking-change notes
- related issues and PRs
- binaries or other assets
- links to external distribution channels

### Issue Forms and hierarchy

Use Issue Forms/templates where structured intake materially improves triage.

Use parent/sub-issue relationships for work breakdown when a large actionable item has independently completable children.

Do not create repository issues merely to record an Adopt / Skip decision when no repository work is required; record such decisions in the adoption initiative.

### Discussions

Use Discussions for non-actionable community interaction:
- Q&A
- ideas
- RFC-style exploration
- announcements
- user feedback

When a discussion becomes accepted executable engineering work, create or promote it to an Issue.

### Wiki versus /docs

Use repository `/docs` for documentation that should evolve in lockstep with code, including:
- architecture
- API behavior
- invariants
- ADRs
- contributor/development documentation
- version-sensitive operational behavior

Use Wiki only for long-lived knowledge that benefits from independent editing and does not need code-version lockstep, such as:
- user how-to material
- FAQ
- troubleshooting knowledge
- broad conceptual guidance

Do not enable Wiki by default.

### GitHub Pages

Use Pages where a project benefits from a public documentation or product site.

Do not enable Pages merely because a repository is public.

### Packages / GHCR

Use GitHub Packages or GHCR when a project has packages or container artifacts whose distribution or CI reuse benefits from GitHub-hosted registries.

### Codespaces / devcontainer

Adopt only when reproducible contributor onboarding or cloud development materially benefits the project.

### Repository Insights

Use Insights as an observation tool for public adoption, traffic, contributors, and repository activity. Do not treat traffic metrics as product-quality evidence.

### Dependency Graph and SBOM

Enable and use dependency graph capabilities where supported.

Adopt SBOM generation/export for repositories where release, supply-chain, or enterprise-consumption requirements justify it.

### Secret scanning and push protection

For eligible public production repositories, prefer proactive secret prevention rather than detection after merge.

Verify repository eligibility and configuration during the adoption audit.

### Vulnerability reporting and security advisories

For public libraries/tools with external users, evaluate:
- private vulnerability reporting
- repository security advisories
- coordinated disclosure/CVE workflow

Enable only after a clear response/ownership flow exists.

### CODEOWNERS

Use when repository ownership is shared enough for path-based review routing or policy enforcement to provide value.

Single-maintainer repositories do not need CODEOWNERS solely for formality.

### Custom Properties

Use structured repository metadata when it enables useful portfolio filtering or policy application.

Candidate properties:
- project-stage
- security-tier
- release-channel
- primary-language
- maintenance-state

The exact schema must be kept small and should exist only where it drives an actual workflow or ruleset.

### Rulesets

Prefer reusable, consistent repository policy.

Where possible, apply rulesets based on meaningful repository classification rather than copy-pasting policy without a governing model.

### Topics and social preview

Public repositories should use accurate topics and a useful social preview when discoverability matters.

### CITATION.cff

Use for research-oriented repositories or software where formal citation is useful.

### Sponsors

Enable only when the project has a real open-source funding model and the maintainer intends to support it.

## Rollout order

### Wave 1 — operating model
1. GitHub Platform Adoption project
2. Engineering Portfolio project
3. Project field/status model
4. Milestone policy
5. Issue hierarchy/forms policy
6. Release policy

### Wave 2 — public project UX
1. Discussions
2. Pages
3. Wiki versus `/docs`
4. repository metadata/topics/social preview

### Wave 3 — governance and supply chain
1. Custom Properties
2. reusable rulesets
3. SBOM
4. secret scanning/push protection
5. vulnerability reporting/advisories

### Wave 4 — selective capabilities
1. Packages/GHCR
2. Codespaces
3. CODEOWNERS
4. CITATION.cff
5. Sponsors

## Decision standard

A capability is adopted only when all of the following are clear:
- purpose
- owner
- expected usage flow
- repository scope
- validation method

Otherwise classify it as `Skip` or `Later` rather than enabling it speculatively.

## Completion of the rollout initiative

The rollout is complete when:
- current capability usage has been inventoried
- portfolio-wide policy is documented
- both GitHub Projects are created and configured
- repository-specific Adopt / Skip / Later decisions are recorded
- selected capabilities are rolled out and validated
- the permanent Engineering Portfolio is actively used
- the temporary GitHub Platform Adoption project is frozen/archived with its history intact
