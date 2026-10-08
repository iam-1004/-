# 다중 파일·오프라인 OCR·원본 자료실 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. 현재 체크아웃 `/workspace/-`가 이미 격리되어 있으므로 별도 worktree를 생성하지 않는다. 사용자에게 권장하는 실행 방식은 Native(직접 구현)다.

**Goal:** 다양한 문서와 스캔 PDF를 오프라인으로 일괄 등록하고, 원본·참고문헌·문항을 재사용·검색·삭제·복원하는 베이지 화면의 `program.exe`를 배포한다.

**Architecture:** 입력을 스냅샷으로 고정한 후 별도 작업 프로세스에서 텍스트 추출/OCR을 수행한다. UI 프로세스가 원본 자료실과 문항을 SQLite에 확정하며, 기존 Store/Editor 흐름과 ID를 유지한다. 공통 문항 파서, 형식 추출기, PDF/OCR, 원본 자료실, 마이그레이션·백업, UI를 책임별로 나눈다.

**Tech Stack:** Python 3.12 64비트, Tkinter/ttk, SQLite, pypdfium2 5.14.0, Pillow 12.3.0, Tesseract 5.5.3, PyInstaller 6.16.0.

**Spec:** `docs/superpowers/specs/2026-10-08-bulk-import-ocr-design.md` — 2026-10-08 사용자 승인.

## Global Constraints

- Windows 10/11 64비트. 실행·OCR에는 로그인·네트워크·Python 별도 설치가 필요하지 않는다.
- HWPX/TXT/DOCX/MD/PDF 및 ZIP·폴더 일괄 입력. `.hwp`와 `.doc`는 지원 대상이 아니다.
- 세트ID·문항ID·기존 자료와 이력을 보존한다. 정답·선택지 타당성·생성연도는 추정하지 않는다.
- OCR 언어 `kor+eng`, 기본 300 DPI. PDF 텍스트 40자 미만 또는 스캔 면적 60% 이상이면 OCR. 방향 점수 10 이상일 때 90/180/270도 보정. 평균 단어 점수 60 미만이면 검토 표시.
- 문서 25 MiB / PDF 500페이지 / 텍스트 2,000,000자 / ZIP 100 MiB / 묶음 풀기 250 MiB / ZIP 항목 2,000개 / 중첩 3단계 / 묶음 문서 500개 / 이미지 40,000,000픽셀 / 페이지 120초.
- SHA256 중복 방지. 원본 경로 `originals/<SHA256>.<허용된 확장자>`. 최초 입력 폴더의 파일은 삭제하지 않는다.
- DB 변경·영구 삭제·복원 전에 원본 포함 자동 백업. 버전 1/2 백업을 지원한다.
- 바탕 `#F3EBDD`, 입력 `#FFFCF6`, 글자 `#3D352B`, 선택 `#DEC9A6`.
- 최종 파일 `program.exe`, GitHub `iam-1004/-`. 다운로드한 바이트의 SHA256을 실제 대조한다.
- Tesseract Windows 설치본 SHA256 `bee9e3434bd94fd65387d9be28cd467a41f61b1275383b55b0f59a1331270ae4`. 모델 기준 커밋 `87416418657359cb625c412a48b6e1d6d41c29bd`의 `kor/eng/osd`를 사용한다. TLS·체크섬·라이선스를 유지한다.

## Review Focus

1. 기존 DB 마이그레이션 도중 디스크/쓰기 실패: 기존 ID·DB·원본·이력이 유지되어야 한다 — Task 2.
2. OCR 취소/시간 초과/작업 프로세스 종료: 이전 성공 문서는 유지하고 현재 작업·자식 OCR·임시 파일을 정리해야 한다 — Tasks 3, 4.
3. 텍스트 머리말과 큰 스캔 이미지가 섞인 PDF·회전된 한국어: 이미지 본문을 놓치지 않고 실제 OCR을 사용해야 한다 — Task 3.
4. ZIP 안의 DOCX/HWPX·동일 원본의 다른 이름·중첩 경로·XML 문자 인코딩: 문서 내부 ZIP 오인과 경로 탈출, 중복 등록을 막아야 한다 — Tasks 1, 4.
5. 같은 원본에서 만든 여러 세트 중 하나의 삭제/OCR 재실행: 다른 세트와 사람이 수정한 해설을 보존해야 한다 — Tasks 2, 5.

