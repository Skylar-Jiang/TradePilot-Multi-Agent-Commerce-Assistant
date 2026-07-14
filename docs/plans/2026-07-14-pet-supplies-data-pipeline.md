# Pet Supplies Data Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

> **Runtime Note:** Run every command in the `shixun` conda environment. Prefer `conda run -n shixun ...` so the exact interpreter and installed test tools are used consistently.

> **Current Progress:** 100% complete for the pet-supplies pipeline scope in this plan. Completed: metadata prefilter, review prefilter, importer, duplicate-review handling, review pruning against the reduced filtered dataset, cleaning script with runtime progress output, pet-supplies domain profile, pet-supplies domain adapter, pet-supplies SQL statistics provider, factory wiring, and targeted end-to-end validation.

> **Current Status Summary:**
> 1. Product metadata prefilter is complete and tested.
> 2. Review prefilter is complete and tested, including capped reviews per parent product.
> 3. Importer is complete for `products`, `competitor_offers`, `reviews`, and product `knowledge_sources`.
> 4. Importer now shows runtime progress and handles duplicate review IDs more safely.
> 5. Existing over-imported review data was pruned so the database now matches the reduced filtered reviews dataset.
> 6. Cleaning script is complete, tested, and now shows runtime progress during large real-data runs.
> 7. Real pet-supplies runtime profile is complete:
>    `config/domain_profiles/pet_supplies.yaml`
> 8. Real pet-supplies adapter is complete:
>    `app/adapters/domains/pet_supplies.py`
> 9. Real pet-supplies SQL statistics provider is complete:
>    `app/statistics/providers/pet_supplies.py`
> 10. Statistics factory wiring is complete and tested.
> 11. Targeted verification is complete with `18 passed` across the pet-supplies pipeline, profile, adapter, provider, injection, and workflow tests.

> **Quick Start Commands:**
> `conda run -n shixun python scripts/init_db.py`
> `conda run -n shixun python scripts/domain_imports/prefilter_pet_supplies.py`
> `conda run -n shixun python scripts/domain_imports/prefilter_pet_supplies_reviews.py`
> `conda run -n shixun python scripts/domain_imports/import_pet_supplies.py`
> `conda run -n shixun python scripts/domain_imports/prune_pet_supplies_reviews.py --skip-upgrade`
> `conda run -n shixun python scripts/domain_imports/clean_pet_supplies.py`
> `conda run -n shixun python -m pytest tests/integration/data/test_pet_supplies_prefilter.py -v`

> **Common Test Commands:**
> `conda run -n shixun python -m pytest tests/integration/data/test_pet_supplies_prefilter.py -v`
> `conda run -n shixun python -m pytest tests/integration/data/test_pet_supplies_reviews_prefilter.py -v`
> `conda run -n shixun python -m pytest tests/integration/data/test_pet_supplies_import.py -v`
> `conda run -n shixun python -m pytest tests/integration/data/test_pet_supplies_prune_reviews.py -v`
> `conda run -n shixun python -m pytest tests/integration/data/test_pet_supplies_clean.py -v`
> `conda run -n shixun python -m pytest tests/integration/data/test_pet_supplies_adapter.py -v`
> `conda run -n shixun python -m pytest tests/unit/statistics/test_pet_supplies_provider.py -v`
> `conda run -n shixun python -m ruff check scripts/domain_imports tests/integration/data`

> **What Is Already Built:**
> - `scripts/domain_imports/prefilter_pet_supplies.py`
> - `scripts/domain_imports/prefilter_pet_supplies_reviews.py`
> - `scripts/domain_imports/import_pet_supplies.py`
> - `scripts/domain_imports/prune_pet_supplies_reviews.py`
> - `scripts/domain_imports/clean_pet_supplies.py`
> - `config/domain_profiles/pet_supplies.yaml`
> - `app/adapters/domains/pet_supplies.py`
> - `app/statistics/providers/pet_supplies.py`
> - `tests/integration/data/test_pet_supplies_prefilter.py`
> - `tests/integration/data/test_pet_supplies_reviews_prefilter.py`
> - `tests/integration/data/test_pet_supplies_import.py`
> - `tests/integration/data/test_pet_supplies_prune_reviews.py`
> - `tests/integration/data/test_pet_supplies_clean.py`
> - `tests/integration/data/test_pet_supplies_adapter.py`
> - `tests/unit/statistics/test_pet_supplies_provider.py`

