# Contributing to WaveDeck

Thanks for helping improve WaveDeck.

## Good Contribution Areas

- Windows desktop UX
- PowerPoint export fidelity
- Cache validation and recovery
- Performance and responsiveness
- Automated testing and packaging
- Documentation and onboarding

## Before You Open A Pull Request

1. Keep changes scoped.
2. Do not add fake marketing claims to the README.
3. Do not upload private decks, API keys, cookies, or customer content.
4. Avoid logging slide contents or screenshots that contain sensitive material.
5. Add or update tests when behavior changes.

## Local Verification

```powershell
.venv\Scripts\python.exe -m pytest -q
```

For a Windows + PowerPoint smoke test:

```powershell
.venv\Scripts\python.exe tests\integration_powerpoint_smoke.py
```

## Scope Notes

- The repository is Windows-first.
- PowerPoint is a required dependency for real deck export.
- Public screenshots should not include camera footage.
- If you expand gesture behavior, keep the slide-stage experience readable and stable.
