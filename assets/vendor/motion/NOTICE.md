# Pinned offline motion dependencies

- GSAP 3.15.0, `dist/gsap.min.js`, from npm `gsap@3.15.0`. Copyright (c) 2008–2026 GreenSock. Standard no-charge license: https://gsap.com/standard-license . The distributed file retains the upstream copyright/license header. See also https://github.com/greensock/GSAP .
- D3 7.9.0, `dist/d3.min.js`, from npm `d3@7.9.0`. Copyright 2010–2023 Mike Bostock. ISC license is preserved in `D3-LICENSE` and the distributed file.

These exact bytes are embedded into the shared transition HTML. Production renders make no CDN or npm requests. Updating a library changes the rendered-page fingerprint and invalidates affected clip caches.
