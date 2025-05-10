def calculate_checksum(sentence: str) -> str:
    """Calculates the NMEA-style checksum for a sentence."""
    checksum = 0
    for char in sentence:
        checksum ^= ord(char)
    return f"{checksum:02X}"


def validate_checksum(message: str) -> bool:
    """Validates the checksum of a received NMEA-style message."""
    if not message or '$' not in message or '*' not in message:
        return False

    try:
        start_idx = message.index('$')
        # Find last asterisk for checksum
        end_idx = message.rindex('*')

        if start_idx >= end_idx or end_idx + 3 > len(message):
            return False  # Invalid structure or not enough chars for checksum

        sentence = message[start_idx + 1:end_idx]
        expected_checksum = calculate_checksum(sentence)
        provided_checksum = message[end_idx + 1:end_idx + 3]

        return expected_checksum.upper() == provided_checksum.upper()
    except ValueError:
        return False  # index() or rindex() throws ValueError if char not found
