# Win7 Startup Binding and Console Repair

Status: implementation, scoped review and native acceptance complete.

- Repository: `https://github.com/lurenxing628/----`, baseline `32dd461f`.
- Isolated checkout: `D:/Github/-----win7-startup-20261004`.
- Branch: `fix/win7-startup-20261004`.
- Scope: console code page and UTF-8 logs, complete Unicode/space/! paths,
  exclusive Windows listener ownership, and health/runtime identity matching.
- Preserve the existing database lock, owner checks, shutdown and persistence
  behavior. Do not modify original applications, databases or VM snapshots.

Windows listeners are bound before endpoint publication and the same server is
passed to the service loop. Binding and contract failures close the listener.
Existing APS candidate-port fallback behavior is retained, including APS_PORT;
PeriodEstimate's explicit-port failure policy is not copied into this project.

Host socket and lifecycle regression checks are not Win7 native acceptance.
Native build and acceptance evidence is kept separately under
`evidence/Win7Launcher/20261004/`. The VM was originally suspended and its
original nine shared-folder keys and two snapshots were recorded before the
temporary task share.

Native findings fixed through separately preserved candidates:
- v2: CLR2 SHA256Managed has no public Dispose method. Use Clear.
- v3: duplicate startup publishes a shared error; both BATs aborted although
  the owner was healthy. Recheck real ownership/identity before waiting/reuse.
- v4: concurrent CMD RANDOM sequences collided on temporary protocol files.
  Generate a checked GUID per launcher and scope all four temporary files to it.

Final v5 was built inside Win7 SP1 x64 using Python 3.8.10/PyInstaller 4.10.
Native acceptance: fresh Unicode/space/! paths, two real ShellExecute requests
120.0052 ms apart (both rc0; one backend and Chrome main process), current-runtime
reopen, all owned windows closed/reopened without changing PID/instance, official
stop/restart with UI-verified Chinese material/spec/unit/12.5 stock/enabled,
default and explicit-port fallback preserving the existing occupier, and actual
SO_REUSEADDR bind rejection 10013 preserving the v5 listener PID/instance.

Final targeted host gates: launcher 205 passed; core/restore-entrypoint 32 passed;
scoped Ruff passed and Python 3.8 Pyright 0 errors/0 warnings. A Windows test
driver's SQLite URI mapping now uses url2pathname; readiness waits for the fresh
published contract rather than only a pre-bind callback marker. Review found no
new blocking issues. Native cross-account and actual restore-host acceptance
remain outside this run. Existing waiting evidence still uses lock declarations
and PID/image; a stale same-name PID can delay failure but full health identity
continues to protect final reuse.

VM restoration verified: task-owned processes 0, keep-awake exited, original
nine sharing keys restored, original two snapshots unchanged, power suspended.
No original user applications/databases/snapshots were removed or replaced.
Release ZIP SHA256:
E2A49B43615124C2A3F4586FDE2E401D1721F5D5A81A8E6D9A26807F452A201C

Merge follow-up on 2026-10-05 against main f9eec457:
- The broader recovery lane exposed another Windows fixture URI guard. It now
  uses url2pathname and retains the original temp-directory ownership check.
- Native tasklist output in the cleanup helper is read as bytes, comparing
  exact ASCII PID fields without decoding localized output as UTF-8.
- Three PID-query regression cases and the affected startup/recovery cases pass
  with reader-thread warnings treated as errors. Production files are unchanged.
- The restore replay subprocess's duplicate URI guard was corrected too.
- Merge verification: startup/entrypoint/recovery lane 260 passed; restore-host
  lane 28 passed; repository smoke checks 8 passed. Three general gate failures
  were reproduced unchanged on original main f9eec457: missing dead-path baseline
  (two checks) and pre-existing schema-documentation debt (one check). No baseline
  was refreshed to conceal these failures; this is not an all-green full gate.
