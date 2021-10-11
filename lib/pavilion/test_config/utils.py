def parse_timeout(value):
    """Parse the timeout value from either the run or build section
    into an int (or none).
    :param Union[str,None] value: The value to parse.
    """

    if value is None:
        return None
    if value.strip().isdigit():
        return int(value)
