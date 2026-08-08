from abc import ABC, abstractmethod

class AIProvider(ABC):
    """Abstract Base Class for AI Code Intelligence Providers."""

    @abstractmethod
    def analyze_code(self, problem: dict, code: str, language: str, mode: str, compiler_results: dict = None, snapshots: list = None) -> dict:
        """Perform comprehensive code quality and structure analysis."""
        pass

    @abstractmethod
    def analyze_progress(self, problem: dict, code: str, language: str, reference_solution: str = None, snapshots: list = None, compiler_results: dict = None) -> dict:
        """Estimate student progress toward completing problem requirements."""
        pass

    @abstractmethod
    def analyze_error(self, code: str, language: str, compiler_output: str) -> dict:
        """Explain compiler/runtime errors with conceptual hints."""
        pass

    @abstractmethod
    def generate_hint(self, problem: dict, code: str, language: str, mode: str, compiler_results: dict = None) -> dict:
        """Generate mode-restricted hint for student."""
        pass

    @abstractmethod
    def detect_stuck(self, code: str, snapshots: list, compiler_history: list, activity_history: list) -> dict:
        """Detect stuck pattern in student coding session."""
        pass

    @abstractmethod
    def generate_session_summary(self, session_info: dict, student_stats: list) -> dict:
        """Generate high-level teacher classroom summary."""
        pass
