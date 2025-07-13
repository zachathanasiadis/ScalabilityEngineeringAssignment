import time

def calculate_fibonacci(n):
    """Calculate the nth Fibonacci number

    Args:
        n (int): Position in the Fibonacci sequence (0-indexed)

    Returns:
        int: The nth Fibonacci number
    """
    if n <= 0:
        return 0
    elif n == 1:
        return 1

    # Use dynamic programming approach for better performance
    fib = [0, 1]
    for i in range(2, n + 1):
        fib.append(fib[i-1] + fib[i-2])

    return fib[n]

def fibonacci_task(parameters):
    """Task handler for calculating Fibonacci numbers

    Args:
        parameters (dict): Task parameters containing 'n' for the position

    Returns:
        dict: Result containing the Fibonacci number and execution time
    """
    start_time = time.time()

    # Default to calculating the 25th Fibonacci number if not specified
    n = parameters.get('n', 25) if parameters else 25

    # Add some artificial delay to simulate work
    time.sleep(1)

    result = calculate_fibonacci(n)
    end_time = time.time()

    return {
        'fibonacci': result,
        'position': n,
        'execution_time_seconds': end_time - start_time
    }