# AX 대시보드 (AX Dashboard)

AX 프로젝트 관리 및 시각화를 위한 FastAPI 기반 애플리케이션입니다. 엑셀 스냅샷 업로드, 데이터 관리(CRUD), 그리고 이해관계자를 위한 인터랙티브 대시보드를 제공합니다.


<img width="30%" alt="image" src="https://github.com/user-attachments/assets/d013923f-c385-4a5c-81d7-29ba793f6118" />
<img width="30%8" alt="image" src="https://github.com/user-attachments/assets/56b91dd7-6f83-4aff-b512-46367cedae69" />
<img width="30%" alt="image" src="https://github.com/user-attachments/assets/6f0b403b-713a-486f-b164-c8304462c62f" />
<img width="30%" alt="image" src="https://github.com/user-attachments/assets/d30ce6f2-8f45-46d2-b5e7-079a8bedb012" />
<img width="30%" alt="image" src="https://github.com/user-attachments/assets/5374c0dc-cecb-4525-b045-6988ef770a5d" />
<img width="30%" alt="image" src="https://github.com/user-attachments/assets/785bc2f2-8af0-4919-8bbc-b684d467bded" />

## 주요 기능

*   **엑셀 업로드**: `YYYY-MM-DD.xlsx` 형식의 스냅샷 파일을 업로드하여 데이터를 동기화합니다.
*   **스냅샷 저장 및 관리**: 업로드된 데이터는 SQLite 데이터베이스(`db/ax.db`)에 영구 저장되며, 중복된 날짜의 데이터는 방지됩니다.
*   **인터랙티브 대시보드**: 챔피언별 활성 프로젝트, 제안 및 승인 월간 랭킹, 주요 KPI 카드, 전략 분포도, 챔피언 활동 히트맵 등을 제공합니다.
*   **데이터 관리(CRUD)**: 프로젝트 및 월간 이벤트를 간편한 폼을 통해 관리할 수 있으며, 모든 변경 사항은 감사 로그(Audit Log)에 기록됩니다.
*   **시각화 차트**: Chart.js를 사용한 막대 그래프와 CSS 기반의 히트맵을 통해 데이터 인사이트를 시각적으로 제공합니다.

## 실행 방법

Python 3.10 이상이 설치되어 있어야 합니다.

1.  가상환경 설정 및 패키지 설치:
    ```sh
    python -m venv venv
    # Windows
    .\venv\Scripts\activate
    # macOS/Linux
    # source venv/bin/activate
    pip install -r requirements.txt
    ```

2.  서버 실행:
    ```sh
    uvicorn app.main:app --reload
    ```

3.  접속:
    *   대시보드: `http://localhost:8000`
    *   관리자 인터페이스: `http://localhost:8000/admin` (스냅샷 업로드 및 데이터 관리)
