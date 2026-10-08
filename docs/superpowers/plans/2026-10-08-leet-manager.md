# LEET 언어이해 문항관리 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 첨부 설계안에 따라 인터넷 없이 사용하는 개인용 Windows 문항관리 프로그램을 구현한다.

**Architecture:** Python 3.12 이상과 Tkinter/ttk로 데스크톱 화면을 구성하고 SQLite로 자료를 저장한다. 데이터베이스와 원본은 `%LOCALAPPDATA%\LEETQuestionManager`에 보관하며 실행 파일과 분리한다. UI, 저장소, HWPX 분석, 백업을 독립 모듈로 나눈다.

**Tech Stack:** Python, Tkinter/ttk, SQLite, zipfile, ElementTree, unittest. Windows 배포는 PyInstaller 폴더형 패키지로 구성한다. 사용 시 Python 설치와 인터넷 연결은 필요하지 않도록 한다.

**Spec:** `docs/specs/LEET_언어이해_문항관리_설계안.md` 및 사용자 추가 요구사항인 문항ID 입력란/표시란.

## Global Constraints

- 개인용 오프라인 구조. 한 사람, 한 컴퓨터 사용. 공유 데이터베이스 동시 수정은 지원하지 않는다.
- GitHub 게시와 원격 push를 하지 않는다.
- 세트에는 제시문 하나와 문항 세 개가 속한다. 초안 저장은 허용하며 검토 완료 전환 시 완전성을 확인한다.
- 세트 ID와 문항 ID는 자동으로 부여하고 수정하지 않는다. 사용자 요구의 문항ID란은 읽기 전용으로 표시하며 검색과 CSV에도 포함한다.
- 핵심 키워드는 세트 공통과 문항 개별을 구별한다.
- 선택지의 정답 여부와 진술의 타당성은 독립 필드로 관리한다.
- 생성 연도·사용·기출·폐기 상태 등 확인되지 않은 정보는 미확인으로 표시한다. 사용 이력 부재는 미사용의 증거가 아니다.
- 자료를 임의로 채우지 않는다. 실제 HWPX는 현재 제공되지 않았으므로 실자료 가져오기 검증은 별도로 남긴다.
- 첫 실행은 빈 데이터베이스로 시작한다. 테스트용 자료는 사용자 데이터 폴더에 넣지 않는다.
- 기존 체크아웃을 사용하고 worktree를 새로 만들지 않는다.

## Review Focus

- 부정형 발문: 타당하지 않은 선택지를 정답으로 저장해도 정상 동작해야 한다.
- 손상되거나 위험한 HWPX/ZIP: 경로 탈출, 과도한 압축 해제, 잘못된 XML을 거부하고 기존 자료를 유지해야 한다.
- 가져오기 중 취소와 중복: 확인 없이 등록하지 않고 동일 해시를 감지해야 한다.
- 복원 실패: 현재 자료를 자동 백업하고 잘못된 구조·DB·원본 해시를 거부해야 한다.
- 한글 경로, 빈 값, 장문: 저장·검색·내보내기·재실행에서 자료가 보존돼야 한다.

---

### Task 1: 데이터 모델과 저장소

**Files:** `leet_manager/models.py`, `leet_manager/store.py`, `tests/test_store.py`.

**Interfaces:**
- `Store(data_dir: Path)`가 데이터 폴더와 DB를 초기화한다.
- `save_set(data: dict, questions: list[dict], set_id: str | None = None) -> str`가 검증 후 트랜잭션으로 저장한다.
- `get_set(set_id: str) -> dict`, `search(query: str, filters: dict) -> list[dict]`가 조회한다.
- `add_usage(set_id: str, question_id: str | None, data: dict)`, `history(set_id: str) -> list[dict]`가 이력을 관리한다.

**모델 결정:**
- 세트와 문항은 UUID 기반 고정 ID, 문항에는 세트 내 번호 1~3를 별도 저장한다.
- 세트: 설계안의 모든 관리 필드, 공통 키워드, 보조 과목, 검색 태그, 사용/기출/폐기 3상태(미확인/예/아니요), 폐기일·사유.
- 문항: 설계안의 모든 필드, 개별 키워드, 보기, 1~5 정답 번호, 선택지 5개. 각 선택지는 본문·해설·타당성(미확인/타당/부적절)을 저장하고 정답 여부는 문항 정답 번호에서 도출한다.
- 사용 이력과 기출 기록은 별도 테이블에서 세트/개별 문항에 연결한다. 수정 이력은 시각과 변경 전후 값을 보존한다.
- 빈 생성 연도와 실제 정답률은 NULL로 저장한다. 정답률 입력 범위는 0~100이다.
- 세부 과목은 기본 분류를 초기화하고 추가를 허용한다. 사용 중인 과목 삭제는 거부한다.

