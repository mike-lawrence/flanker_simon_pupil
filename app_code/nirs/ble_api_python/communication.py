import time
import struct
import logging
import asyncio

import numpy as np
import numpy.lib.recfunctions as rfn
from bleak import BleakClient

from .constants import *
from .structures import header_struct
from .packets import validate_data_packet

# Controls whether sent/received bytes get printed to stdout.
# Will eventually replace with proper Pythonic logging.
VERBOSE = False

def dbg_print(s):
    if VERBOSE:
        print(s)


def cmd_to_packet(cmd, data = b""):
    """Generates a command packet for a given command type.

    Args:
        cmd (:obj:`PacketType`): The packet type definition for the command to
            generate.
        data (bytes, optional): Any additional encoded data to append to the end
            of the packet (e.g. for a write levels command). Defaults to no
            additional data.

    Returns:
        bytes: The formatted command packet to send to the headset.

    """
    cmd_array = np.array(
        (HEADER_PREAMBLE, 3 + len(data), cmd.ptype, cmd.pclass, cmd.cmd),
        dtype=header_struct
    )
    return cmd_array.tobytes() + data


def parse_packet(p, pformat):
    """Parses raw packet bytes into a given Numpy data structure.

    Args:
        p (bytearray): The raw data bytes (excluding header, command code, and
            result code) of the packet to parse.
        pformat (numpy.dtype): A custom ``numpy.dtype`` defining the names and
            data types of the fields contained in the packet.
    
    Returns:
        A custom numpy data structure containing the data from the packet.

    """
    try:
        return np.frombuffer(p, dtype=pformat)[0]
    except ValueError:
        expected = pformat.itemsize
        e = "Packet data does match expected length in bytes "
        e += "(expected {0}, got {1})".format(expected, len(p))
        raise ValueError(e)


def parse_data_packets(packets, pformat):
    """Parses and validates a set of path data packets from the headset.
    
    This function returns packets as a 2D numpy record array.
    """
    # Merge all packet bytes into a single array, discarding headers
    merged_bytes = bytearray(0)
    for p in packets:
        merged_bytes.extend(p['data'][4:])

    # Parse bytes as structured array, replacing checksums w/ checksum validity
    parsed = np.frombuffer(merged_bytes, dtype=pformat)
    parsed['checksum'][:] = [validate_data_packet(p['data']) for p in packets]
    parsed = rfn.append_fields(parsed,'time',np.array([p['time'] for p in packets],dtype='float64'))
    # Return parsed 2D array as record array (allows field access by attribute)
    return parsed.view(np.recarray)


def raise_headset_err(ret, msg=""):
    """Raises an informative exception for a given headset error code.
    
    This meant to be called internally when a packet with an error code is
    encountered. A message describing the process during which the error
    occurred (e.g. "calibrating the headset") can be optionally supplied.

    Args:
        ret (int): The result code of the error for which to raise an exception.
        msg (str, optional): A string of text to place after "Error encountered"
            in the exception error message (e.g. "initializing the headset").
    
    Raises:
        RuntimeError: An exception indicating the type of error specified by ``ret``.

    """
    if len(msg):
        msg = " " + msg
    err = "unknown error"
    if ret == RESULT_NOT_IMPLEMENTED:
        err = "command not yet implemented in firmware"
    elif ret == RESULT_UNKNOWN_COMMAND:
        err = "unrecognized command"
    elif ret == RESULT_INCOMPLETE_COMMAND:
        err = "incomplete command"
    elif ret == RESULT_CMD_PARAMETER_OUT_OF_RANGE:
        err = "parameter out of range"
    elif ret == RESULT_CMD_FAILED_CALIBRATION_ACTIVE:
        err = "cannot perform operation during calibration"
    elif ret == RESULT_CMD_FAILED_SESSION_ACTIVE:
        err = "cannot perform operation while recording data"
    elif ret == RESULT_CMD_FAILED_SESSION_NOT_ACTIVE:
        err = "cannot perform operation unless recording data"
    elif ret == RESULT_CMD_FAILED_NO_CAL_DATA:
        err = "device must have levels set before recording"
    elif ret == RESULT_CMD_FAILED_OPS_BUSY:
        err = "device is busy"
    raise RuntimeError("Error encountered{0}: {1}".format(msg, err))


def get_uuids(client):
    # Different revisions of the device have different input/output UUIDs.
    # This function tries to determine the correct UUIDs to communcate
    # with the given headset based on its service UUIDs.
    uuids = {}
    for service in client.services:
        if service.uuid in UART_UUIDS.keys():
            uuids = UART_UUIDS[service.uuid]
            break
    return uuids


def _bleak_backend(client):
    # Gets the name of the backend Bleak is currently using
    classname = client.__class__.__name__
    if classname == "BleakClientBlueZDBus":
        return "bluez"
    elif classname == "BleakClientCoreBluetooth":
        return "corebluetooth"
    elif classname == "BleakClientWinRT":
        return "winrt"
    elif classname == "BleakClientP4Android":
        return "p4android"
    return "unknown"


async def push_events(dev, q, rx_uuid):
    if not q.empty():
        val = q.get()
        if val[0] == 0x00:
            return False # Null byte tells ble thread to terminate
        await dev.write_gatt_char(rx_uuid, val)
        dbg_print("Sent: {0}\n".format(val))
    return True


async def ble_event_loop(device, q_in, q_out):
    """Asynchronous bluetooth communication loop with the headset.

    This runs in a separate thread after connecting to a headset, both for
    performance and so the end user doesn't need to understand or care about
    asyncio in order to use the headset in Python.

    """
    def _receive_events(sender, data):
        now = time.perf_counter()
        q_in.put({'time':now,'data':data})
        dbg_print("Received: {0}\n".format(data))

    running = True
    async with BleakClient(device) as headset:
        if _bleak_backend(headset) == "bluez":
            await headset._acquire_mtu() # Special case for Linux
        # NOTE: Raise error on systems with too small MTU sizes?
        dbg_print("System MTU size: {0} bytes".format(headset.mtu_size))
        ble_uuids = get_uuids(headset)
        await headset.start_notify(ble_uuids['tx'], _receive_events)
        while headset.is_connected and running:
            await asyncio.sleep(0.05)
            running = await push_events(headset, q_out, ble_uuids['rx'])
    dbg_print("Communication thread terminated!")


def ble_event_thread(device, q_in, q_out):
    """Initializes the bluetooth communication loop with the headset.

    To allow for fast sending and recieving of packets from the headset, this
    function is designed to be run in a separate thread from the main headset
    process.

    Args:
        device (str): The unique bluetooth address of the headset to initiate
            communication with.
        q_in (:obj:`queue.Queue`): An event queue the communication loop will
            watch for command packets to send to the headset.
        q_out (:obj:`queue.Queue`): An event queue where the communication loop
            will place any received response/event/data packets from the headset.
        
    """
    asyncio.run(ble_event_loop(device, q_in, q_out))
