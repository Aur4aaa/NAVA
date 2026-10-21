# Standards and content provenance

NAVA's requested initial baseline is **ISO/IEC 27001:2022 with Amendment 1:2024**. The bundled release is `nava-iso27001-2022-amd1-2024-r1`. Its short labels and practical summaries are original application content, not the standard's normative wording. Consult properly licensed material for authoritative requirements and interpretation. The software does not certify an organization.

## Verification state: UNVERIFIED

Official-source access was attempted on **20 October 2026** from the build environment using HTTPS with certificate verification enabled. The network proxy rejected the two requested `www.iso.org` connections with **HTTP 403** before source content could be retrieved. The configured destination policy did not include ISO's website. No TLS or proxy bypass was attempted.

A later retrieval attempt after network configuration changed also returned HTTP 403. No official source content was obtained; the catalog remains unverified.

Consequently:

- The initial edition is a requested baseline, **not a claim that the latest applicable edition and amendments were independently verified**.
- `FrameworkVersion.verification_status` is `unverified`, and `verified_on` is null.
- The verification-attempt date and source locators are recorded in provenance.
- All bundled summaries and their mappings need authorized review against licensed material before authoritative use.
- Structural tests validate identifier coverage and preservation behavior; they do not prove standards equivalence or completeness.

| Source locator | Intended purpose | Actual retrieval result |
| --- | --- | --- |
| <https://www.iso.org/standard/27001> | Official overview and edition listing | Attempted; proxy HTTP 403 |
| <https://www.iso.org/standard/88435.html> | Locator for the requested 2024 amendment | Attempted; proxy HTTP 403; locator itself remains unverified |
| <https://www.iso.org/standard/75652.html> | Locator for ISO/IEC 27002:2022 guidance | Not retrieved because the destination was blocked; locator unverified |

To complete verification, allow access to `www.iso.org` and any verified redirect destination, then inspect the official edition, amendment, and guidance records. An authorized standards maintainer should record the actual verification date, retained source references, and scope of verification in a **new catalog release**. Verification of bibliographic metadata alone must not be represented as validation of every application summary. Do not mark a catalog verified merely because the network destination became accessible.

## Requirements versus reference controls

Seven management-system areas represent **clauses 4–10** separately from Annex A. They remain mandatory areas in the catalog. A missing assessment or incomplete implementation is a gap; there is no Annex A-style exclusion switch on these requirements. These short area summaries do not substitute for a full subclause assessment against licensed requirements.

The catalog contains the **93 Annex A reference identifiers**, grouped as follows:

| Theme | Identifiers | Count |
| --- | --- | ---: |
| Organizational | A.5.1–A.5.37 | 37 |
| People | A.6.1–A.6.8 | 8 |
| Physical | A.7.1–A.7.14 | 14 |
| Technological | A.8.1–A.8.34 | 34 |

Applicability, implementation, and effectiveness are separate organizational decisions. An exclusion needs a reason; an upload alone proves neither implementation nor effectiveness. Selecting a control does not automatically lower a risk score. Organizations may add controls beyond Annex A where risk treatment or obligations require them.

**ISO/IEC 27002:2022 is implementation guidance**, not an additional certification-requirements checklist. The application does not bundle its copyrighted explanatory text.

## Climate amendment

The scope/context workflow asks whether climate change is relevant to the ISMS and records a rationale. It also provides a requirements register for relevant interested-party needs, which may include climate-related requirements. The bundled clause 4 summary identifies these considerations without claiming to reproduce amended text. This does not automatically impose environmental controls unrelated to information-security context and applicable needs.

## Versioning and historical records

Framework catalog releases are separate from organizational scope, risk, assessment, SoA, document, and evidence versions. The seeder creates a release once, adds missing records idempotently, and refuses to overwrite a same-release reference whose content differs. New content belongs in a new `catalog_release` with new reference rows. Existing foreign keys and frozen snapshots retain their original catalog references.

A catalog update does not imply organizational reassessment. An authorized ISMS manager must plan impact review of the scope, risk methodology, risks, applicability decisions, gaps, documents, and audit coverage.

## Organization-supplied licensed material

An organization may record relevant citations or upload licensed material through the private document/evidence workflow when its license permits this. Apply confidential classification and explicit user permissions. Do not place standard PDFs in public static directories, seed data, source control, or unrestricted exports. NAVA's access controls do not enlarge the organization's license rights.

## Outstanding standards work

1. Complete official edition/amendment verification when destination access is available.
2. Have a qualified authorized reviewer validate mappings and original summaries against licensed material.
3. Introduce granular subclause references as a separately versioned reviewed release; the current seven-area assessment is intentionally basic.
4. Add an authorized catalog-review interface and explicit catalog migration/impact-review workflow.