- [x] **Step 1:** 재실행 후 한글/장문/고정 ID 유지, 공통·개별 키워드 분리, 부정형 정답, 미확인 상태, 사용 이력 누적, 폐기 제외/포함, 문항별 분류·ID 검색, 과목 삭제 제한, 검토 완료 유효성, 수정 이력 테스트를 작성한다.
- [x] **Step 2:** `python -m unittest discover -s tests -v`로 아직 저장소가 없어 실패함을 확인한다.
- [x] **Step 3:** 위 인터페이스와 모델을 구현한다. SQLite 외래키, 파라미터 바인딩, 저장 트랜잭션을 사용한다. 초안도 정답 범위·번호 중복·잘못된 정답률은 거부한다.
- [x] **Step 4:** 동일 명령으로 저장소 테스트가 통과하는지 확인한다.

### Task 2: 확인형 HWPX 가져오기

**Files:** `leet_manager/hwpx.py`, `leet_manager/import_service.py`, `tests/test_hwpx.py`.

**Interfaces:**
- `extract_text(path: Path) -> str`는 Contents/section*.xml의 문단을 문서 순서로 추출한다.
- `propose_sections(text: str) -> dict`는 제시문·문항·보기·해설 배정 후보와 경고를 반환한다.
- `import_confirmed(store: Store, source: Path, data: dict, questions: list[dict]) -> str`는 확인한 자료와 원본 사본을 등록한다.

- [x] **Step 1:** 테스트용 HWPX를 임시 폴더에서 생성하고 문항 경계, ①~⑤, 보기, 해설, 키워드, 평가 목표, 정답, 제시문 근거, 오답 근거 원문, 참고문헌과 [12면] 보존을 검사한다. 손상 XML/ZIP, 비정상 크기, 취소·중복·복사 실패 테스트도 작성한다.
- [x] **Step 2:** 테스트가 기능 부재로 실패함을 확인한다.
- [x] **Step 3:** 해시 기반 원본 보관, ZIP 크기 제한, XML 안전성 검사, 자연 순서 section 분석을 구현한다. 불확실한 경계는 경고로 표시하고 텍스트를 버리지 않는다. 자동 후보는 초안이며 사용자 확인 전 저장하지 않는다.
- [x] **Step 4:** 전체 테스트 통과를 확인한다. 생성 연도와 사용 상태를 분석기가 추측하지 않는지도 검사한다.

### Task 3: 백업·복원·CSV

**Files:** `leet_manager/backup.py`, `leet_manager/export.py`, `tests/test_backup.py`, `tests/test_export.py`.

**Interfaces:**
- `backup(store: Store, destination: Path) -> Path`는 SQLite backup API를 이용해 DB와 원본을 ZIP으로 만든다.
- `restore(store: Store, source: Path) -> Path`는 복원 전 자동 백업 경로를 반환한다.
- `export_csv(store: Store, destination: Path, filters: dict) -> int`는 출력 문항 수를 반환한다.

- [x] **Step 1:** 복원 후 문항·이력·원본 SHA256 일치, 잘못된 DB/스키마/해시/ZIP 경로 거부, 복원 실패 시 현재 자료 유지, 복원 전 자동 백업 테스트를 작성한다. 한 문항 한 행, 문항ID/세트ID, 한글 BOM, 모든 해설·키워드 구분, 스프레드시트 수식 입력 방어를 검사한다.
- [x] **Step 2:** 테스트가 기능 부재로 실패함을 확인한다.
- [x] **Step 3:** 임시 영역 검증 후 자료 교체와 실패 시 롤백을 구현한다. 백업 구조에는 버전 manifest, DB, originals를 포함한다. CSV는 UTF-8 BOM과 표준 csv 모듈을 사용한다.
- [x] **Step 4:** 전체 테스트를 실행한다.

### Task 4: Windows 데스크톱 화면

**Files:** `leet_manager/ui.py`, `leet_manager/editor.py`, `leet_manager/import_dialog.py`, `main.py`, `tests/test_ui.py`.

**Interfaces:** `App(root: Tk, store: Store)`가 목록, 편집, 가져오기, 자료 관리 화면을 제공한다. `main.py`는 Windows 사용자 데이터 폴더를 결정하고 앱을 시작한다.

