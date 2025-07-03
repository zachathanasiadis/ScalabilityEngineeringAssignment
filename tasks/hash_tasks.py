import hashlib
import time

def md5_task(parameters):
    """Task handler for calculating MD5 hash

    Args:
        parameters (dict): Task parameters containing 'string' to hash

    Returns:
        dict: Result containing the MD5 hash and execution time
    """
    start_time = time.time()

    # Get the string to hash
    string = parameters.get('string', '') if parameters else ''

    # Calculate MD5 hash
    md5 = hashlib.md5()
    md5.update(string.encode())
    hashed_string = md5.hexdigest()

    end_time = time.time()

    return {
        'original_string': string,
        'md5_hash': hashed_string,
        'execution_time_seconds': end_time - start_time
    }

def sha256_task(parameters):
    """Task handler for calculating SHA256 hash

    Args:
        parameters (dict): Task parameters containing 'string' to hash

    Returns:
        dict: Result containing the SHA256 hash and execution time
    """
    start_time = time.time()

    # Get the string to hash
    string = parameters.get('string', '') if parameters else ''

    # Calculate SHA256 hash
    sha256 = hashlib.sha256()
    sha256.update(string.encode())
    hashed_string = sha256.hexdigest()

    end_time = time.time()

    return {
        'original_string': string,
        'sha256_hash': hashed_string,
        'execution_time_seconds': end_time - start_time
    }