---

## Task 1: 공통 후보·참고문헌 파서와 문서 스냅샷

**Files:** Create `leet_manager/document_types.py`, `leet_manager/text_parser.py`, `leet_manager/documents.py`, `tests/test_documents.py`, `tests/test_references.py`, `tests/fixtures.py`; modify `leet_manager/hwpx.py`.

**Interfaces:**
- `DocumentInput(stage_path: Path, original_name: str, extension: str, digest: str, container: str='')`: 불변 입력 스냅샷. 확장자는 점을 포함한 소문자다.
- `ExtractedDocument(document: DocumentInput, text: str, pages: list[dict], warnings: list[str], review_needed: bool=False)`; 페이지 정보 키는 `page`, `text`, `method`, `confidence`, `warnings`다. DOCX/HWPX의 내부 ZIP은 기존 50 MiB/2,000항목 제한도 적용한다.
- `iter_documents(paths: Sequence[Path], stage_dir: Path, report: Callable[[dict], None]) -> Iterator[DocumentInput]`: 파일·폴더·ZIP을 스냅샷으로 만들며 제한/오류를 보고한다. 원본 경로는 쓰지 않는다.
- `extract_document(doc: DocumentInput) -> ExtractedDocument`: HWPX/TXT/MD/DOCX 공통 반환형. PDF는 Task 3의 추출기를 호출한다.
- `extract_references(text: str) -> str`, `propose_sections(text: str) -> dict`: 실제 문헌 항목과 기존 형식의 세트 후보. `hwpx`의 기존 공개 함수는 호환 래퍼로 유지한다.

- [ ] **Write failing tests:** `test_references_before_explanations`, `test_markdown_and_bracket_references`, `test_numbered_bibliography_is_not_question`, `test_reference_word_in_sentence_is_not_heading`에서 실제 참고문헌이 `source`에 남고 정답은 3/1/4, `year is None`, 다른 문항이 문헌에 들어가지 않음을 확인한다.

```python
def test_reference_without_explanation_section(self):
    c = propose_sections('제시문\n[참고문헌]\n저서 1998년')
    self.assertEqual(c['source'], '저서 1998년')
    self.assertIsNone(c['year'])
```
- [ ] **Write failing tests:** UTF-8/BOM/UTF-16/CP949 TXT, MD, DOCX 문단·표·헤더·각주 순서, 대문자 확장자, ZIP 내부 DOCX/HWPX, 중첩 3단계 및 모든 크기 경계, UTF-16 XML DTD·중복/절대/탈출/심볼릭 링크 경로 거부를 실파일로 검증한다. 스냅샷 후 입력 파일을 바꿔도 스냅샷의 SHA256과 텍스트는 처음 바이트를 유지한다.
- [ ] **Verify RED:** `python -m unittest discover -s tests -p 'test_references.py' -v`, `python -m unittest discover -s tests -p 'test_documents.py' -v` — 새 함수/행동 미구현으로 실패. OCR 의존성 누락 같은 다른 오류로 대체하지 않는다.
- [ ] **Implement:** 위 인터페이스와 제한을 구현한다. XML 문서 순서를 보존하고 ZIP 이름은 표시용 메타데이터로만 사용한다. 지원하지 않는 파일은 보고 후 계속한다. 텍스트·정답·원문을 임의로 잘라 완료 처리하지 않는다.
- [ ] **Verify GREEN:** 위 두 명령과 `python -m unittest discover -s tests -p 'test_hwpx.py' -v` — 모두 통과. 파서 실행만으로 DB에 등록되지 않는 기존 보장을 유지한다.
- [ ] **Commit:** `feat: add multi-format extraction and reference parsing`.

## Task 2: 원본 자료실·버전 2 DB·호환 백업

**Files:** Create `leet_manager/schema.py`, `leet_manager/migration.py`, `leet_manager/catalog.py`, `tests/test_catalog.py`, `tests/test_migration.py`, `tests/test_backup_v2.py`; modify `leet_manager/store.py`, `leet_manager/models.py`, `leet_manager/backup.py`, `leet_manager/paths.py`, `leet_manager/import_service.py`.

