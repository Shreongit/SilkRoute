# Project plan

## Stage 1 — foundation and frontend prototype
- Complete: editorial storefront design, responsive routes, search/filter/sort interactions, typed mock catalogue and initial read-only Flask API.

## Stage 2 — creator publishing and persistence
- Complete foundation: SQLAlchemy models and Flask-Migrate revisions; PostgreSQL and SQLite configuration; the four fixed product categories; registration/login/logout; creator-owned drafts; category validation; private local resource storage; publish/unpublish workflow; React API service and creator studio; API-backed public catalogue; tests and setup documentation.
- Current limitations: local filesystem storage is development-only; users cannot recover accounts; external identity/OAuth is not implemented; uploaded source-file delivery is disabled.

## Future work
- Production object storage and malware scanning, download entitlements, audit/retention policies, account recovery, creator moderation, accessibility review, observability and deployment hardening.
- Payments, creator payouts, subscriptions, commissions and refunds require product/legal/accounting decisions and remain outside Stage 2.
