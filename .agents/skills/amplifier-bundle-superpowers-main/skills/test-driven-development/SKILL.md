# Test-Driven Development (TDD)

## Overview

Write the test first. Watch it fail. Write minimal code to pass.

**Core principle:** If you didn't watch the test fail, you don't know if it tests the right thing.

**Violating the letter of the rules is violating the spirit of the rules.**

## The Iron Law

```
NO PRODUCTION CODE WITHOUT A FAILING TEST FIRST
```

Write code before the test? **Delete it. Start over.**

- Don't keep it as "reference"
- Don't "adapt" it while writing tests
- Don't look at it
- Delete means delete

Implement fresh from tests. Period.

## When to Use

**Always:**
- New features
- Bug fixes
- Refactoring
- Behavior changes

**Exceptions (ask your human partner):**
- Throwaway prototypes
- Generated code
- Configuration files

Thinking "skip TDD just this once"? Stop. That's rationalization.

## Red-Green-Refactor Cycle

### RED - Write Failing Test

Write one minimal test showing what should happen.

**Requirements:**
- One behavior per test
- Clear descriptive name
- Real code (no mocks unless unavoidable)

**Good Example:**
```python
def test_retries_failed_operations_three_times():
    attempts = 0
    def operation():
        nonlocal attempts
        attempts += 1
        if attempts < 3:
            raise Exception("fail")
        return "success"
    
    result = retry_operation(operation)
    
    assert result == "success"
    assert attempts == 3
```

**Bad Example:**
```python
def test_retry_works():  # Vague name
    mock = Mock(side_effect=[Exception(), Exception(), "success"])
    retry_operation(mock)  # Tests mock, not real behavior
    assert mock.call_count == 3
```

### Verify RED - Watch It Fail

**MANDATORY. Never skip.**

```bash
pytest path/to/test.py -v
```

Confirm:
- Test fails (not errors)
- Failure message is expected
- Fails because feature missing (not typos)

**Test passes immediately?** You're testing existing behavior. Fix the test.

**Test errors?** Fix error, re-run until it fails correctly.

### GREEN - Minimal Code

Write the **simplest code** to pass the test.

**Good:** Just enough to pass
```python
def retry_operation(fn, max_retries=3):
    for i in range(max_retries):
        try:
            return fn()
        except Exception:
            if i == max_retries - 1:
                raise
```

**Bad:** Over-engineered
```python
def retry_operation(
    fn,
    max_retries=3,
    backoff="exponential",  # YAGNI
    on_retry=None,          # YAGNI
    retry_exceptions=None,  # YAGNI
):
    # 50 lines of code for features not needed
```

Don't add features. Don't refactor other code. Don't "improve" beyond the test.

### Verify GREEN - Watch It Pass

**MANDATORY.**

```bash
pytest path/to/test.py -v
```

Confirm:
- Test passes
- Other tests still pass
- Output pristine (no errors, warnings)

**Test fails?** Fix code, not test.

**Other tests fail?** Fix now, not later.

### REFACTOR - Clean Up

After green only:
- Remove duplication
- Improve names
- Extract helpers

Keep tests green. Don't add behavior.

### Repeat

Next failing test for next behavior.

## Common Rationalizations

| Excuse | Reality |
|--------|---------|
| "Too simple to test" | Simple code breaks. Test takes 30 seconds. |
| "I'll test after" | Tests passing immediately prove nothing. |
| "Already manually tested" | Ad-hoc ≠ systematic. No record, can't re-run. |
| "Deleting X hours is wasteful" | Sunk cost fallacy. Keeping unverified code is debt. |
| "Need to explore first" | Fine. Throw away exploration, start with TDD. |
| "Test hard = don't need it" | Hard to test = hard to use. Fix the design. |
| "TDD will slow me down" | TDD is faster than debugging. |
| "This is different because..." | It's not. Follow the process. |

## Red Flags - STOP and Start Over

If you catch yourself:
- Writing code before test
- Test passes immediately (without implementation)
- Can't explain why test failed
- Rationalizing "just this once"
- "Keep as reference" or "adapt existing code"
- "I already manually tested it"

**All of these mean: Delete code. Start over with TDD.**

## Verification Checklist

Before marking work complete:

- [ ] Every new function/method has a test
- [ ] Watched each test fail before implementing
- [ ] Each test failed for expected reason
- [ ] Wrote minimal code to pass each test
- [ ] All tests pass
- [ ] Output pristine (no errors, warnings)
- [ ] Tests use real code (mocks only if unavoidable)
- [ ] Edge cases and errors covered

Can't check all boxes? You skipped TDD. Start over.

## Debugging Integration

Bug found? 

1. Write failing test reproducing it
2. Follow TDD cycle
3. Test proves fix and prevents regression

**Never fix bugs without a test.**

## Testing Anti-Patterns to Avoid

- **Testing mock behavior** instead of real behavior
- **Adding test-only methods** to production classes
- **Mocking without understanding** the actual dependencies
- **"and" in test name** - split into multiple tests
- **Huge test setup** - simplify the design

## Final Rule

```
Production code → test exists and failed first
Otherwise → not TDD
```

No exceptions without your human partner's explicit permission.