**Interfaces:**
- `initialize_store(store) -> Path | None`: 새 DB는 버전 2 생성. 버전 1은 검증·자동 백업 후 트랜잭션 마이그레이션. 기존 DB 손상/미지원 버전이면 중단한다. 반환값은 마이그레이션 전 백업 경로다.
- `Store.sources: SourceCatalog`; `SourceCatalog.register(doc: ExtractedDocument) -> tuple[str, bool]`: 문서ID `F-...`와 신규 여부. `find_hash(digest) -> dict | None`, `get(fid) -> dict`, `list(include_trash=False) -> list[dict]`, `proposal(fid) -> dict`, `update_text(fid, extracted, expected_revision) -> None`.
- `sources` 테이블: `id TEXT PRIMARY KEY`, `file_hash TEXT NOT NULL UNIQUE`, `original_name TEXT NOT NULL`, `format TEXT NOT NULL`, `original_path TEXT NOT NULL`, `raw_text TEXT NOT NULL`, `imported_at TEXT NOT NULL`, `pages TEXT NOT NULL`, `warnings TEXT NOT NULL`, `state TEXT NOT NULL`, `revision INTEGER NOT NULL`. `pages/warnings`는 검증된 JSON, `state`는 `active/trash`다.
- 기존 세트 JSON에 `source_id=''`, `trashed=False`를 추가한다. `Store.save_set`은 이전 문서 연결과 원본을 유지하고 존재하는 문서 연결만 허용한다. 기존 문항 필드는 바꾸지 않는다.
- 기존 `backup(store, destination)` / `restore(store, source)` / `validate_directory(directory)`는 공개 인터페이스를 유지하되 실제 DB 버전별 스키마·필드·해시·문서 연결을 검사한다. 버전 1 필수 필드에 새 필드를 강요하지 않는다.

- [ ] **Write failing tests:** 등록 후 Store 재연결에서 동일한 F-ID/텍스트/원본 바이트가 남음; 해시 중복은 `(same_fid, False)`; 같은 원본에서 여러 세트 생성 시 S/Q-ID는 각각 유지; 미확정 원본도 백업됨; 원본 기록 실패 시 DB/파일 잔재가 없음.

```python
def test_registry_survives_restart(self):
    fid, created = self.store.sources.register(self.extracted_txt)
    self.assertTrue(created)
    self.assertTrue(fid.startswith('F-'))
    directory = self.store.data_dir
    self.store.close()
    self.store = Store(directory)
    self.assertEqual(self.store.sources.get(fid)['raw_text'], self.extracted_txt.text)
    self.assertEqual(self.store.sources.register(self.extracted_txt), (fid, False))
```
- [ ] **Write failing tests:** 실제 버전 1 DB fixture의 S/Q-ID, 날짜, 상태·사용/기출/수정 이력과 원본이 마이그레이션/복원 후 동일함. 빈 참고문헌만 원문에서 보완하고 새 수정 이력이 남음. 자동 백업·DB 업데이트 실패를 주입하면 원래 DB/파일 바이트가 유지됨. 버전 2 원본 경로·해시·JSON·다른 문서 연결의 손상 백업을 거부함.
- [ ] **Verify RED:** 새 세 파일의 unittest discover를 각각 실행해 기능 미구현 실패를 확인한다.
- [ ] **Implement:** 원본은 임시 기록·fsync·원자적 교체 후 DB에 확정하고 실패 시 되돌린다. `Store.__init__`는 연결 후 `initialize_store`를 호출하고 그 뒤 `SourceCatalog`를 구성한다. 버전 1 백업 경로에서는 아직 생성하지 않은 catalog를 사용하지 않는다. 기존 HWPX 확인 저장 API의 중복 거부와 저장 실패 롤백을 유지한다.
- [ ] **Verify GREEN:** 새 세 파일, 기존 `test_backup.py`, `test_review_regressions.py`, `test_store.py`, `test_hwpx.py`가 통과한다. 복원 파일 교체 실패 후 DB 연결을 다시 사용할 수 있다.
- [ ] **Commit:** `feat: preserve source catalog and migrate backups safely`.

## Task 3: 실제 PDF 추출·오프라인 OCR·배포 자산