> **Completion Result:**
> 1. Filtered metadata import completed successfully for `161540` products/offers/knowledge sources.
> 2. Filtered review import completed successfully for `591406` retained reviews after duplicate handling.
> 3. Stale over-imported reviews were pruned from the SQLite database so the real dataset now matches the reduced review JSON.
> 4. Cleaning completed successfully on the reduced real dataset with runtime progress output.
> 5. Pet-supplies runtime profile, adapter, SQL statistics provider, and factory wiring were all implemented and verified.
> 6. Targeted verification passed:
>    `conda run -n shixun python -m pytest tests/integration/data tests/unit/statistics tests/integration/test_statistics_injection.py tests/unit/test_domain_profiles.py tests/unit/test_workflow.py -v`
>    Result: `18 passed`

> **How To Continue Testing:**
> 1. Prefilter product metadata:
>    `conda run -n shixun python scripts/domain_imports/prefilter_pet_supplies.py`
> 2. Prefilter reviews using the filtered product set:
>    `conda run -n shixun python scripts/domain_imports/prefilter_pet_supplies_reviews.py`
> 3. Initialize or upgrade the local SQLite database:
>    `conda run -n shixun python scripts/init_db.py`
> 4. Import the filtered product and review datasets:
>    `conda run -n shixun python -u scripts/domain_imports/import_pet_supplies.py --metadata-input data/filtered/meta_pet_supplies_prefiltered.jsonl --reviews-input data/filtered/pet_supplies_reviews_prefiltered.jsonl`
> 5. Prune stale reviews if the filtered review file has been reduced since an earlier full import:
>    `conda run -n shixun python -u scripts/domain_imports/prune_pet_supplies_reviews.py --skip-upgrade`
> 6. Normalize the imported records:
>    `conda run -n shixun python scripts/domain_imports/clean_pet_supplies.py`
> 7. Run targeted tests after code changes:
>    `conda run -n shixun python -m pytest tests/integration/data/test_pet_supplies_prefilter.py -v`
>    `conda run -n shixun python -m pytest tests/integration/data/test_pet_supplies_reviews_prefilter.py -v`
>    `conda run -n shixun python -m pytest tests/integration/data/test_pet_supplies_import.py -v`
>    `conda run -n shixun python -m pytest tests/integration/data/test_pet_supplies_prune_reviews.py -v`
>    `conda run -n shixun python -m pytest tests/integration/data/test_pet_supplies_clean.py -v`
>    `conda run -n shixun python -m pytest tests/integration/data/test_pet_supplies_adapter.py -v`
>    `conda run -n shixun python -m pytest tests/unit/statistics/test_pet_supplies_provider.py -v`
> 8. Run broader verification when needed:
>    `conda run -n shixun python -m pytest tests/integration/data tests/unit/statistics tests/integration/test_statistics_injection.py tests/unit/test_domain_profiles.py tests/unit/test_workflow.py -v`
> 9. Run lints for the data pipeline area:
>    `conda run -n shixun python -m ruff check scripts/domain_imports tests/integration/data`

> **Current Known Import Issue History:**
> - The first full import failed on `UNIQUE constraint failed: reviews.review_id`.
> - Fix applied:
>   1. `review_id` generation now includes `text` in addition to `parent_asin`, `asin`, `user_id`, `timestamp`, and `title`.
>   2. Same-run duplicate `review_id` values are skipped and counted as `skipped_duplicate_reviews`.
> - Final result after re-import and review pruning:
>   1. Importer completed successfully on the filtered datasets.
>   2. Database review volume was reduced to the filtered target set with `prune_pet_supplies_reviews.py`.
>   3. Cleaning completed successfully on the reduced dataset.

> **Next Session Prompt:**
> `我现在继续 TradePilot 的 pet supplies 数据链路工作。请先阅读 F:\\TradePilot\\docs\\plans\\2026-07-14-pet-supplies-data-pipeline.md，然后基于当前代码状态继续。已完成：两份预处理脚本、导入脚本、清洗脚本和对应测试。请先查看我贴出的最新导入/清洗输出结果，再判断下一步是修导入问题、执行清洗，还是开始做 pet_supplies 的 domain profile / domain adapter / SQL StatisticsProvider。`

**Goal:** Build the teammate-one pet supplies data pipeline from raw metadata through prefiltering, import, cleaning, and SQL statistics output.

**Architecture:** Keep the pipeline split into four layers so each stage has one job: prefilter the huge raw JSONL to reduce load, import the filtered records into existing shared tables, normalize and deduplicate the imported records, then compute deterministic SQL statistics through a `StatisticsProvider`. Preserve the shared contracts and database schema; store pet-specific fields in `attributes_json` and `metadata_json`.

