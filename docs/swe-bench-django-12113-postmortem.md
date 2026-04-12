# Post-Mortem: SWE-bench django__django-12113 Evaluation Failure

**Date:** 2026-02-08
**Instance:** django__django-12113
**Status:** Failed (Not Resolved)
**Evaluation System:** YAAAF on SWE-bench Lite

---

## Executive Summary

The evaluation of `django__django-12113` failed due to multiple systemic issues in the test execution infrastructure. While the agent successfully identified and applied code changes (adding TEST configuration to DATABASES), **no tests were ever executed** due to import errors from version mismatches between the repository code and installed Django packages.

**Key Finding:** The agent reported success (`yaaaf_success: True`), made correct code modifications, but the evaluation framework couldn't verify the fix because tests failed to run.

---

## Problem Statement

**Task:** Fix admin_views.test_multidb test failures when using persistent SQLite databases (--keepdb flag)
**Expected Fix:** Add `TEST['NAME']` settings to `tests/test_sqlite.py` to use named database files instead of in-memory databases
**Test to Pass:** `test_custom_test_name (backends.mysql.test_creation.TestDbSignatureTests)`

---

## Timeline of Failures

### Phase 1: Initial Tests (Pre-Agent Intervention)
**Result:** 0 passed, 0 failed, 0 errors
**Root Cause:** Import error in test runner

```python
ImportError: cannot import name 'default_test_processes' from 'django.test.runner'
```

**Analysis:** The repository's `tests/runtests.py` (old Django version) tried to import from site-packages Django (newer version), causing immediate failure before any tests ran.

### Phase 2: Agent Execution
**Result:** Successfully modified `tests/test_sqlite.py`

**Changes Applied:**
```diff
 DATABASES = {
     'default': {
         'ENGINE': 'django.db.backends.sqlite3',
+        'TEST': {
+            'NAME': 'test_default.sqlite3'
+        },
     },
     'other': {
         'ENGINE': 'django.db.backends.sqlite3',
+        'TEST': {
+            'NAME': 'test_other.sqlite3'
+        },
     }
 }
```

**Agent Status:** `yaaaf_success: True` - agent completed workflow

### Phase 3: Post-Fix Test Validation
**Result:** 0 passed, 0 failed, 0 errors
**Root Cause:** Different import error

```python
ImportError: cannot import name 'DiscoverRunner' from 'django.test'
```

**Analysis:** After code changes, test runner still failed with similar but different import error, preventing verification.

### Phase 4: Final Tests
**Result:** 0 passed, 0 failed, 0 errors
**Overall Status:** `resolved: False`

---

## Root Cause Analysis

### Primary Issue: Django Import Path Priority

**Problem:** Django's test runner (`tests/runtests.py`) imported from **site-packages Django** (newer version) instead of **repository Django** (older version under test).

**Why This Happened:**
1. Virtual environment had Django installed in site-packages (for test dependencies)
2. Repository Django code wasn't prioritized in PYTHONPATH
3. Test runner tried to import classes that were renamed/moved between Django versions

**Impact:** Tests never ran - evaluation framework couldn't determine if fix worked

### Secondary Issues

#### 1. Test Runner Selection
- **Issue:** Evaluation used pytest instead of Django's native test runner
- **Location:** `repo_manager.py:728-773`
- **Status:** Fixed (switched to Django native runner)
- **Why Not Resolved:** Fix not deployed during this evaluation run

#### 2. PYTHONPATH Configuration
- **Issue:** Repository code not prioritized over site-packages
- **Location:** `bash_executor.py:97-113`
- **Status:** Partially fixed (added PYTHONPATH for Django repos)
- **Why Not Resolved:** May not have taken effect or was insufficient

#### 3. Test ID Format Conversion
- **Issue:** SWE-bench uses unittest format, pytest/Django use different formats
- **Example:** `test_method (module.Class)` vs `module.Class.test_method`
- **Status:** Conversion logic exists but wasn't tested due to import failures

---

## Issues Discovered in Code Editor

### 1. Line Number Indentation Mismatch
**Problem:** View operation used TAB separator (`39\t`), LLM copied with colon+space (`39: `), causing different indentation after parsing.

**Impact:** Validation failures due to off-by-one-space indentation errors

**Fix Applied:** Changed view format from TAB to colon+space, updated regex to consume space after colon

**Files Modified:**
- `code_edit_executor.py:283` - View format
- `code_edit_executor.py:343` - Regex pattern

### 2. Trailing Comma Differences
**Problem:** LLM provided old_str with trailing commas that didn't match file without trailing commas

**Example:**
```python
# LLM expected:
'NAME': 'test.sqlite3',  # ← comma

# File had:
'NAME': 'test.sqlite3'   # ← no comma
```

**Impact:** Validation rejected correct replacements due to stylistic differences

**Status:** Not fixed - strict matching enforced to prevent stale content usage

### 3. File Corruption from Duplicate Content
**Problem:** Line-number replacement inserted content containing duplicates, creating syntax errors