**Files:** Create `leet_manager/pdf_ocr.py`, `leet_manager/ocr_runtime.py`, `tools/prepare_ocr_assets.py`, `requirements-runtime.txt`, `tests/test_pdf_ocr.py`, `tests/test_ocr_runtime.py`, `tests/fixtures/scan_ko_en.pdf`, `tests/fixtures/scan_rotated.pdf`, `tests/fixtures/mixed.pdf`; modify `requirements-build.txt`, `.gitignore`, Task 1 `documents.py`.

**Interfaces:**
- `OcrRuntime(executable: Path, tessdata: Path)`; `locate_ocr_runtime() -> OcrRuntime`: frozen 자산/소스 실행용 준비 자산에서만 찾으며 다운로드하지 않는다. 없는 엔진·모델은 구체적인 오류로 알린다.
- `recognize_image(image, runtime: OcrRuntime, cancel=None) -> dict`: UTF-8 `text`, `confidence`, `rotation`, `warnings`. subprocess는 인자 목록·타임아웃·콘솔 숨김으로 실행한다.
- `extract_pdf(doc: DocumentInput, force_ocr=False, emit=None, cancel=None) -> ExtractedDocument`; `render_pdf_page(path: Path, page: int, max_pixels=40_000_000)`: 0부터 시작하는 미리 보기 페이지 번호. 추출 메타데이터의 `page`는 사용자에게 표시하는 1부터 시작하는 번호다.
- `prepare_ocr_assets.py --output <directory>`는 고정 배포본·모델을 TLS/공식 체크섬·Git blob과 대조하고 런타임 DLL·모델·라이선스·SHA256 manifest를 준비한다. 실행 중 네트워크 다운로드는 없다.

- [ ] **Write failing tests:** 실 PDF의 직접 텍스트 페이지는 `method='text'`; 스캔 및 큰 이미지/짧은 머리말 페이지는 `method='ocr'`; 한 파일에서 두 방식이 순서대로 유지됨. 40자·60%·40,000,000픽셀·500페이지 경계를 검증한다. 강제 OCR은 모든 페이지에서 OCR을 사용한다.
- [ ] **Write failing tests:** 실제 인식기로 한국어·영어 스캔에서 `참고문헌`, `LEET`가 추출되고 원문에는 1쪽/2쪽 구분이 남음. 회전된 스캔의 방향 보정과 낮은 점수/빈 결과 경고, 암호화/손상 PDF·자산 누락·시간 초과·취소를 검증한다. OCR 성공 시험은 엔진을 모의하거나 skip하지 않는다.

```python
def test_actual_offline_korean_scan(self):
    result = extract_pdf(self.scan_ko_en_document)
    self.assertIn('참고문헌', result.text)
    self.assertIn('LEET', result.text)
    self.assertEqual(result.pages[0]['method'], 'ocr')
    self.assertEqual(result.pages[0]['page'], 1)
    self.assertTrue(result.pages[0]['text'].strip())
```

스캔 fixture는 위 문구를 포함하는 실제 이미지 PDF이며 텍스트 레이어를 넣지 않는다. 한국어 글리프가 존재하는 라이선스 허용 폰트로 생성하고, PDF 텍스트 추출이 비어 있음을 먼저 검증한다. `mixed.pdf`는 텍스트 1쪽과 같은 스캔 2쪽, `scan_rotated.pdf`는 90도 회전한 스캔을 담는다.
- [ ] **Verify RED:** `python -m unittest discover -s tests -p 'test_pdf_ocr.py' -v`와 `test_ocr_runtime.py` — 기능 미구현 실패를 확인한다.
- [ ] **Implement:** 승인된 pypdfium2/Pillow/Tesseract 버전을 설치·검증하고 실제 자산을 준비한다. 한 페이지씩 렌더링/해제한다. 시간 초과·취소 때 시작한 OCR 자식 프로세스를 종료하고 임시 파일을 지운다. OCR 원문과 점수만 반환하며 정답·연도는 생성하지 않는다.
- [ ] **Verify GREEN:** 실제 Linux OCR 테스트와 Windows Python/Wine의 PDF·한국어 OCR을 모두 실행해 통과한다. 소켓 연결이 차단된 테스트에서도 보관된 자산만으로 인식한다.
- [ ] **Commit:** `feat: extract scanned PDFs with bundled offline OCR`.

## Task 4: 일괄 입력 작업·결과 보고

**Files:** Create `leet_manager/import_worker.py`, `leet_manager/batch_import.py`, `tests/test_batch_import.py`; modify `main.py`, `leet_manager/import_service.py`.

