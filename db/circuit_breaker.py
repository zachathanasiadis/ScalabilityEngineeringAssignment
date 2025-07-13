"""
Circuit Breaker pattern for database operations
Prevents database overloading by failing fast when database is overwhelmed
"""

import time
import threading
from enum import Enum
from typing import Callable, Any
from functools import wraps

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Circuit breaker is open (failing fast)
    HALF_OPEN = "half_open"  # Testing if service is back

class DatabaseCircuitBreaker:
    """Circuit breaker for database operations"""

    def __init__(self, failure_threshold=5, recovery_timeout=60, success_threshold=3):
        self.failure_threshold = failure_threshold  # Number of failures before opening
        self.recovery_timeout = recovery_timeout    # Time to wait before trying again
        self.success_threshold = success_threshold  # Successes needed to close circuit

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED
        self.lock = threading.RLock()

    def _can_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset"""
        if self.last_failure_time is None:
            return True
        return time.time() - self.last_failure_time >= self.recovery_timeout

    def _record_success(self):
        """Record a successful operation"""
        with self.lock:
            self.failure_count = 0
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.success_count = 0
                    print("Circuit breaker CLOSED - database is healthy")

    def _record_failure(self):
        """Record a failed operation"""
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            self.success_count = 0

            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
                print(f"Circuit breaker OPEN - database appears to be overloaded")

    def call(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with circuit breaker protection"""
        with self.lock:
            if self.state == CircuitState.OPEN:
                if self._can_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                    print("Circuit breaker HALF_OPEN - testing database")
                else:
                    raise Exception("Circuit breaker is OPEN - database operations are failing")

        try:
            result = func(*args, **kwargs)
            self._record_success()
            return result
        except Exception as e:
            self._record_failure()
            raise e

    def get_state(self) -> dict:
        """Get current circuit breaker state"""
        with self.lock:
            return {
                "state": self.state.value,
                "failure_count": self.failure_count,
                "success_count": self.success_count,
                "last_failure_time": self.last_failure_time,
                "can_attempt_reset": self._can_attempt_reset()
            }

# Global circuit breaker instance
db_circuit_breaker = DatabaseCircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60,
    success_threshold=3
)

def with_circuit_breaker(func):
    """Decorator to wrap database operations with circuit breaker"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        return db_circuit_breaker.call(func, *args, **kwargs)
    return wrapper