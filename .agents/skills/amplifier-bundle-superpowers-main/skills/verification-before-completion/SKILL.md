# Verification Before Completion

## Overview

Never declare victory without evidence. "It should work" is not verification.

**Core principle:** Verify it's actually fixed before claiming success.

## The Iron Law

```
NO CLAIMING SUCCESS WITHOUT VERIFICATION
```

If you can't demonstrate the fix works, you haven't fixed it.

## Verification Checklist

Before marking ANY task complete:

### 1. Tests Pass

```bash
# Run the specific tests for your changes
pytest tests/path/to/test.py -v

# Run the full test suite
pytest

# Verify no new warnings or errors in output
```

- [ ] All relevant tests pass
- [ ] No new test failures introduced
- [ ] Output is clean (no warnings, deprecations)

### 2. Manual Verification

If the fix is user-visible:

- [ ] Actually try the feature/fix
- [ ] Test the exact scenario that was broken
- [ ] Test edge cases related to the fix
- [ ] Verify in the actual environment (not just tests)

### 3. Code Review Self-Check

- [ ] Changes are minimal and focused
- [ ] No unrelated modifications
- [ ] Code follows project conventions
- [ ] No debug code left behind

### 4. Integration Verification

For changes that affect multiple components:

- [ ] Verify each component still works
- [ ] Test the integration points
- [ ] Check for cascading effects

## Verification Anti-Patterns

**DON'T:**
- Declare "should work now" without running tests
- Skip manual verification for "simple" changes
- Assume passing tests = complete verification
- Mark complete before all checks pass

**DO:**
- Run tests after every change
- Manually verify user-visible changes
- Check for side effects
- Document verification steps taken

## When to Stop and Re-Investigate

If during verification you discover:
- New test failures
- Unexpected behavior
- Partial fix (some cases work, others don't)

**STOP.** Return to the debugging process. Don't patch on top of patches.

## Verification Report Template

When completing a task, provide:

```markdown
## Verification

**Tests:**
- Ran: `pytest tests/specific_test.py` - PASS
- Ran: `pytest` (full suite) - PASS (X tests, 0 failures)

**Manual Check:**
- Tested: [specific scenario]
- Result: [what happened]

**Side Effects:**
- Checked: [related functionality]
- Status: [working/not affected]
```

## Real Examples

### Good Verification
```
Fixed the login timeout issue.

Verification:
- pytest tests/auth/test_login.py - All 12 tests pass
- pytest (full suite) - 847 tests pass, 0 failures
- Manual test: Login with slow network simulation - succeeds
- Manual test: Login with invalid credentials - proper error shown
- Checked: Session management still works correctly
```

### Bad Verification
```
Fixed the login timeout issue. Should work now.
```

## Final Rule

```
Verified = demonstrated working with evidence
Otherwise = not verified, not complete
```

If you can't show the evidence, you haven't finished the task.