**Interfaces:**
- `run_import_worker(paths: list[str], stage_dir: str, known_hashes: dict[str, str], queue, cancel) -> None`: `progress/page_started/document/existing/error/done` 이벤트를 내보낸다. 이벤트는 기본 자료형만 사용하며 document에는 검증된 스냅샷 위치와 Task 1 반환형의 필드를 전달한다. SQLite/Tk 객체는 전달하지 않는다.
- `ImportController(store, on_event)`: `start(paths: Sequence[Path])`, `poll()`, `cancel()`, `close()`, `running`을 제공한다. `poll`은 UI 스레드에서 document를 SourceCatalog에 등록하고 성공 이벤트를 보낸다. 기존 해시이면 추출/OCR을 건너뛴다.
- `export_import_report(rows: list[dict], destination: Path) -> int`: UTF-8 BOM CSV, 기존 관리 경로 보호·수식 방어·원자적 저장 적용.

- [ ] **Write failing tests:** TXT/DOCX/HWPX/PDF/ZIP 혼합 입력의 신규·기존·실패 수, 이름이 다른 동일 파일과 반복 ZIP의 중복 0개, 취소 전 성공 문서 보존, 실패 뒤 다음 문서 처리, 검토 필요 PDF 원본 보관을 실제 작업 프로세스로 확인한다.

```python
def test_repeated_archive_does_not_duplicate_sources(self):
    self.run_batch_and_poll_until_done([self.mixed_zip])
    original = {s['id'] for s in self.store.sources.list()}
    self.run_batch_and_poll_until_done([self.mixed_zip])
    self.assertEqual({s['id'] for s in self.store.sources.list()}, original)
    self.assertEqual(self.second_report['registered'], 0)
```

`run_batch_and_poll_until_done`는 테스트 보조 함수이며 실제 ImportController를 poll한다. 보고 집계 키는 `registered/existing/failed/review_needed`다. 제품 클래스에 테스트 전용 메서드를 넣지 않는다.
- [ ] **Write failing tests:** 페이지 120초 초과/작업 프로세스 비정상 종료 시 UI가 완료 이벤트를 받고 중단된 작업이 성공으로 표시되지 않음; 작업/OCR 자식과 임시 폴더 정리; 원본 스냅샷 변조나 해시 불일치 거부. 보고 CSV의 수식 입력은 실행되지 않는다.
- [ ] **Verify RED:** `python -m unittest discover -s tests -p 'test_batch_import.py' -v`.
- [ ] **Implement:** spawn 프로세스와 큐, 페이지 감시, 취소, 관리하는 자식 프로세스만 종료하는 처리를 추가한다. `main.py`에서 Tk 창 생성 전 `multiprocessing.freeze_support()`를 호출한다. 성공 DB 기록 이후에만 등록 완료를 표시한다. 임시 파일 위치는 부모가 만든 작업 폴더로 제한한다.
- [ ] **Verify GREEN:** 위 테스트와 기존 import/UI 회귀 테스트 통과. GUI poll 사이에는 대량 파일 추출을 실행하지 않는다.
- [ ] **Commit:** `feat: batch import documents with progress and cancellation`.

## Task 5: 휴지통·검색·일괄 수정·입력 누락 점검

**Files:** Create `leet_manager/trash.py`, `leet_manager/quality.py`, `tests/test_trash.py`, `tests/test_search_bulk.py`; modify `catalog.py`, `store.py`, `export.py`.

**Interfaces:**
- `SourceCatalog.set_state(fid, state)`; `Store.set_trashed(sid, trashed)`; `purge_source(store, fid) -> Path`, `purge_set(store, sid) -> Path`: 반환값은 삭제 직전 자동 백업. 휴지통 대상만 영구 삭제한다.
- `Store.search(query='', filters=None)`의 필터 추가: `year_from/year_to`는 int 또는 None, `include_trash` bool, `sort`는 `updated/title/year`, `descending` bool, `needs_review` bool. 기존 `year='미확인'`과 필터를 유지한다. 미확인 연도는 양방향 연도 정렬 모두 마지막에 둔다.
- `Store.bulk_update(sids: Sequence[str], changes: dict, expected_revisions: dict[str, int]) -> None`: `year/tags/review_status` 중 선택된 필드만 변경하며 전체 검증 후 한 트랜잭션으로 기록한다.
- `review_issues(set_data: dict, source: dict | None=None) -> list[dict]`: `field/number/message`로 누락·OCR 경고를 반환한다. 기존 완료 검증과 별도로 초안의 보완점도 표시한다.

