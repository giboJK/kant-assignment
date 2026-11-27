# AI 사용 기록

사용 도구: Claude Code (Claude Opus 5)

질문과 관련 함수:

- `prepare_chunks`: 문단을 더 작게 나누지 않고 그대로 청크로 두는 기준이 무엇인지, 청크에 어떤 메타데이터를 남겨야 뒤 단계에서 쓸 수 있는지 물었습니다.
- `build_index`: `normalize_embeddings=True`가 왜 필요한지, E5 계열 모델에서 `passage: `와 `query: ` 접두어를 나누는 이유를 물었습니다.
- `search`: 폐기 문서를 색인에서 빼는 것과 검색 시 필터로 거르는 것의 차이를 물었습니다.
- `rewrite_query`: 별칭이 여러 개일 때 치환 결과가 누락되지 않으려면 어떤 변수에 이어서 치환해야 하는지 물었습니다.
- `answer_question`: 모델이 검색 결과에 없는 출처를 인용하는 경우를 어떻게 걸러내는지, 청크 ID와 원문 ID의 단위 차이를 물었습니다.
- `measure`: 같은 원문의 청크를 여러 개 찾았을 때 중복을 세지 않는 계산 방법과, 필요한 문서가 없는 사례에서 `0/0`을 피하는 이유를 물었습니다.


이해한 내용:

- E5 계열 임베딩은 문서에 `passage: `, 질의에 `query: ` 접두어를 붙이는 비대칭 검색용으로 학습되어, 접두어를 섞으면 검색 품질이 떨어집니다.
- `normalize_embeddings=True`로 정규화한 벡터의 내적이 코사인 유사도이므로 컬렉션의 `Distance.COSINE`과 맞습니다.
- `vpn`과 `vpn-old`는 둘 다 `category: access`라 의미 유사도만으로는 구분되지 않습니다. 폐기 문서를 색인에서 빼는 대신 검색 시 `status == "current"` 필터로 거르면 문서 이력은 남기면서 현행만 답할 수 있습니다.
- 공백을 먼저 정리해야 뒤따르는 중복 제거가 문자열 일치로 동작합니다. 정리하지 않으면 같은 문장이 공백 차이로 다른 청크가 됩니다.
- 답변의 `citations`는 청크 ID, 평가 사례의 `relevant_document_ids`는 원문 ID로 단위가 다릅니다. 모델이 원문 ID를 인용하면 출처 검사에서 걸러야 합니다.
- 문서 Recall은 집합 교집합으로 계산해야 같은 원문의 청크를 여러 개 찾아도 한 번만 셉니다. 필요한 문서가 없는 사례는 `0/0`을 계산하지 않고 `None`으로 두어 평균에서 제외합니다.
- 별칭 `초록문`은 `door` 문서의 `초록색`, `출입문`과 글자가 겹쳐 변환 전에는 엉뚱한 문서가 검색될 수 있습니다. 이 점이 질의 변환의 효과를 확인할 지점이 됩니다.

직접 작성한 부분:

- (빈칸 10개와 평가 사례, 이유 주석과 관측 주석을 본인이 어떻게 작성했는지 적으세요.)

다시 실행한 명령과 확인 결과:

- (본인이 실행한 명령과 그때 나온 수치를 적으세요. 아래는 확인할 항목입니다.)
- `uv run --frozen python main.py check index`
- `uv run --frozen python main.py run index` — 청크 수와 Point 수, `artifacts/index.json`에서 `vpn:0`의 승인 문장과 `vpn-old` 제외 여부
- `uv run --frozen python main.py check answer`
- `uv run --frozen python main.py check evaluate`
- `uv run --frozen python main.py run answer --live`
- `uv run --frozen python main.py run evaluate --live` — 변환 전후의 문서 Recall과 answer_check
- `uv run --frozen python main.py check all`
