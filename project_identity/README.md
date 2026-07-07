# Project Identity Assets

This folder groups the reusable NEXUS identity assets for ROBOTarm_NEXUS:
the logo / intro animation, and the legal / community templates.

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

## Logo intro

To play the animated NEXUS logo intro from the repo root:

```bash
bash project_identity/logo/play_logo_intro.sh 30 golden
```

Styles: `golden` (default), `blackgold`, `cyber`, `ice`, `matrix`, `ember`,
`random`. Requires `python3` with `numpy`, `scipy.ndimage`, `PIL`; the script
fails open (exits 0 silently) if anything is missing, so it is safe to call
from `set -euo pipefail` boot scripts.

## Reuse

To reuse this identity bundle in another NEXUS project: copy this folder,
then update the project name, author, copyright year, third-party notices,
and any README links.