**화면 결정:**
- 목록: 세트/문항 전환, 검색, 생성 연도·영역·과목·문항 유형·사용·기출·폐기·검토 필터. 문항 목록은 문항ID와 세트 내 번호를 모두 표시한다.
- 상세/등록: 세트 정보·제시문, 문항 1~3, 관리 이력 탭. 긴 텍스트는 스크롤 가능한 편집기로 구성한다. 문항ID는 읽기 전용란으로 표시한다.
- 각 문항은 5개 선택지의 본문·타당성·해설과 별도 정답 선택란을 제공한다. 공통 키워드와 개별 키워드를 구분해 표기한다.
- 가져오기: 추출 원문, 자동 분리 후보, 원문 선택 텍스트를 입력란에 배정하는 기능, 최종 확인 저장. 취소 시 변경하지 않는다.
- 자료 관리: 원본 열기, 사용·기출 기록 추가, 폐기/복구 표시, 변경 이력 조회, 과목 추가/삭제, CSV·ZIP 백업·복원.
- 사용자 데이터는 프로그램 삭제와 분리한다. 미저장 수정 시 닫기/다른 자료 이동 전에 경고한다.

- [x] **Step 1:** UI 통합 테스트로 빈 시작, 직접 입력 저장, 재조회, 정답/타당성 분리, 검색 필터, 원문 배정, 취소, 백업·복원 연결을 검사한다.
- [x] **Step 2:** 화면 부재로 테스트가 실패함을 확인한다. GUI 실행 가능한 환경이 없다면 디스플레이 테스트 제한을 명시한다.
- [x] **Step 3:** 화면과 데이터 서비스 연결을 구현한다. 입력 오류는 한글 안내로 표시하고 실패 시 입력을 보존한다. 원본 열기는 Windows의 파일 연결을 사용한다.
- [x] **Step 4:** 전체 테스트와 가능한 GUI 통합 검증을 수행한다. Windows 전용 파일 연결은 Windows에서 별도 검증한다.

### Task 5: 배포와 사용 설명서

**Files:** `README.md`, `build_windows.ps1`, `requirements-build.txt`, `.gitignore`.

- [x] **Step 1:** 설명서에 Python 소스 실행, HWPX 가져오기 확인 절차, 문항ID, 미확인 상태, 원본 연결, 데이터 위치, 백업/복원, 제한과 검증 결과를 작성한다.
- [x] **Step 2:** Windows 전용 빌드 스크립트를 작성한다. 고정 버전 PyInstaller를 사용해 콘솔 없는 폴더형 앱과 ZIP을 생성하고 사용자 데이터를 포함하지 않는다.
- [x] **Step 3:** 전체 테스트를 실행하고 소스 배포 ZIP을 만든다. 테스트용 자료와 로컬 사용자 DB는 배포에서 제외한다.
- [ ] **Step 4:** Windows 빌드 도구/실행 환경이 있으면 EXE를 생성해 빈 시작·저장·재실행·가져오기·복원을 검증한다. 현재 환경은 Linux이며 Wine과 GUI 디스플레이 도구가 확인되지 않았다. Windows 빌드가 불가능하면 소스/빌드 스크립트 제공과 검증하지 못한 항목을 정확히 보고한다.

## 구현 방식 및 검증 범위

현재 세션에서 직접 구현하는 방식을 기본 제안으로 한다. GitHub 게시 없이 로컬 파일만 작성한다. 구현 완료 조건은 저장소·가져오기·백업 테스트와 실행 가능한 환경에서의 UI 검증이다. 실제 첨부 HWPX와 Windows EXE 검증은 해당 파일/환경 확보 여부에 따라 별도 결과로 기록한다.

## 실행 결과

소스·데스크톱 화면·Windows 빌드 스크립트를 구현했다. 33개 테스트를 Linux 가상 화면에서 실행해 모두 통과했다. Windows EXE 생성/실행 및 실제 HWPX 검증은 환경/파일 미확보로 미완료이며 README에 명시했다. 독립 검토의 Important 3개는 실패 재현 테스트를 작성한 뒤 수정했고 복원 실패 롤백도 검증했다. GitHub 게시 없이 로컬 산출물로 제공한다.

후속 완료: Windows용 Python과 Wine 호환 환경을 임시로 준비해 단일 EXE 생성, 33개 테스트 및 frozen GUI 저장/재실행을 검증했다. 네이티브 Windows PC 검증은 별도다.
