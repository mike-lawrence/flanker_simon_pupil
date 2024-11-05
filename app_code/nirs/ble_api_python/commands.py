from .constants import *
import struct


class PacketType(object):
    """A helper class for representing command/response/event packet types.

    Except for measurement data packets (which are identified by a unique
    preamble), all packets sent to and received from the headset are identified
    by three bytes:

    * The packet type (command, response, or event)
    * The packet class (system, measurement, or diagnostic)
    * The packet command code (e.g. ``SYSTEM_READ_SYSINFO``).

    To make the internal checking of packet types easier, this class allows the
    raw packet type bytes to be compared directly with packet type constants::

       packet_type_bytes = b"\x02\x01\x01"
       is_sysinfo = packet_type_bytes == RSP_READ_SYSINFO
    
    Args:
        ptype (int): The type of the packet (``CMD``, ``RSP``, or ``EVT``).
        pclass (int): The class of the packet (``SYSTEM``, ``MEASURE``, or ``DIAG``).
        cmd (int): The command ID for the packet.

    """
    def __init__(self, ptype, pclass, cmd):
        self.ptype = ptype
        self.pclass = pclass
        self.cmd = cmd
        self.name = self._get_name(ptype, pclass, cmd)
        self.bytes = struct.pack("BBB", ptype, pclass, cmd)

    def __repr__(self):
        return self.__str__()

    def __str__(self):
        if self.ptype == CMD:
            return "Command({0})".format(self.name)
        elif self.ptype == RSP:
            return "Response({0})".format(self.name)
        elif self.ptype == EVT:
            return "Event({0})".format(self.name)
        else:
            return "UnknownPacket({0})".format(self.name)

    def _get_name(self, ptype, pclass, cmd):
        name = "{}, {}, {}".format(ptype, pclass, cmd)
        try:
            if self.ptype in [CMD, RSP]:
                name = CMD_NAME_MAP[pclass][cmd]
            elif self.ptype == EVT:
                name = EVT_NAME_MAP[pclass][cmd]
        except KeyError:
            pass
        return name

    def __eq__(self, other):
        if isinstance(other, bytes):
            return self.bytes == other
        elif isinstance(other, PacketType):
            return self.bytes == other.bytes
        return False



CMD_READ_SYSINFO = PacketType(CMD, SYSTEM, SYSTEM_READ_SYSINFO)
CMD_READ_BATTERY = PacketType(CMD, SYSTEM, SYSTEM_READ_BATTERY)

CMD_MEASURE_WRITE_CAL = PacketType(CMD, MEASURE, MEASURE_WRITE_CAL)
CMD_MEASURE_READ_CAL = PacketType(CMD, MEASURE, MEASURE_READ_CAL)
CMD_MEASURE_CONFIG_CAL = PacketType(CMD, MEASURE, MEASURE_CONFIG_CAL)
CMD_MEASURE_BEGIN_CAL = PacketType(CMD, MEASURE, MEASURE_BEGIN_CAL)
CMD_MEASURE_CONFIG_SESS = PacketType(CMD, MEASURE, MEASURE_CONFIG_SESS)
CMD_MEASURE_BEGIN_SESS = PacketType(CMD, MEASURE, MEASURE_BEGIN_SESS)
CMD_MEASURE_END_SESS = PacketType(CMD, MEASURE, MEASURE_END_SESS)

CMD_DIAG_READ_IMU = PacketType(CMD, DIAG, DIAG_READ_IMU)  # Not in FW


RSP_READ_SYSINFO = PacketType(RSP, SYSTEM, SYSTEM_READ_SYSINFO)
RSP_READ_BATTERY = PacketType(RSP, SYSTEM, SYSTEM_READ_BATTERY)

RSP_MEASURE_WRITE_CAL = PacketType(RSP, MEASURE, MEASURE_WRITE_CAL)
RSP_MEASURE_READ_CAL = PacketType(RSP, MEASURE, MEASURE_READ_CAL)
RSP_MEASURE_CONFIG_CAL = PacketType(RSP, MEASURE, MEASURE_CONFIG_CAL)
RSP_MEASURE_BEGIN_CAL = PacketType(RSP, MEASURE, MEASURE_BEGIN_CAL)
RSP_MEASURE_CONFIG_SESS = PacketType(RSP, MEASURE, MEASURE_CONFIG_SESS)
RSP_MEASURE_BEGIN_SESS = PacketType(RSP, MEASURE, MEASURE_BEGIN_SESS)
RSP_MEASURE_END_SESS = PacketType(RSP, MEASURE, MEASURE_END_SESS)

RSP_DIAG_READ_IMU = PacketType(RSP, DIAG, DIAG_READ_IMU)  # Not in FW


EVT_SYSTEM_BATTERY_STATUS = PacketType(EVT, SYSTEM, SYSTEM_BATTERY_STATUS)
EVT_SYSTEM_ERROR = PacketType(EVT, SYSTEM, SYSTEM_ERROR)
EVT_SYSTEM_CONN_READY = PacketType(EVT, SYSTEM, SYSTEM_CONN_READY)
EVT_IMU_UPDATE = PacketType(EVT, SYSTEM, IMU_UPDATE)

EVT_MEASURE_COMPLETE_CAL = PacketType(EVT, MEASURE, MEASURE_COMPLETE_CAL)

EVT_DIAG_MEASURE_COMPLETE = PacketType(EVT, DIAG, DIAG_MEASURE_COMPLETE)  # Not in FW
