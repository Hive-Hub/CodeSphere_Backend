import os
import json
import requests
from app.ai.providers.base import AIProvider
from app.logger import error_logger

class OpenAIProvider(AIProvider):
    """OpenAI REST API Provider Implementation."""

    def __init__(self, api_key: str = None, model: str = "gpt-4o-mini", timeout: int = 30):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model
        self.timeout = timeout
        self.base_url = "https://api.openai.com/v1/chat/completions"

    def _call_api(self, prompt: str, system_prompt: str = "You are an AI coding assistant.") -> dict:
        if not self.api_key:
            return {"error": "OPENAI_API_KEY is missing"}

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2
        }

        try:
            resp = requests.post(self.base_url, json=payload, headers=headers, timeout=self.timeout)
            if resp.status_code == 200:
                data = resp.json()
                content = data["choices"][0]["message"]["content"]
                return json.loads(content)
            else:
                error_logger.error(f"OpenAI API error HTTP {resp.status_code}: {resp.text}")
                return {"error": f"OpenAI API error HTTP {resp.status_code}"}
        except Exception as e:
            error_logger.error(f"OpenAI request exception: {str(e)}")
            return {"error": f"OpenAI request exception: {str(e)}"}

    def analyze_code(self, problem: dict, code: str, language: str, mode: str, compiler_results: dict = None, snapshots: list = None) -> dict:
        prompt = f"Analyze code quality for {language}:\nCode:\n{code}\nProblem: {json.dumps(problem or {})}"
        sys_p = "Analyze code quality. Return JSON with keys: overall (0-100), logic (0-10), readability (0-10), structure (0-10), efficiency (0-10), error_handling (0-10), summary (str), suggestions (list)."
        res = self._call_api(prompt, sys_p)
        if "error" in res:
            from app.ai.providers.mock_provider import MockAIProvider
            return MockAIProvider().analyze_code(problem, code, language, mode, compiler_results, snapshots)
        return res

    def analyze_progress(self, problem: dict, code: str, language: str, reference_solution: str = None, snapshots: list = None, compiler_results: dict = None) -> dict:
        prompt = f"Estimate progress for {language} problem solving:\nProblem: {json.dumps(problem or {})}\nCode:\n{code}"
        sys_p = "Estimate progress. Return JSON with keys: progress (0-100 or null), confidence (0-100), stage (str), completed_components (list), remaining_components (list), reasoning_summary (str)."
        res = self._call_api(prompt, sys_p)
        if "error" in res:
            from app.ai.providers.mock_provider import MockAIProvider
            return MockAIProvider().analyze_progress(problem, code, language, reference_solution, snapshots, compiler_results)
        return res

    def analyze_error(self, code: str, language: str, compiler_output: str) -> dict:
        prompt = f"Explain compiler output for {language}:\nCode:\n{code}\nCompiler Output:\n{compiler_output}"
        sys_p = "Explain compiler error without giving direct solution code. Return JSON with keys: error_type, explanation, likely_cause, concept_hint."
        res = self._call_api(prompt, sys_p)
        if "error" in res:
            from app.ai.providers.mock_provider import MockAIProvider
            return MockAIProvider().analyze_error(code, language, compiler_output)
        return res

    def generate_hint(self, problem: dict, code: str, language: str, mode: str, compiler_results: dict = None) -> dict:
        prompt = f"Generate hint for {mode} mode in {language}:\nProblem: {json.dumps(problem or {})}\nCode:\n{code}"
        sys_p = "Generate hint. If mode is problem_solving, DO NOT give direct code solutions or algorithm implementations. Return JSON with keys: hint, hint_type, mode."
        res = self._call_api(prompt, sys_p)
        if "error" in res:
            from app.ai.providers.mock_provider import MockAIProvider
            return MockAIProvider().generate_hint(problem, code, language, mode, compiler_results)
        return res

    def detect_stuck(self, code: str, snapshots: list, compiler_history: list, activity_history: list) -> dict:
        from app.ai.providers.mock_provider import MockAIProvider
        return MockAIProvider().detect_stuck(code, snapshots, compiler_history, activity_history)

    def generate_session_summary(self, session_info: dict, student_stats: list) -> dict:
        from app.ai.providers.mock_provider import MockAIProvider
        return MockAIProvider().generate_session_summary(session_info, student_stats)
