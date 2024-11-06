from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from langchain_anthropic import ChatAnthropic
from langchain_community.utilities import SQLDatabase
from django.conf import settings
import os
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage


class LLMAnalysisViewSet(viewsets.ViewSet):
    @action(detail=False, methods=["post"])
    def analyze(self, request):
        question = request.data.get("question")
        if not question:
            return Response({"error": "질문을 입력해주세요."}, status=400)

        try:
            # DB 연결 URL 구성
            db_settings = settings.DATABASES["default"]
            db_url = (
                f"postgresql://{db_settings['USER']}:{db_settings['PASSWORD']}@"
                f"{db_settings.get('HOST', 'localhost')}:{db_settings.get('PORT', '5432')}/"
                f"{db_settings['NAME']}"
            )

            # DB 연결
            db = SQLDatabase.from_uri(db_url)

            # 시스템 프롬프트 수정
            system_prompt = """You are a PostgreSQL query generator. Generate ONLY SQL queries.
STRICT RULES:
1. Return ONLY the SQL query, nothing else
2. Query MUST start with SELECT
3. NO explanations, NO comments
4. NO Korean text except in LIKE conditions
5. Use proper table aliases (u for users, d for departments, t for tasks)
6. Always include proper JOIN conditions

Database Schema:
organizations_department (d):
  id, name, code, parent_id
  - parent_id NULL means headquarters (본부)
  - parent_id NOT NULL means team under headquarters (팀)

accounts_user (u):
  id, department_id, username, first_name, last_name, role, rank, is_active
  - department_id references organizations_department(id)
  - is_active default true

tasks_task (t):
  id, assignee_id, department_id, title, status, priority, difficulty
  - assignee_id references accounts_user(id)
  - department_id references organizations_department(id)
  - status: TODO/IN_PROGRESS/REVIEW/DONE/HOLD

tasks_taskevaluation (te):
  id, task_id, evaluator_id, performance_score
  - task_id references tasks_task(id)
  - evaluator_id references accounts_user(id)
  - performance_score: 1-5

Example Queries:

1. Count employees in 백엔드팀:
SELECT COUNT(*) FROM accounts_user u 
JOIN organizations_department d ON u.department_id = d.id 
WHERE d.name LIKE '%백엔드%' AND u.is_active = true;

2. Count all employees in 푸드테크본부 (including teams):
SELECT COUNT(*) FROM accounts_user u 
JOIN organizations_department d ON u.department_id = d.id 
LEFT JOIN organizations_department p ON d.parent_id = p.id 
WHERE (d.name LIKE '%푸드테크%' AND d.parent_id IS NULL) 
   OR (p.name LIKE '%푸드테크%') AND u.is_active = true;

3. Find best performing employee:
SELECT u.last_name || u.first_name as name, d.name as dept, 
       ROUND(AVG(te.performance_score)::numeric, 1) as score
FROM accounts_user u 
JOIN tasks_task t ON t.assignee_id = u.id 
JOIN tasks_taskevaluation te ON te.task_id = t.id 
JOIN organizations_department d ON u.department_id = d.id 
WHERE t.status = 'DONE' 
GROUP BY u.id, u.last_name, u.first_name, d.name 
HAVING COUNT(te.id) >= 3 
ORDER BY score DESC LIMIT 1;

REMEMBER: Return ONLY the SQL query. Any other text will cause an error."""

            # Anthropic 모델 초기화
            llm = ChatAnthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                model="claude-3-haiku-20240307",
                temperature=0.7,
                streaming=True,
            )

            # 직접 LLM에 질문하여 SQL 쿼리 생성
            response = llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(
                        content=(
                            "Generate a PostgreSQL query to answer:"
                            f" {question}"
                        )
                    ),
                ]
            )

            # 응답에서 SQL 쿼리 추출
            sql_query = response.content

            # 쿼리 검증
            if (
                not sql_query.strip().upper().startswith("SELECT")
                or "이" in sql_query
                or "를" in sql_query
            ):
                return Response(
                    {
                        "error": "유효한 쿼리를 생성할 수 없습니다.",
                        "sql_query": "SELECT NULL AS error;",
                        "result": None,
                    },
                    status=400,
                )

            # 쿼리 실행
            result = db.run(sql_query)

            # 결과를 LLM에게 전달하여 자연스러운 응답 생성
            format_prompt = """You are a helpful assistant that formats database query results into natural Korean sentences.
            
Original question: {question}
SQL query: {sql_query}
Query result: {result}

Rules:
1. Respond in Korean only
2. Keep the response concise but natural
3. Include the numeric results in the response
4. Match the tone of the response to the question
5. If the result is 0 or empty, explain that no matching data was found
6. Use appropriate Korean particles and honorifics

Format the result into a natural Korean sentence:"""

            llm = ChatAnthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                model="claude-3-5-sonnet-20240620",
                temperature=0.7,
                streaming=True,
            )

            response = llm.invoke(
                [
                    SystemMessage(content=format_prompt),
                    HumanMessage(
                        content=(
                            f"Question: {question}\nSQL: {sql_query}\nResult:"
                            f" {result}"
                        )
                    ),
                ]
            )

            formatted_result = response.content

            return Response(
                {
                    "question": question,
                    "sql_query": sql_query,
                    "result": result,
                    "formatted_result": formatted_result,
                }
            )

        except Exception as e:
            return Response({"error": str(e)}, status=500)