**Tech Stack:** Python 3.12, JSONL, SQLite, SQLAlchemy, Alembic, pytest

---

### Task 1: Create the Pet Supplies Plan Branch and Working Notes

**Files:**
- Create: `docs/plans/2026-07-14-pet-supplies-data-pipeline.md`
- Reference: `docs/team-work-split.md`
- Reference: `docs/data-contract.md`
- Reference: `docs/contract-governance.md`

**Step 1: Create the business branch**

Run: `git switch -c data/pet-supplies-pipeline`
Expected: Git switches to a new `data/pet-supplies-pipeline` branch.

**Step 2: Confirm protected files before coding**

Check:
- `app/adapters/base.py`
- `app/adapters/profiles.py`
- `app/statistics/contracts.py`
- `app/statistics/factory.py`
- `app/db/models/core.py`
- `app/db/repositories/protocols.py`
- `migrations/versions/20260714_0001_initial_schema.py`

Expected: Treat these as read-only unless the Contract Maintainer explicitly asks for a contract PR.

**Step 3: Commit**

```bash
git add docs/plans/2026-07-14-pet-supplies-data-pipeline.md
git commit -m "docs: add pet supplies pipeline plan"
```

### Task 2: Add a Prefilter Script for the Large Raw Metadata File

**Files:**
- Create: `scripts/domain_imports/prefilter_pet_supplies.py`
- Reference: `F:/TradePilot/data/meta_Pet_Supplies.jsonl/meta_Pet_Supplies.jsonl`
- Test: `tests/integration/data/test_pet_supplies_prefilter.py`

**Step 1: Write the failing test**

Test behaviors:
- keeps rows with `price`, `title`, and `parent_asin`
- drops rows where `price` is `null`
- keeps rows where `main_category == "Pet Supplies"` or `"Pet Supplies"` appears in `categories`
- writes a filtered JSONL output file
- prints a summary count for kept and dropped rows

Example test fixture shape:

```python
def test_prefilter_drops_rows_with_missing_price(tmp_path):
    input_path = tmp_path / "raw.jsonl"
    output_path = tmp_path / "filtered.jsonl"
    input_path.write_text(
        "\n".join(
            [
                '{"main_category":"Pet Supplies","title":"A","price":12.5,"parent_asin":"P1","categories":["Pet Supplies"]}',
                '{"main_category":"Pet Supplies","title":"B","price":null,"parent_asin":"P2","categories":["Pet Supplies"]}',
            ]
        ),
        encoding="utf-8",
    )

    summary = prefilter_pet_supplies(input_path, output_path)

    assert summary.kept == 1
    assert summary.dropped_missing_price == 1
```

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/data/test_pet_supplies_prefilter.py -v`
Expected: FAIL because the script and helper function do not exist yet.

**Step 3: Write minimal implementation**

Implementation requirements:
- stream line-by-line instead of loading the full 1.57 GB file into memory
- parse each JSON object safely
- keep only records that satisfy:
  - `price is not None`
  - `title` is non-empty
  - `parent_asin` is non-empty
  - pet-supplies match by `main_category` or `categories`
- write kept records as JSONL
- return a summary object with counters

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/data/test_pet_supplies_prefilter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/domain_imports/prefilter_pet_supplies.py tests/integration/data/test_pet_supplies_prefilter.py
git commit -m "feat(data): add pet supplies metadata prefilter"
```

### Task 3: Add the Real Pet Supplies Domain Profile

**Files:**
- Create: `config/domain_profiles/pet_supplies.yaml`
- Test: `tests/unit/test_domain_profiles.py`
- Reference: `config/domain_profiles/generic_cross_border_demo.yaml`

**Step 1: Write the failing test**

Add a test that:
- loads `pet_supplies`
- validates `profile_id == "pet_supplies"`
- validates `data_origin == "real"` or the agreed value for the profile
- validates the adapter path points to the pet-supplies adapter

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/test_domain_profiles.py -v`
Expected: FAIL because the profile file does not exist.

**Step 3: Write minimal implementation**

Profile fields:
- `profile_id: pet_supplies`
- `display_name: TradePilot Pet Supplies`
- `data_origin: real`
- `implementation_status: scaffold`
- `adapter: app.adapters.domains.pet_supplies.PetSuppliesDomainAdapter`
- `knowledge_domains: [product_knowledge, review_insight]`
- `notes: Real pet supplies metadata and review domain.`

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/test_domain_profiles.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add config/domain_profiles/pet_supplies.yaml tests/unit/test_domain_profiles.py
git commit -m "feat(data): add pet supplies domain profile"
```

