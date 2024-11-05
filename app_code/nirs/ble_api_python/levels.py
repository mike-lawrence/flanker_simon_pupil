import numpy as np

from .structures import packet_types


def validate_levels(emit_levels, gain_levels, n_chans, n_paths):
    """Validates a given set of levels emitter/gain levels.

    This function ensures that the provided sets of emitter power and path gain
    values are a) the right lengths, and b) within the correct ranges of values.

    """
    len_err = " (expected {0}, got {1})"
    if len(emit_levels) != n_chans:
        e = "Emitter levels must match the number of measurements"
        raise ValueError(e + len_err.format(n_chans, len(emit_levels)))
    if len(gain_levels) != n_paths:
        e = "Path gain levels must match the number of paths"
        raise ValueError(e + len_err.format(n_paths, len(gain_levels)))
    
    range_err = " (invalid value: {0})"
    for val in emit_levels:
        if not (0 <= val <= 512):
            e = "Emitter power levels must be between 0 and 512, inclusive."
            raise ValueError(e + range_err.format(val))
    for val in gain_levels:
        if not (0 <= val <= 5):
            e = "Path gain levels must be between 0 and 5, inclusive."
            raise ValueError(e + range_err.format(val))


def encode_levels(emit_levels, gain_levels, ch_names):
    """Encodes a set of emitter and gain levels into headset format.
    
    """
    emit_arr = np.asarray(emit_levels, dtype=np.uint16)
    gain_arr = np.zeros((len(ch_names), 2), dtype=np.uint8)

    # Fill in empty array with gain values, leaving 2nd gain value for short (S)
    # channels blank (since they only have one path and thus only one gain)
    gain_list = list(gain_levels)
    for i in range(len(ch_names)):
        gain_arr[i, 0] = gain_list.pop(0)
        if ch_names[i][0] != "S":
            gain_arr[i, 1] = gain_list.pop(0)

    return emit_arr.tobytes() + gain_arr.tobytes()


def format_levels(p, ch_names):
    """Wrangle parsed levels data into a friendlier format.

    This returns levels values in the format ``[emit_levels, gain_levels]``,
    with "emit_levels" being a list of emitter power levels in the order of
    measurements and "gain_levels" being a list of path gain levels in the order
    of paths.

    Returns:
        tuple: A tuple containing the formatted levels data.

    """
    # Wrangle the (NUM_MEASUREMENTS, 2) gains array to (NUM_PATHS, 1), omitting
    # dummy values corresponding to the second gain for short (S) emitters.
    gain_list = []
    gain_arr = p['gains']
    for i in range(len(ch_names)):
        gain_list.append(int(gain_arr[i, 0]))
        if ch_names[i][0] != "S":
            gain_list.append(int(gain_arr[i, 1]))

    emit_list = [int(i) for i in p['attenuations']]
    return (emit_list, gain_list)