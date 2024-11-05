import struct
import numpy as np

from .constants import HEADER_PREAMBLE_BYTES, DATA_PREAMBLE_BYTES


def is_data_packet(p):
    """Checks whether a raw headset packet is a measurement data packet.

    Args:
        p (bytearray): The raw packet to inspect.

    Returns:
        bool: True if the packet is a data packet, otherwise False.

    """
    return p[:4] == DATA_PREAMBLE_BYTES


def validate_data_packet(p):
    """Checks the integrity of a data packet from the headset.

    Measurement packet checksums are calculated in the firmware by casting the
    pre-checksum packet bytes to an array of unsigned 16-bit ints, adding those
    values together, and casting the result to a 16-bit int (discarding any bits
    above ``0xFFFF``). This function performs the same operation on the
    recieving end to verify the packet matches its checksum.

    Args:
        p (bytearray): The raw measurement packet to validate.

    Returns:
        bool: Whether the packet matches its checksum.

    """
    tmp = np.frombuffer(p, dtype=np.uint16)
    checksum = tmp[-1]
    packet_sum = int(np.sum(tmp[:-1]))
    return (packet_sum & 0xFFFF) == checksum


class RecievedPacket(object):
    """An intermediate class for parsing and validating response/event packets.

    In the headset firmware, all non-measurement packets share a basic structure
    and characteristics:

    * A two-byte preamble (0xF0CA, first two bytes)
    * The length of the packet (3rd byte)
    * The packet type, class, and command (4th-6th bytes)
    * The result code of the packet (last 4 bytes)

    This class validates the basic structure of a packet and makes its attributes
    more easily accessible.

    Args:
        raw (bytearray): The raw headset packet to parse and validate.
    
    Raises:
        ValueError: If the packet is too small (under 10 bytes), missing the
            preamble, or does not match its self-reported length.

    """
    def __init__(self, raw):
        self._validate(raw)
        self._raw = raw

    def _validate(self, p):
        # Check that input is large enough to be a packet
        # (header = 6 bytes, result = 4 bytes)
        if len(p) < 10:
            e = "Packet too short ({0} bytes)".format(len(p))
            raise ValueError(e)
        # Check start of packet for sync preamble bytes
        if p[:2] != HEADER_PREAMBLE_BYTES:
            e = "Packet missing sync preamble (0xF0CA) in header"
            raise ValueError(e)
        # Make sure the packet's self-reported length is accurate
        expected = p[2] + 3
        if len(p) != expected:
            e = "Packet does not match self-reported length ({} expected, {} actual)"
            raise ValueError(e.format(expected, len(p)))

    @property
    def type(self):
        return bytes(self._raw[3:6])

    @property
    def length(self):
        """int: The length of the packet, excluding the preamble and length byte.
        """
        return self._raw[2] - 3
    
    @property
    def data(self):
        """bytearray: The raw bytes between the commmand code and result code (if any).

        """
        return self._raw[6:-4]

    @property
    def result(self):
        """int: The result code for the packet.
        
        If this value is ``1`` (``RESULT_SUCCESS``), its associated command
        completed successfully. Otherwise, this value indicates the type of
        error that occurred during its corresponding process.
        
        """
        return struct.unpack("I", self._raw[-4:])[0]
