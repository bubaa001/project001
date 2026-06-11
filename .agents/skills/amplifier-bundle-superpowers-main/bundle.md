---
bundle:
  name: superpowers
  version: 1.0.0
  description: Superpowers workflow system - disciplined software development with TDD, systematic debugging, and structured planning

includes:
  # Include foundation for core tools and agents
  - bundle: git+https://github.com/microsoft/amplifier-foundation@main
  # Include recipes bundle for workflow execution
  - bundle: git+https://github.com/microsoft/amplifier-recipes@main
  # Include our own behavior
  - bundle: git+https://github.com/ramparte/superpowers@main#subdirectory=behaviors/superpowers.yaml
---

# Superpowers Bundle

A disciplined approach to software development that enforces TDD, systematic debugging, structured planning, and human checkpoints at critical points.

## Philosophy

@superpowers:context/philosophy.md

---

## Instructions

@superpowers:context/instructions.md

---

## Foundation Integration

@foundation:context/shared/common-system-base.md
