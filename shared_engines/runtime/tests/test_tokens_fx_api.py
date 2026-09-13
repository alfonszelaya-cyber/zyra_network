name: ZYRA Hardening Block 2

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: write

jobs:
  harden:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install cryptography pytest

      - name: Patch runtime tests (person subjects -> organization, add bypass certification)
        run: |
          python3 - <<'PYEOF'
          from pathlib import Path

          path = Path(
              "shared_engines/runtime/tests/"
              "test_runtime_api.py"
          )
          src = path.read_text(encoding="utf-8")

          MARKER = (
              "test_person_register_is_bypass_blocked"
          )

          if MARKER in src:
              print("RESULT: already patched, nothing to do")
          else:
              fixed = src.replace(
                  '"kind": "person"',
                  '"kind": "organization"',
              )
              new_test = '''

          def test_person_register_is_bypass_blocked(
              cluster: _Cluster,
          ) -> None:
              """HARDENING CERTIFICATION: creating a PERSON via
              the legacy door is refused — persons must go
              through /identity/enroll (mandatory biometric
              proofing)."""
              status, payload = cluster.call(
                  "POST",
                  "/identity/register",
                  {
                      "kind": "person",
                      "display_name": "Bypass Try",
                      "actor": "attacker",
                  },
              )
              assert status == 403
              assert (
                  payload["error"]["type"]
                  == "person_bypass_forbidden"
              )
          '''
              fixed = fixed + new_test
              path.write_text(fixed, encoding="utf-8")
              print("RESULT: PATCHED OK")

          import ast
          ast.parse(
              path.read_text(encoding="utf-8")
          )
          print("SYNTAX OK")
          PYEOF

      - name: Biometrics suite stays green (13 tests)
        run: python -m shared_engines.security.biometrics -v

      - name: Runtime tests (all must pass now)
        run: python -m pytest shared_engines/runtime/tests -q

      - name: Commit patch (only if all green)
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add shared_engines/runtime/tests/test_runtime_api.py
          if git diff --cached --quiet; then
            echo "Nothing to commit"
          else
            git commit -m "harden: runtime tests use non-person subjects; certify person bypass is blocked"
            git push
          fi
