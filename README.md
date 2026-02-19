#  PI Dashboard (Project Insight Dashboard)

PI Dashboard는 엑셀 기반의 프로젝트 데이터를 분석하여 직관적인 통찰력을 제공하는 **프로젝트 인사이트 대시보드**입니다. 복잡한 데이터를 시각화하고 성과를 모니터링하여 효율적인 의사결정을 돕습니다.


<img width="30%" alt="image" src="https://github.com/user-attachments/assets/d013923f-c385-4a5c-81d7-29ba793f6118" />
<img width="30%8" alt="image" src="https://github.com/user-attachments/assets/56b91dd7-6f83-4aff-b512-46367cedae69" />
<img width="30%" alt="image" src="https://github.com/user-attachments/assets/6f0b403b-713a-486f-b164-c8304462c62f" />
<img width="30%" alt="image" src="https://github.com/user-attachments/assets/d30ce6f2-8f45-46d2-b5e7-079a8bedb012" />
<img width="30%" alt="image" src="https://github.com/user-attachments/assets/5374c0dc-cecb-4525-b045-6988ef770a5d" />
<img width="30%" alt="image" src="https://github.com/user-attachments/assets/785bc2f2-8af0-4919-8bbc-b684d467bded" />

## 주요 기능 (Key Features)

*   **데이터 동기화**: `YYYY-MM-DD.xlsx` 형식의 엑셀 스냅샷을 업로드하여 대량의 프로젝트 데이터를 빠르고 정확하게 데이터베이스화합니다.
*   **성과 모니터링 대시보드**: 
    *   **KPI 카드**: 프로젝트 진행률, 제안 건수, 승인 현황 등 핵심 지표를 실시간 확인
    *   **챔피언 랭킹**: 월간 제안 및 승인 실적에 따른 실시간 순위 산정
    *   **활동 히트맵**: 팀원별 활동 강도를 시각화하여 리소스 관리 지원
*   **효율적인 프로젝트 관리 (CRUD)**: 직관적인 웹 인터페이스를 통해 현황을 직접 수정하고 관리할 수 있으며, 이 모든 과정은 감사 로그(Audit Log)로 철저히 기록됩니다.
*   **비주얼 인사이트**: Chart.js 기반의 동적 그래프와 세련된 UI를 통해 데이터 사이의 상관관계와 트렌드를 한눈에 파악합니다.

## 시작하기 (Getting Started)

Python 3.10 이상의 환경이 필요합니다.

1.  **환경 설정 및 의존성 설치**:
    ```sh
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    ```

2.  **프로그램 실행**:
    ```sh
    uvicorn app.main:app --reload
    ```

3.  **접속 링크**:
    *   **통합 대시보드**: `http://localhost:8000`
    *   **데이터 관리 시스템**: `http://localhost:8000/admin`

