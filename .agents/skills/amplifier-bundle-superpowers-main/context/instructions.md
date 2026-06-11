# Superpowers Instructions

You have access to the Superpowers workflow system - a disciplined approach to software development.

## Available Recipes

Execute these workflows using the recipes tool:

| Recipe | Purpose | When to Use |
|--------|---------|-------------|
| `superpowers:recipes/brainstorming.yaml` | Refine ideas into designs | Starting a new feature |
| `superpowers:recipes/writing-plans.yaml` | Create detailed implementation plans | After design is approved |
| `superpowers:recipes/executing-plans.yaml` | Execute plans in batches | For batch execution with checkpoints |
| `superpowers:recipes/subagent-development.yaml` | Fresh agent per task + reviews | For same-session execution |
| `superpowers:recipes/git-worktree-setup.yaml` | Create isolated workspace | Before implementation |
| `superpowers:recipes/finish-branch.yaml` | Complete development branch | After implementation done |

## Available Skills

Load these for reference using the skills tool:

| Skill | Purpose |
|-------|---------|
| `superpowers:skills/test-driven-development/SKILL.md` | TDD methodology and rules |
| `superpowers:skills/systematic-debugging/SKILL.md` | 4-phase debugging framework |
| `superpowers:skills/verification-before-completion/SKILL.md` | Verification checklist |

## The Full Development Cycle

For a complete feature, the workflow is:

```
1. Brainstorming → Design document (approval gate)
2. Git Worktree → Isolated workspace
3. Writing Plans → Implementation plan (approval gate)
4. Executing Plans → Code with TDD (batch approval gates)
   OR Subagent Development → Fresh agent per task with reviews
5. Finish Branch → Merge/PR (approval gate)
```

## Quick Commands

**Start a new feature:**
```
Execute superpowers:recipes/brainstorming.yaml with topic="my feature idea"
```

**Create implementation plan:**
```
Execute superpowers:recipes/writing-plans.yaml with design_path="docs/plans/YYYY-MM-DD-feature-design.md"
```

**Set up workspace:**
```
Execute superpowers:recipes/git-worktree-setup.yaml with branch_name="feature/my-feature"
```

**Execute plan:**
```
Execute superpowers:recipes/executing-plans.yaml with plan_path="docs/plans/YYYY-MM-DD-feature-plan.md"
```

**Finish work:**
```
Execute superpowers:recipes/finish-branch.yaml
```

## Key Rules

1. **TDD Always** - No production code without failing test first
2. **Verify Everything** - Evidence over claims
3. **Systematic Debugging** - Root cause before fixes
4. **Human Checkpoints** - Approval gates at critical points
5. **Clean Isolation** - Worktrees for feature work

## When "Superpowers" is Mentioned

If the user mentions "superpowers" or asks about workflows:
- Explain available recipes and their purpose
- Recommend the appropriate recipe for their situation
- Help them execute the workflow

If the user is starting development work:
- Suggest starting with brainstorming recipe
- Emphasize TDD and systematic approach
- Offer to guide through the full workflow

## Philosophy Reference

For deep understanding of the principles, see:
- `superpowers:context/philosophy.md` - Core principles and anti-patterns
- `superpowers:docs/ANALYSIS_SUMMARY.md` - Full analysis and background
