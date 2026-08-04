# Changelog

All notable changes to this project will be documented in this file.

## Unreleased

### Added

- Open-source project documentation for setup, contribution, security, and content licensing.
- Automated tests for authentication, validation, configuration, guestbook, and static export behavior.
- GitHub Actions workflow for running the test suite.
- Basic local admin login rate limiting.
- Shared security headers for local and static responses.
- Shared security headers for Cloudflare Pages Function JSON responses.
- IP-wide admin login rate limiting in addition to the existing IP+username bucket.
- Shared accessible dialog behavior with focus entry, focus trapping, focus return, Escape dismissal, and background inertness.
- Mobile lightbox close control, swipe navigation, and keyboard photo navigation.
- Restorable URL state for gallery filters and the open photo.
- Admin collection search, collapsed editors, unsaved-change warnings, advanced-field disclosure, and a publish checklist.

### Changed

- Restored the public counter to increment for every recorded exhibition page visit instead of deduplicating by browser token.
- Generalized administrator examples from project-specific values to `admin` and `/admin`.
- Made admin login rate limiting thread-safe for the local threaded server.
- Preserved the original project prompt under `docs/original-specification.md`.
- Simplified the responsive header to a single row with the MoMent logo centered between the remaining controls.
- Stabilized randomized photo order for the browser session and converted lightbox information controls to real tabs.
- Removed the frequently rewritten gallery grid from live-region announcements and added a skip link and concise status updates.
- Changed the lightbox `정보` and `방명록` tabs from capsule controls to compact rectangular controls.

### Removed

- Removed the public history dialog and navigation control.
- Removed background audio, its navigation control, bundled media asset, and static export path.
- Retired audio asset URLs now return an uncached `410 Gone` response.
- Removed the public map menu, map dialog, lightbox map action, Leaflet assets, and OpenStreetMap CSP allowance.
- Removed the persistent lightbox previous/next control bar and photo position counter while preserving keyboard and swipe navigation.

### Security

- Documented the difference between source code licensing and media content rights.
- Added HTTPS-aware secure cookie configuration based on the admin server URL.
- Allowed `blob:` images in CSP so the admin upload preview path remains compatible with browser policy.
- Raised the Pillow minimum to 12.3.0 and added CI dependency auditing.
- Refused non-loopback admin binds unless an explicit private-network exception is enabled.
- Removed committed status-token fallback material and replaced hidden guestbook deletion passwords with generated high-entropy tokens.
- Added transactional D1-backed endpoint rate limits without User-Agent-derived keys.
- Moved D1 schema and moderation maintenance out of public request paths into a versioned migration.
- Added anonymous visit deduplication, HSTS, stricter CSP directives, a real static 404 page, admin same-origin mutation checks, and query-redacted local error logging.

## v0.1.0 Draft Release Notes

MoMent is prepared as a small open-source online photography exhibition platform while preserving the original MoMent exhibition workflow.

Highlights:

- Local Python admin app for managing photos and metadata.
- Static export for Cloudflare Pages.
- Minimal public exhibition UI with photo interactions, lightbox, visit counter, latest-update marker, and trace guestbook.
- Tests and CI covering the core local app logic.

Maintainer confirmation required before release:

- Verify the public demo URL and screenshots.
- Confirm reuse permissions for photographs, logos, QR images, and exhibition copy.
- Confirm GitHub repository About fields, topics, and release notes in the web UI.