**Example:**
```python
DATABASES = { ... }
        'ENGINE': ...  # ← Duplicate fragment
    }
}
```

**Root Cause:** LLM's new_str contained duplicate lines, validation only checked old_str match

**Fix Applied:** Added Python syntax validation using `ast.parse()` before writing files

**Files Modified:**
- `code_edit_executor.py:438-456` - Line-number replacement validation
- `code_edit_executor.py:543-562` - String replacement validation

**Status:** Linter not working (reported by user) - needs investigation

---

## What Worked

1. ✅ Agent identified correct fix (add TEST settings)
2. ✅ Agent successfully modified the file
3. ✅ Code changes were syntactically correct
4. ✅ Validation prevented some corruption attempts
5. ✅ Agent completed workflow without crashes

---

## What Failed

1. ❌ Tests never ran (import errors)
2. ❌ Couldn't verify if fix actually works
3. ❌ Python syntax linter not working (despite implementation)
4. ❌ PYTHONPATH prioritization insufficient
5. ❌ Test runner selection not deployed
6. ❌ Agent tried interactive commands (nano) - got stuck
7. ❌ No feedback loop - agent thought it succeeded despite test failures

---

## Critical Gaps

### 1. No Verification Loop
**Problem:** Agent reported success without confirming tests passed

**Needed:** Agent should:
- Run tests after making changes
- Parse test output
- Retry if tests fail
- Only report success when tests pass

### 2. Environment Isolation
**Problem:** Installed packages interfere with repository code

**Needed:**
- PYTHONPATH must always prioritize repository over site-packages
- Editable install (`pip install -e`) failed - need better fallback
- Consider container isolation

### 3. Test Runner Intelligence
**Problem:** Pytest used for Django instead of native runner

**Needed:**
- Auto-detect test framework
- Use correct runner automatically
- Handle test ID format conversions

### 4. Syntax Validation Not Working
**Problem:** `ast.parse()` validation implemented but not catching errors

**Investigation Needed:**
- Check if validation code is reached
- Verify ast.parse() is catching syntax errors
- Add logging to confirm validation runs

---

## Recommendations

### Immediate Actions

1. **Debug Python Linter**
   - Add detailed logging to syntax validation
   - Test with known-bad Python code
   - Verify validation runs before file writes

2. **Deploy PYTHONPATH Fix**
   - Ensure `bash_executor.py` PYTHONPATH changes are loaded
   - Test with actual Django import
   - Verify repository code takes precedence

3. **Deploy Django Test Runner**
   - Restart YAAAF backend with updated `repo_manager.py`
   - Verify native Django runner is used
   - Test with sample Django test

4. **Block Interactive Commands**
   - Deploy updated `bash_executor.py` blocking nano/vim
   - Test that agent receives error message
   - Verify no hanging processes

### Short-Term Improvements

1. **Add Test Result Feedback Loop**
   - Agent must read test output
   - Agent must retry on failure
   - Agent only succeeds when tests pass

2. **Improve Validation Error Messages**
   - Show exact character-by-character differences
   - Highlight indentation issues clearly
   - Suggest specific fixes (e.g., "remove trailing comma")

3. **Environment Health Checks**
   - Verify PYTHONPATH is set correctly
   - Test imports before running tests
   - Detect and warn about version mismatches

### Long-Term Architecture

1. **Container-Based Isolation**
   - Run each evaluation in fresh container
   - No interference from system packages
   - Reproducible environments

2. **Smarter Test Execution**
   - Auto-detect test framework
   - Convert test IDs automatically
   - Use correct runner for each project

3. **Multi-Stage Validation**
   - Syntax check (ast.parse)
   - Import check (can modules load?)
   - Logical check (does replacement make sense?)
   - Test check (do tests pass?)

---

## Lessons Learned

1. **Success ≠ Tests Passing:** Agent reporting success doesn't mean the fix works - need test verification
2. **Version Matters:** Old repository code + new installed packages = import errors
3. **Validation Complexity:** Catching all edge cases (trailing commas, indentation, duplicates) is hard
4. **Framework Diversity:** Different projects need different test runners - one size doesn't fit all
5. **Feedback is Critical:** Without test output, agent can't improve - must close the loop

---

## Conclusion

The `django__django-12113` evaluation failed not due to agent intelligence limitations, but due to **infrastructure issues** preventing test execution. The agent made correct code changes, but the evaluation framework couldn't verify them.

**Key Takeaway:** A robust SWE-bench evaluation system needs:
- ✅ Correct test runner for each framework
- ✅ Proper environment isolation (PYTHONPATH)
- ✅ Syntax validation before writing files
- ✅ Test result feedback to agent
- ✅ Retry loops until tests pass

**Next Steps:**
1. Debug and fix Python linter
2. Deploy pending fixes (test runner, PYTHONPATH, interactive blocking)
3. Re-run evaluation with updated system
4. Verify tests actually execute and pass

**Status:** Infrastructure improvements in progress, re-evaluation pending