### Task 4: Import Prefiltered Pet Supplies Metadata into Shared Tables

**Files:**
- Create: `scripts/domain_imports/import_pet_supplies.py`
- Test: `tests/integration/data/test_pet_supplies_import.py`
- Reference: `scripts/seed_demo.py`
- Reference: `app/db/models/core.py`
- Reference: `app/db/repositories/sqlalchemy.py`

**Step 1: Write the failing test**

Test behaviors:
- imports one filtered record into `products`
- writes one market record into `competitor_offers`
- writes one text evidence record into `knowledge_sources`
- is idempotent for the same `parent_asin`

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/data/test_pet_supplies_import.py -v`
Expected: FAIL because the import script does not exist.

**Step 3: Write minimal implementation**

Import mapping:
- `products.name <- title`
- `products.category <- normalized leaf category or "pet-supplies"`
- `products.data_origin <- user` for the product profile created in the repo layer
- `products.attributes_json <- {"parent_asin", "store", "brand", "categories", "details", "images", "videos"}`
- `products.payload_json <- normalized product payload compatible with `ProductProfile``
- `competitor_offers.attributes_json <- {"price", "average_rating", "rating_number", "store", "brand", "categories", "parent_asin"}`
- `knowledge_sources.content <- concatenated title + features + description + selected details`
- `knowledge_sources.metadata_json <- source file path, source line number, parent_asin`

Idempotency rule:
- use `parent_asin` as the natural identifier in imported metadata logic
- if a product for the same `parent_asin` already exists, update or skip rather than duplicate

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/data/test_pet_supplies_import.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/domain_imports/import_pet_supplies.py tests/integration/data/test_pet_supplies_import.py
git commit -m "feat(data): import pet supplies metadata into shared tables"
```

### Task 5: Clean and Normalize Imported Pet Supplies Data

**Files:**
- Create: `scripts/domain_imports/clean_pet_supplies.py`
- Test: `tests/integration/data/test_pet_supplies_clean.py`
- Reference: `app/schemas/product.py`

**Step 1: Write the failing test**

Test behaviors:
- normalizes `price` to decimal-compatible numeric text
- normalizes `average_rating` and `rating_number`
- resolves `brand` from `details.Brand` first, then falls back to `store`
- normalizes category paths to a stable list
- preserves raw fields in `metadata_json`

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/data/test_pet_supplies_clean.py -v`
Expected: FAIL because the cleaning script does not exist.

**Step 3: Write minimal implementation**

Cleaning rules:
- trim whitespace from `title`, `store`, and string details
- preserve original raw record in `metadata_json["raw_record"]` only if size remains manageable; otherwise preserve key subsets plus line/source references
- set `attributes_json["brand"]`
- set `attributes_json["species"]` when discoverable from categories or details
- set `attributes_json["subcategory_path"]`
- set `attributes_json["image_count"]` and `attributes_json["video_count"]`
- set `competitor_offers.attributes_json["price"]` as a numeric value

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/data/test_pet_supplies_clean.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add scripts/domain_imports/clean_pet_supplies.py tests/integration/data/test_pet_supplies_clean.py
git commit -m "feat(data): normalize imported pet supplies records"
```

### Task 6: Add the Pet Supplies Domain Adapter

**Files:**
- Create: `app/adapters/domains/pet_supplies.py`
- Reference: `app/adapters/demo.py`
- Reference: `app/adapters/base.py`
- Test: `tests/integration/data/test_pet_supplies_adapter.py`

**Step 1: Write the failing test**

Test behaviors:
- the adapter implements `DomainAdapter`
- `domain_name == "pet_supplies"`
- `seed(...)` returns a valid `ProductProfile`
- adapter logic reuses imported/cleaned product data instead of creating a demo fixture

**Step 2: Run test to verify it fails**

Run: `pytest tests/integration/data/test_pet_supplies_adapter.py -v`
Expected: FAIL because the adapter does not exist.

**Step 3: Write minimal implementation**

Implementation outline:
- query an existing imported pet-supplies product through the repository
- if no imported product exists, raise a clear error or create a controlled placeholder with `data_gaps`
- ingest pet-supplies knowledge documents into the provided `KnowledgeStore`
- return the selected `ProductProfile`

**Step 4: Run test to verify it passes**

