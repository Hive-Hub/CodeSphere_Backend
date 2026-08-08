from app.ai.providers.base import AIProvider

class MockAIProvider(AIProvider):
    """Deterministic Mock AI Provider for testing and offline execution."""

    def analyze_code(self, problem: dict, code: str, language: str, mode: str, compiler_results: dict = None, snapshots: list = None) -> dict:
        return {
            "overall": 85,
            "logic": 8,
            "readability": 9,
            "structure": 8,
            "efficiency": 8,
            "error_handling": 7,
            "summary": "Mock analysis: Clean code structure with proper logic flow.",
            "suggestions": ["Consider adding input validation edge cases."]
        }

    def analyze_progress(self, problem: dict, code: str, language: str, reference_solution: str = None, snapshots: list = None, compiler_results: dict = None) -> dict:
        if not code or len(code.strip()) < 5:
            return {
                "progress": None,
                "confidence": 30,
                "stage": "Not Started",
                "completed_components": [],
                "remaining_components": ["All requirements"],
                "reasoning_summary": "Insufficient code provided for estimation."
            }

        return {
            "progress": 75,
            "confidence": 90,
            "stage": "Implementation",
            "completed_components": ["Input parsing", "Core logic"],
            "remaining_components": ["Edge cases", "Output formatting"],
            "reasoning_summary": "Student has completed core algorithm logic."
        }

    def analyze_error(self, code: str, language: str, compiler_output: str) -> dict:
        return {
            "error_type": "SyntaxError" if "syntax" in compiler_output.lower() else "ExecutionError",
            "explanation": "The compiler encountered an invalid statement structure.",
            "likely_cause": "Missing semicolon or unmatched parentheses.",
            "concept_hint": "Check syntax rules for statement termination."
        }

    def generate_hint(self, problem: dict, code: str, language: str, mode: str, compiler_results: dict = None) -> dict:
        if mode == "problem_solving":
            return {
                "hint": "Try breaking down the problem into smaller steps. Check your loop condition.",
                "hint_type": "conceptual",
                "mode": "problem_solving"
            }
        return {
            "hint": "Consider using a hash map to reduce time complexity to O(N).",
            "hint_type": "optimization",
            "mode": "practice"
        }

    def detect_stuck(self, code: str, snapshots: list, compiler_history: list, activity_history: list) -> dict:
        failed_compiler_count = sum(1 for c in compiler_history if c.get("exit_code") != 0 or c.get("error"))
        if failed_compiler_count >= 3:
            return {
                "stuck": True,
                "confidence": 85,
                "reason": f"Repeated compilation failures ({failed_compiler_count} times)."
            }
        return {
            "stuck": False,
            "confidence": 90,
            "reason": "Student is making steady progress."
        }

    def generate_session_summary(self, session_info: dict, student_stats: list) -> dict:
        return {
            "summary": "Overall good classroom engagement with 80% students making progress.",
            "key_topics_struggled": ["Boundary conditions", "Syntax errors"],
            "recommendations": ["Review array indexing concepts in next lecture."]
        }
