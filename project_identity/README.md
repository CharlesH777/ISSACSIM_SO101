# Project Identity Assets

This folder stores repo-specific logo assets and legal/community documents.

## Layout

```text
project_identity/
├── logo/
│   ├── nexus_logo.py
│   ├── nexus_logo.png
│   └── play_logo_intro.sh
└── legal/
    ├── LICENSE
    ├── NOTICE.md
    ├── CODE_OF_CONDUCT.md
    └── CONTRIBUTING.md
```

## Canonical vs. template

- The **canonical** license of this repo is at the repo root:
  [`../LICENSE.md`](../LICENSE.md) (GitHub auto-detected).
- `legal/LICENSE` is the identity-bundle source copy with identical content.
- `legal/NOTICE.md`, `legal/CONTRIBUTING.md` have been adapted to the
  ROBOTarm_NEXUS context (Isaac Lab / Lula / SO-101 third-party stack).
- `legal/CODE_OF_CONDUCT.md` is the generic Contributor Covenant template.

## Logo Intro

To play the terminal intro from the repo root:

```bash
bash project_identity/logo/play_logo_intro.sh 30 golden
```

Styles: `golden` (default), `blackgold`, `cyber`, `ice`, `matrix`, `ember`,
`random`. Requires `python3` with `numpy`, `scipy.ndimage`, `PIL`; the script
fails open (exits 0 silently) if anything is missing, so it is safe to call
from `set -euo pipefail` boot scripts.

## Reuse

If you copy these files into another repo, update the project name, author,
copyright year, third-party notices, and README links.