- [ ] **Write failing tests:** 원본/세트 휴지통·복원 후 폐기/사용/기출 상태가 불변; 공유 원본에서 한 세트 삭제 후 다른 세트와 원본 유지; OCR 원문 갱신 후 수정한 세트 해설 불변; 백업·DB·파일 교체 실패 시 삭제 롤백; 외부 입력 파일 보존.
- [ ] **Write failing tests:** 2023/2024/미확인 자료에서 범위 2023~2024는 앞 두 개, 미확인 검색은 마지막 한 개; 세트·문항·CSV가 같은 조건 사용; 일괄 생성연도/태그 변경의 Q-ID와 이력 보존; 한 세트의 충돌·완료 검증 실패 시 모든 선택 자료가 변경되지 않음; 누락 점검이 참고문헌·정답·선택지·목표와 OCR 경고를 반환함.

```python
def test_range_excludes_unknown_year(self):
    result = self.store.search(filters={'year_from': 2023, 'year_to': 2024})
    self.assertEqual({s['year'] for s in result}, {2023, 2024})
    self.assertNotIn(None, [s['year'] for s in result])
    unknown = self.store.search(filters={'year': '미확인'})
    self.assertEqual([s['id'] for s in unknown], [self.unknown_sid])
```
- [ ] **Verify RED:** `test_trash.py`, `test_search_bulk.py` 각각 unittest discover 실행.
- [ ] **Implement:** 자료 연결 관계를 검사하고 백업 후 DB/파일 변경을 되돌릴 수 있게 수행한다. 단일 저장과 일괄 저장에 공통 트랜잭션 내부 기록 함수를 사용해 중첩 context의 중간 commit을 피한다. 문헌 연도를 생성연도로 추정하지 않는다.
- [ ] **Verify GREEN:** 새 테스트, 기존 검색·정답 타당성·상태·수정 충돌·CSV 보호 경로 테스트 통과.
- [ ] **Commit:** `feat: add recoverable deletion and year-based batch management`.

## Task 6: 베이지 UI·자료실·PDF 원본 비교

**Files:** Create `leet_manager/theme.py`, `leet_manager/library_window.py`, `leet_manager/batch_dialog.py`, `leet_manager/pdf_viewer.py`, `tests/test_batch_ui.py`, `tests/test_theme_ui.py`; modify `ui.py`, `editor.py`, `import_dialog.py`, `widgets.py`.

**Interfaces:** `apply_theme(root)`, `LibraryWindow(parent, store, on_saved)`, `BatchDialog(parent, store, paths, on_saved)`, `PdfViewer(parent, path, text, pages)`. 기존 `open_import`와 `Editor`는 기존 단일 입력 테스트를 유지하며 SourceCatalog의 후보·세트 연결도 받는다.

- [ ] **Write failing GUI tests:** 여러 파일·폴더 선택→등록 결과→자료실→문항 편집→재실행에서 파일을 다시 선택하지 않음; 참고문헌 저장 유지; 휴지통/복원/영구 삭제 개수와 자동 백업 안내; 연도 범위·다중 선택 일괄 변경·검토 필요 이동·보고 CSV 동작.
- [ ] **Write failing GUI tests:** PDF 비교창에서 페이지 이동마다 원본과 해당 페이지 텍스트를 표시; 전체 OCR 재실행이 기존 해설을 바꾸지 않음; 열린 편집창/미저장 상태의 삭제·복원·일괄 변경이 조용히 입력을 잃게 하지 않음; 모든 Tk Text/Canvas/Toplevel과 ttk 목록/선택/포커스가 승인 색상을 사용함.

