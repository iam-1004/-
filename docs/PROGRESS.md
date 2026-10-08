# 실행 기록 — 2026-10-08-leet-manager
승인한 계획: docs/superpowers/plans/2026-10-08-leet-manager.md
기존 격리 체크아웃 사용. GitHub 게시 없음.
Pre-flight: Task 1 Store → Tasks 2/3/4, dict 기반 인터페이스 일치.
Pre-flight: Task 2 extract_text/propose_sections → Task 4 확인형 가져오기, 일치.
Pre-flight: Task 3 backup/restore/export_csv → Task 4 자료관리, 일치.
Task 1: complete — 저장소 테스트 7/7 통과. ID 불변, 초안/완료 검증, 검색, 과목, 이력 확인.
Task 2: complete — 全13 tests pass. 합성 HWPX에서 정답 3/1/4·보기·해설·쪽수 보존, 미확인 분류, 중복·손상·크기 제한 확인. 실 HWPX는 미첨부.
Task 3: complete — 전체 17/17 통과. DB+원본 백업, 자동 백업 후 복원, 손상/경로 탈출 거부, CSV 식별자·키워드·수식 방어 확인.
Task 4: complete — 가상 디스플레이(Xvfb)를 임시 폴더에서 준비해 GUI 테스트 실제 실행. 화면 저장/문항ID/원문 배정/가져오기/문항 필터 통과. readonly Tcl_Obj 상태 비교 오류 RED→GREEN.
Task 5: 소스 실행 설명서, Python 3.12 Windows 빌드 스크립트, 실행 CMD 준비. Linux에서 Windows 바이너리를 만들어 검증했다는 주장은 하지 않는다.
날짜 유효성·미확인 연도 필터·OS 단일 인스턴스 잠금 추가, 전체 23/23 통과.
Final review: 독립 reviewer가 Important 3개 확인. Critical/Minor 없음.
Final: fixed CSV 보호 경로와 원자적 파일 교체 — test_csv_rejects_managed_destinations_without_modifying/test_csv_atomic_failure_preserves_destination RED→GREEN.
Final: fixed 중복 편집창 저장 충돌 — test_stale_edit_rejected_preserves_new_passage RED→GREEN. UI에서 revision 보존해 충돌을 사용자에게 알리고 입력 유지.
Final: fixed 복원 스키마/자료 검증 — incompatible_schema, invalid_record_payload, missing_set_fields RED→GREEN.
Final: 복원 파일 교체 실패 fault injection에서 기존 DB·원본과 연결 복구 확인.
Final: 전체 33/33 테스트 통과 (GUI 실제 실행 포함), skipped=0.
환경 제한: Linux이며 Windows Python 공식 설치 파일 주소 접근은 프록시 403. Windows EXE 생성/실행, 파일 연결, Windows 전용 잠금은 검증하지 않음. 실제 HWPX 미첨부. 소스 패키지와 Windows 빌드 절차를 제공.

사용자 후속 요청: Windows EXE 제공 및 다운로드 경로 변경.
Windows용 CPython 3.12.15(배포 SHA256 대조 완료), Wine 10, PyInstaller 6.16으로 단일 PE32+ x64 GUI EXE 생성.
Windows Python/Wine에서 33/33 테스트 실제 통과. Windows용 잠금 경로도 통과.
실제 frozen EXE에서 화면 시작, 키보드/마우스로 자료 저장, 정상 종료, 재실행, 세트·문항ID 및 제시문 보존 확인.
같은 자료 폴더의 두 번째 EXE 실행은 중복 실행 안내로 거부됨.
Windows Python/Tcl 런타임을 EXE에 포함했고 Wine 시스템 라이브러리는 포함하지 않음. 사용자 자료 미포함.
최종 산출물: /workspace/outputs/LEETQuestionManager.exe. 실제 Windows PC 검증은 Wine 검증과 구별하며 미실시.

사용자 요청에 따라 영문 파일명 program.exe로 소스에서 다시 빌드(단순 파일 복사/이름 변경 아님).
build_windows.ps1과 README.md의 산출물 이름을 program.exe로 변경.
환경 재시작으로 사라진 Windows CPython/Wine/PyInstaller를 검증된 배포본에서 재준비.
Windows Python/Wine 전체 33/33 테스트 통과, PyInstaller 새 빌드 exit 0.
새 frozen program.exe의 실제 GUI 시작 및 WM_CLOSE에 따른 정상 종료 exit 0 확인.
산출물: /workspace/outputs/program.exe, SHA256 3d1d3e701e8742f29cbc08bfba7ef02a15aeb5be7f15c16adec7947fff38cb6d.
다운로드 전달은 별도 미완료: Dropbox 업로드 도구/저장된 인증값 없음. file.io API는 POST 301 및 리다이렉트 대상 POST 405 응답으로 업로드 미수행.