Run: `pytest tests/integration/data/test_pet_supplies_adapter.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/adapters/domains/pet_supplies.py tests/integration/data/test_pet_supplies_adapter.py
git commit -m "feat(data): add pet supplies domain adapter"
```

### Task 7: Implement the Pet Supplies SQL Statistics Provider

**Files:**
- Create: `app/statistics/providers/pet_supplies.py`
- Test: `tests/unit/statistics/test_pet_supplies_provider.py`
- Reference: `app/statistics/contracts.py`
- Reference: `app/statistics/stub.py`

**Step 1: Write the failing test**

Test behaviors:
- returns a valid `StatisticsResult`
- populates deterministic metrics from SQL-backed imported records
- preserves `product_id` and `data_origin`
- returns `SUCCEEDED` when metrics exist

First-pass metrics:
- `offer_count`
- `priced_offer_count`
- `avg_price`
- `min_price`
- `max_price`
- `avg_rating`
- `total_rating_count`

**Step 2: Run test to verify it fails**

Run: `pytest tests/unit/statistics/test_pet_supplies_provider.py -v`
Expected: FAIL because the provider does not exist.

**Step 3: Write minimal implementation**

Implementation outline:
- accept a SQLAlchemy session in the provider constructor
- query imported `competitor_offers` for the current product or matching `parent_asin`
- compute decimal-safe metrics
- return `StatisticsResult(metrics=..., evidence_ids=..., data_gaps=...)`
- use `evidence_ids` that point to imported `knowledge_sources` or stable imported record identifiers

**Step 4: Run test to verify it passes**

Run: `pytest tests/unit/statistics/test_pet_supplies_provider.py -v`
Expected: PASS

**Step 5: Commit**

```bash
git add app/statistics/providers/pet_supplies.py tests/unit/statistics/test_pet_supplies_provider.py
git commit -m "feat(data): add pet supplies SQL statistics provider"
```

### Task 8: Wire the Real Provider Through the Existing Factory Safely

**Files:**
- Modify: `app/statistics/factory.py`
- Test: `tests/integration/test_statistics_injection.py`
- Test: `tests/unit/test_workflow.py`
- Reference: `docs/contract-governance.md`

**Step 1: Pause and confirm ownership**

Before editing `app/statistics/factory.py`, confirm with the Contract Maintainer or team lead that teammate-one is allowed to make this change in a business PR. If not, open a separate `contract/<topic>` PR or request the maintainer to make the wiring change.

**Step 2: Write the failing test**

Add a test showing that the real pet-supplies path selects the pet provider while demo paths still use the scaffold provider.

**Step 3: Run test to verify it fails**

Run: `pytest tests/integration/test_statistics_injection.py tests/unit/test_workflow.py -v`
Expected: FAIL because the factory still returns the scaffold provider for every case.

**Step 4: Write minimal implementation**

Implementation outline:
- keep demo behavior intact
- select `PetSuppliesStatisticsProvider(session)` for the pet-supplies real path
- avoid changing the `StatisticsProvider` protocol

**Step 5: Run test to verify it passes**

Run: `pytest tests/integration/test_statistics_injection.py tests/unit/test_workflow.py -v`
Expected: PASS

**Step 6: Commit**

```bash
git add app/statistics/factory.py tests/integration/test_statistics_injection.py tests/unit/test_workflow.py
git commit -m "feat(data): wire pet supplies statistics provider"
```

### Task 9: Run End-to-End Verification and Prepare the Shared Push

**Files:**
- Modify: `README.md` only if command usage for the new pet-supplies pipeline needs documentation
- Reference: `docs/development-guide.md`

**Step 1: Run targeted tests**

Run:
- `pytest tests/integration/data -v`
- `pytest tests/unit/statistics -v`

Expected: PASS

**Step 2: Run project verification gates**

Run:
- `pytest -q`
- `python -m compileall -q app tests scripts`
- `ruff check app tests scripts`

Expected: PASS

**Step 3: Run the pipeline manually**

Run:
- `python scripts/init_db.py`
- `python scripts/domain_imports/prefilter_pet_supplies.py`
- `python scripts/domain_imports/import_pet_supplies.py`
- `python scripts/domain_imports/clean_pet_supplies.py`

Expected:
- local SQLite database initializes
- filtered JSONL file is created
- import summary prints record counts
- cleaning summary prints normalized record counts

**Step 4: Push the branch**

Run:
- `git status`
- `git push -u origin data/pet-supplies-pipeline`

Expected: The branch is available in the shared repository for PR review.

**Step 5: Commit**

```bash
git add .
git commit -m "feat(data): complete pet supplies pipeline"
```