```python
def test_beige_editor_preserves_reference(self):
    editor = Editor(self.root, self.store, self.store.get_set(self.sid))
    box = editor.set_form.widgets['source']
    self.assertEqual(box.cget('background'), '#FFFCF6')
    editor.set_form.set('source', '저서 1998년')
    editor.save(close=False)
    self.assertEqual(self.store.get_set(self.sid)['source'], '저서 1998년')
```
- [ ] **Verify RED:** Xvfb 또는 Windows 화면에서 새 GUI 테스트를 실행해 실제 창의 행동 실패를 확인한다. 화면 없음으로 skip된 결과를 통과로 세지 않는다.
- [ ] **Implement:** 작업 큐를 `after`로 갱신한다. 주요 도구 모음과 자료관리 메뉴, 등록 파일/휴지통, 검토 점검, 연도 범위, 선택 개수/변경 필드, PDF 비교를 연결한다. 스캔 인식 오류를 사용자가 수정하고 초안 저장할 수 있게 유지한다.
- [ ] **Verify GREEN:** 기존 `test_ui.py`와 새 GUI 테스트 실행, 스크린샷 육안 검토. 입력·Undo·스크롤·원본 열기·dirty close 동작 유지.
- [ ] **Commit:** `feat: add beige document library and OCR review screens`.

## Task 7: EXE·오프라인 검증·GitHub 다운로드

**Files:** Create `tools/check_frozen.py`; modify `build_windows.ps1`, `README.md`, `docs/PROGRESS.md`, `program.exe`, `program.exe.sha256`.

- [ ] **Prepare:** SHA256 manifest로 OCR 실행 파일·필요 DLL·kor/eng/osd·라이선스를 검증한다. 빌드 스크립트에 runtime 요구사항/검증/자산 준비와 PyInstaller 포함 경로를 기록한다. 준비되지 않은 자산은 빌드를 실패시킨다.
- [ ] **Verify suite:** Linux GUI 포함 `python -m unittest discover -s tests -v`, Windows Python/Wine에서 같은 명령을 실행한다. 기존 33개를 포함해 실제 실행·통과·skip·실패 수를 구별해 기록한다.
- [ ] **Build:** Windows CPython 3.12/PyInstaller 6.16.0으로 `program.exe`를 새로 빌드하고 exit 0 및 PE32+ x64를 확인한다. OCR 자산을 제외해 크기만 줄이지 않는다.
- [ ] **Verify frozen:** 네트워크가 없는 환경에서 한국어·영어 스캔 PDF 실제 OCR, TXT/DOCX/MD/HWPX/ZIP 일괄 등록, 원본 비교, 참고문헌, 정상 종료/재실행, 동일 파일 중복 방지, 연도 범위, 휴지통·복원·백업을 실행한다. frozen spawn이 새 메인 창을 반복 생성하지 않음과 취소 후 OCR 자식 종료를 확인한다.
- [ ] **Review:** 최신 변경을 독립 검토하고 기존 자료 손실·OCR 미포함·파일 누락·취소/복원 실패를 해결한다. Windows PC 실기 접근이 없으면 Wine과 실기를 구별해 보고한다.
- [ ] **Publish:** 기존 GitHub 인증으로 `iam-1004/-`에 소스·실행 파일·SHA256을 저장한다. 100 MiB를 넘으면 가능한 Release 업로드 방법을 먼저 검증하며, 기존 실행 파일만 바뀐 것처럼 보고하지 않는다.
- [ ] **Verify download:** GitHub 실제 다운로드 응답 200, 다운로드 파일 크기, SHA256을 로컬 빌드와 비교한다. README의 다운로드 링크와 기능 설명을 새 버전으로 맞춘다.
- [ ] **Commit:** `release: ship offline OCR question manager for Windows`.

## 자체 검토와 사용자 검토

설계의 완료 조건 1~10을 Tasks 1~7에 대응시켰다. 데이터 모델과 원본/세트 API를 Tasks 1~2에서 정의했고 OCR/worker/UI는 같은 반환형을 사용한다. 기존 33개 테스트를 유지하면서 스캔 실제 인식, 버전 1 호환, 반복 ZIP, 취소, 공유 원본 삭제, 기록 실패를 별도 검증한다. 실행 순서는 1→2→3→4→5→6→7이다.

문서 상태: 사용자 검토용 구현 계획. 설계는 승인되었으나 이 계획의 검토와 실행 방식 선택 전에는 제품 코드 변경을 시작하지 않는다. 직접 구현은 제가 순서대로 수행하고 마지막에 독립 검토한다. 분담 구현은 작업별 별도 구현/검토 에이전트를 사용한다.
