# Superpowers to Amplifier: Analysis Summary

## Background

This document summarizes the analysis comparing [obra/superpowers](https://github.com/obra/superpowers) (a Claude Code skills library) with Amplifier's capabilities, and outlines the plan to port Superpowers' workflow disciplines to Amplifier.

## What is Superpowers?

Superpowers is a **workflow-oriented skills library** for Claude Code that enforces disciplined software development practices. It operates primarily through **markdown instruction files** that guide LLM behavior.

### Core Philosophy
- Test-Driven Development (TDD) as non-negotiable
- Systematic debugging over ad-hoc fixes
- Structured planning before implementation
- Evidence over claims - verify before declaring success

### Key Components

**14 Skills:**
1. `brainstorming` - Socratic design refinement
2. `writing-plans` - Detailed implementation plans with bite-sized tasks
3. `executing-plans` - Batch execution with human checkpoints
4. `subagent-driven-development` - Fresh subagent per task + two-stage review
5. `test-driven-development` - RED-GREEN-REFACTOR enforcement
6. `systematic-debugging` - 4-phase root cause analysis
7. `verification-before-completion` - Ensure fixes actually work
8. `using-git-worktrees` - Isolated workspaces per feature
9. `finishing-a-development-branch` - Merge/PR decision workflow
10. `requesting-code-review` - Pre-review checklist
11. `receiving-code-review` - Responding to feedback
12. `dispatching-parallel-agents` - Concurrent subagent workflows
13. `writing-skills` - Create new skills
14. `using-superpowers` - Introduction to the system

**1 Agent:** `code-reviewer`

**3 Commands:** `/brainstorm`, `/write-plan`, `/execute-plan`

## Key Insight: Skills vs Recipes

**Critical finding:** Many Superpowers "skills" are actually **multi-step workflows** with decision points and human checkpoints - exactly what Amplifier's recipe system is designed for.

### True Skills (Knowledge/Reference)
These should remain as **Amplifier skills**:
- `test-driven-development` - TDD philosophy and rules
- `systematic-debugging` - 4-phase debugging framework
- `writing-skills` - Meta-guide for creating skills

### Actually Recipes (Multi-Step Workflows)
These should become **Amplifier recipes**:

| Superpowers "Skill" | Why It's a Recipe |
|---------------------|-------------------|
| `brainstorming` | Flow: Questions → Approaches → Chunked design → Save → Handoff |
| `writing-plans` | Flow: Analyze → Create tasks → Save → Offer execution choice |
| `executing-plans` | Flow: Load → Review → Batch execute → **Human checkpoint** → Repeat |
| `subagent-driven-development` | Flow: Implementer → Spec review → Quality review → Loop → Next task |
| `using-git-worktrees` | Flow: Check dirs → Verify gitignore → Create → Setup → Verify baseline |
| `finishing-a-development-branch` | Flow: Verify tests → Present options → Execute → Cleanup |

## Comparison: Superpowers vs Amplifier

Both systems have significant strengths. Here's an honest comparison:

| Feature | Superpowers | Amplifier Recipes |
|---------|-------------|-------------------|
| **Resumability** | Yes - plan file tracks task status, re-run picks up where left off | Yes - formal checkpoint-based resume |
| **Two-Stage Review** | Yes - spec compliance + code quality, both with loops until approved | Ported from Superpowers |
| **Human Checkpoints** | Implicit ("say 'Ready'") | Formal approval gates |
| **Context Flow** | Manual passing via plan file | Automatic accumulation |
| **Validation** | LLM interprets markdown | Schema-checked YAML |
| **Provider Support** | Claude Code only | 7+ LLM providers |
| **Composability** | Implicit skill chaining | Explicit sub-recipes |

### What Superpowers Does Well (preserved in port)
- **Two-stage review loops** - Spec compliance review, then code quality review, both iterate until approved
- **Task-based resumability** - Plan file tracks in_progress/completed status
- **Fresh agent per task** - Prevents context pollution
- **TDD enforcement** - Strict RED-GREEN-REFACTOR discipline

### What Amplifier Adds
- **Multi-provider support** - Not locked to Claude
- **Formal approval gates** - Schema-enforced checkpoints
- **Recipe composition** - Sub-recipes and modular workflows

## Gap Analysis: What Amplifier Lacked (before this port)

### Gaps Addressed by This Port
1. **Enforced TDD Workflow** - Now in skills/test-driven-development
2. **Git Worktree Management** - Now in recipes/git-worktree-setup.yaml
3. **Two-Stage Code Review** - Now in recipes/subagent-development.yaml (spec + quality loops)
4. **Structured Planning Templates** - Now in recipes/writing-plans.yaml

### Already Strong in Amplifier
- Systematic debugging (`bug-hunter` agent)
- Parallel agent dispatch (`task` tool)
- Code review (`zen-architect` REVIEW mode)
- LSP code intelligence (not in Superpowers)
- Session management (not in Superpowers)

## Implementation Plan

### 1. Recipes to Build

```
superpowers/recipes/
├── brainstorming.yaml           # Design refinement workflow
├── writing-plans.yaml           # Plan creation with task granularity
├── executing-plans.yaml         # Batch execution with checkpoints
├── subagent-development.yaml    # Implementation with two-stage review
├── git-worktree-setup.yaml      # Isolated workspace creation
├── finish-branch.yaml           # Branch completion workflow
└── full-development-cycle.yaml  # Compose all above (meta-recipe)
```

### 2. Skills to Build

```
superpowers/skills/
├── test-driven-development/
│   └── SKILL.md                 # TDD philosophy and rules
├── systematic-debugging/
│   └── SKILL.md                 # 4-phase debugging framework
└── verification/
    └── SKILL.md                 # Verification before completion
```

### 3. Bundle Structure

```
superpowers/
├── bundle.md                    # Thin bundle (includes foundation)
├── behaviors/
│   └── superpowers.yaml         # Reusable behavior
├── agents/
│   └── superpowers-expert.md    # Agent that knows the system
├── context/
│   ├── philosophy.md            # Core principles
│   └── instructions.md          # How to use superpowers
├── recipes/                     # Workflow recipes
├── skills/                      # Domain knowledge
└── docs/
    └── ANALYSIS_SUMMARY.md      # This file
```

### 4. Bundle Composition Pattern

The bundle will use the **thin bundle pattern**:
- `bundle.md` includes foundation and the superpowers behavior
- Users load ONE bundle: `amplifier --bundle superpowers`
- Behavior is extractable for custom compositions

### 5. Superpowers Expert Agent

A specialized agent that:
- Knows all superpowers recipes and skills
- Can recommend which workflow to use
- Understands TDD enforcement
- Can be invoked when "superpowers" is mentioned

## Source Materials

- **Superpowers Repo:** https://github.com/obra/superpowers
- **Superpowers Blog Post:** https://blog.fsck.com/2025/10/09/superpowers/
- **Amplifier Foundation:** amplifier-foundation repo
- **Recipe System:** recipes bundle documentation

## Next Steps

1. ✅ Create directory structure
2. ✅ Write this summary
3. ⏳ Build recipes using recipe-author agent
4. ⏳ Build skills
5. ⏳ Create bundle with behavior
6. ⏳ Create superpowers-expert agent
7. ⏳ Test end-to-end workflow
