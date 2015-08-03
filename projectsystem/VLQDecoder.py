encoded_values = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"

def decode_char(char):
    if len(char) == 1:
        return encoded_values.index(char)
    
    # Return -1 if invalid input
    return -1

def decode(input_string, offset):
    result = 0
    negative = False

    shift = 0

    for i in range(offset, len(input_string)):
        byte = decode_char(input_string[i])
        if (i == offset):
            # Invalid character encoding
            if (byte == -1):
                return None

            if ((byte & 1) == 1):
                negative = True

            result = (byte >> 1) & 15
        else:
            result = result | ((byte & 31) << shift)

        shift += 4 if (i == offset) else 5

        if ((byte & 32) == 32):
            continue
        else:
            return { 'value': -result if negative else result, 'chars_read': (i - offset + 1) }