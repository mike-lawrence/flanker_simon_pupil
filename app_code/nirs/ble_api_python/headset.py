import time
import struct
import atexit
import asyncio
import logging
import warnings
import threading
from queue import Queue

import numpy as np
from bleak import BleakScanner, BleakClient

from .constants import *
from .commands import (
    CMD_READ_SYSINFO, RSP_READ_SYSINFO,
    CMD_MEASURE_CONFIG_CAL, RSP_MEASURE_CONFIG_CAL,
    CMD_MEASURE_CONFIG_SESS, RSP_MEASURE_CONFIG_SESS,
    CMD_MEASURE_READ_CAL, RSP_MEASURE_READ_CAL,
    CMD_MEASURE_WRITE_CAL, RSP_MEASURE_WRITE_CAL,
    CMD_MEASURE_BEGIN_CAL, RSP_MEASURE_BEGIN_CAL,
    CMD_MEASURE_BEGIN_SESS, RSP_MEASURE_BEGIN_SESS,
    CMD_MEASURE_END_SESS, RSP_MEASURE_END_SESS,
    EVT_SYSTEM_CONN_READY, EVT_MEASURE_COMPLETE_CAL,
    EVT_SYSTEM_ERROR,
)
from .utils import isiterable
from .packets import is_data_packet, RecievedPacket
from .structures import packet_types
from .communication import (
    ble_event_thread, cmd_to_packet, parse_packet, parse_data_packets, raise_headset_err
)
from .levels import validate_levels, encode_levels, format_levels


def _is_valid_headset(device):
    # Checks whether the given device has a known service UUID
    valid = False
    for uuid in device.metadata['uuids']:
        if uuid in UART_UUIDS.keys():
            valid = True
            break
    return valid


async def _get_headset(devname):
    devices = await BleakScanner.discover(timeout=0.5)
    for d in devices:
        if d.name == devname:
            if _is_valid_headset(d):
                return d
    return None


def get_headset(devname="Axem Pro", timeout=5.0):
    """Retrieves the bluetooth address of the first available headset.

    Args:
        devname (str, optional): The bluetooth device name to search for.
            Defaults to "Axem Pro" if not specified.
        timeout (float, optional): The maximum number of seconds to wait for a
            headset device matching the given name. Defaults to 5 seconds.

    Returns:
        str or None: The unique bluetooth address of the headset, or None if no
        valid headset matching the given name was found before timing out.

    """
    search_start = time.time()
    while (time.time() - search_start) < timeout:
        device = asyncio.run(_get_headset(devname))
        if device:
            return device.address
    return None



class HeadsetInfo(object):
    """A class containing system information about a headset.
    
    """
    def __init__(self, p):
        self._packet = p
        self._measurement_names = None
        self._path_names = None
        self._init_names()

    def _init_names(self):
        # Determines the user-facing names and sequences of the headset's measurements
        # and paths from the system info packet's sequence information
        name_map = {
            POD1: {
                'emitter': {F1: "F3", R1: "R3", S0: "S3", S1: "S1"},
                'detector': {D0: "D3", D1: "D1"},
            },
            POD2: {
                'emitter': {F1: "F4", R1: "R4", S0: "S2", S1: "S4"},
                'detector': {D0: "D2", D1: "D4"},
            },
        }
        paths = []
        measurements = []
        seq = self._packet['sequence']
        for i in range(self.num_measurements):
            pod = seq[i]['pod']
            emitter = name_map[pod]['emitter'][seq[i]['location']]
            wavelength = "LO" if seq[i]['wavelength'] == L740 else "HI"
            measurements.append("_".join([emitter, wavelength]))
            for det in seq[i]['detectors']:
                if det == DX:
                    continue
                detector = name_map[pod]['detector'][det]
                paths.append("_".join([emitter, detector, wavelength]))

        self._measurement_names = tuple(measurements)
        self._path_names = tuple(paths)

    @property
    def uuid(self):
        return self._packet['uuid']

    @property
    def firmware(self):
        p = self._packet
        return (int(p['fw_major']), int(p['fw_minor']), int(p['fw_build']))

    @property
    def paths(self):
        return self._path_names

    @property
    def measurements(self):
        return self._measurement_names

    @property
    def num_paths(self):
        return int(self._packet['num_paths'])

    @property
    def num_measurements(self):
        return int(self._packet['num_measurements'])



class AxemHeadset(object):

    def __init__(self, device):
        self._device = device
        self._from_device = Queue()
        self._to_device = Queue()
        self._ble_thread = None
        self._data_packets = []

        self._packet_version = None
        self._data_struct = None
        self._info = None
        self._levels_set = False
        self._calibrating = False
        self._recording = False

    def connect(self):
        """Initializes communication with the headset.

        This method must be called before the headset can be used.

        """
        # To improve performance (and prevent end users from needing to write
        # code with asyncio), the communication loop sending/recieving packets from
        # the headset is run in a separate thread.
        self._ble_thread = threading.Thread(
            target=ble_event_thread,
            args=(self._device, self._from_device, self._to_device),
            daemon=True
        )
        self._ble_thread.start()

        # Wait for the headset's "System Connection Ready" event
        resp = self._wait_for_packet(EVT_SYSTEM_CONN_READY, timeout=5.0)
        if resp.result != RESULT_SUCCESS:
            print(resp.result)
            raise_headset_err(resp.result, "initializing the headset")

        # Once we're connected, make sure disconnect() get called on main thread exit
        atexit.register(self.disconnect)

        # After connecting successfully, get headset system information
        if not self._info:
            self._init_sysinfo()

        # Currently, the headset starts with calibration disabled for all paths.
        # In order to be able to set up and record with the device, we enable them
        # all as soon as we connect.
        session_rate = b"\x00" # Not used in firmware, but still needed for packet size
        active_fields = struct.pack("Q", 0xFFFF)

        resp = self._send_cmd(CMD_MEASURE_CONFIG_SESS, RSP_MEASURE_CONFIG_SESS, active_fields + session_rate)
        if resp.result != RESULT_SUCCESS:
            raise_headset_err(resp.result, "configuring the headset")

        resp = self._send_cmd(CMD_MEASURE_CONFIG_CAL, RSP_MEASURE_CONFIG_CAL, active_fields)
        if resp.result != RESULT_SUCCESS:
            raise_headset_err(resp.result, "configuring the headset")
        
        #initialize levels at zero
        # self.write_levels(emit_levels=0,gain_levels=0)

    def _init_sysinfo(self):
        """Fetches and parses headset system info for use within the class.

        This is only called once, during initial connection to the headset.

        """
        resp = self._send_cmd(CMD_READ_SYSINFO,RSP_READ_SYSINFO)
        if resp.result != RESULT_SUCCESS:
            raise_headset_err(resp.result, "retrieving headset system information")
        parsed = parse_packet(resp.data, packet_types['sysinfo'])
        self._packet_version = int(parsed['version'])
        self._data_struct = packet_types['data'][self._packet_version]
        self._info = HeadsetInfo(parsed)

    def _check_init(self):
        """Ensures the headset communication thread is active.

        """
        if self._ble_thread == None:
            e = "The connect() method must be called before using the headset."
            atexit.unregister(self.disconnect)
            raise RuntimeError(e)
        elif not self._ble_thread.is_alive():
            e = "The connection to the headset was lost."
            atexit.unregister(self.disconnect)
            raise RuntimeError(e)

    def _pump(self):
        """Fetches new data packets from the headset.

        Any measurement data packets are set aside in a sepearate queue to be
        handled by :meth:`get_path_data`, other packet types are returned
        in a list for processing.

        Returns:
            list of :obj:`RecievedPacket`: A list of any new non-data packets
            received from the headset.
    
        """
        out = []
        while not self._from_device.empty():
            msg = self._from_device.get()
            if is_data_packet(msg['data']):
                self._data_packets.append(msg)
            else:
                p = RecievedPacket(msg['data'])
                self._handle_events(p)
                out.append(p)
        return out

    def _handle_events(self, p):
        if p.type == EVT_MEASURE_COMPLETE_CAL:
            self._levels_set = True
            self._calibrating = False
        elif p.type == EVT_SYSTEM_ERROR:
            # NOTE: Should system errors always be non-fatal, or should some
            # raise an exception?
            e = "Headset encountered an error (code {0})"
            warnings.warn(e.format(p.result), RuntimeWarning)

    def _send_cmd(self, cmd, resp_cmd=None, data=b""):
        """Sends a command packet (and any corresponding data) to the headset.

        Args:
            cmd: The command type to send to the headset.
            data (bytes, optional): The encoded bytes containing the required
                data (if any) for the command. If not specificed, no additional
                data will be sent.

        """
        # NOTE: Should check whether the data is the correct length for the cmd type
        # FIXME: Due to an unknown firmware bug, this sometimes randomly times
        # out without a response. For now we retry twice before raising an
        # error, but this should be removed once the underlying bug is fixed.
        resp = None
        attempts = 0
        while attempts < 10 and not resp:
            if attempts >= 1:
                msg = "Command timed out, retrying..." #FIXME: can we figure out the cmd for a more informative msg here?
                warnings.warn(msg, RuntimeWarning)
            self._to_device.put(cmd_to_packet(cmd, data))
            if resp_cmd is not None:
                resp = self._wait_for_packet(resp_cmd, raise_err=False)
            attempts += 1
        if attempts>1:
            print('Communication with the headset took '+str(attempts)+' attempts.')
        if resp == None:
            raise RuntimeError("Communication with the headset timed out.")
        return(resp)

    def _wait_for_packet(self, ptype, timeout=2.0, raise_err=True):
        """Waits a given duration for a specific response or event packet.

        This method checks the headset queue repeatedly for a packet matching
        the specified type and returns it immediately once found. If a packet of
        the requested type is not received before the timeout occurs, this
        method will either raise an exception (if ``raise_err`` is ``True``) or
        return ``None`` (if ``raise_err`` is ``False``).

        Args:
            ptype (:obj:`PacketType`): The specific response or event packet to
                wait for.
            timeout (float, optional): The duration (in seconds) to wait for the
                packet before timing out. Defaults to 2 seconds.
            raise_err (bool, optional): Whether an exception should be raised if
                a timeout occurs. Defaults to ``True``.
        
        Returns:
            :obj:`RecievedPacket` or NoneType: The awaited packet if it was
            received, otherwise ``None``.

        """
        start = time.time()
        while (time.time() - start) < timeout:
            for p in self._pump():
                if p.type == ptype:
                    return p
        if raise_err:
            # NOTE: Is there a case where we don't want an exception?
            raise RuntimeError("Communication with the headset timed out.")

    def read_levels(self):
        """Reads the current set of emitter and gain levels from the headset.

        Levels are returned in the format ``(emit_levels, gain_levels)``,
        with "emit_levels" being a list of emitter power levels in the order of
        measurements and "gain_levels" being a list of path gain levels in the
        order of paths.

        Returns:
            tuple: The current emitter power and path gain levels for the headset.

        """
        self._check_init()
        resp = self._send_cmd(CMD_MEASURE_READ_CAL,RSP_MEASURE_READ_CAL)
        #FIXME: next two lines are repeated across lots of functions; any way to embed in the _send_cmd while also maintaining informative msg?
        if resp.result != RESULT_SUCCESS:
            raise_headset_err(resp.result, "reading the current levels data")
        parsed = parse_packet(resp.data, packet_types['calibration'])
        return format_levels(parsed, self.info.measurements)

    def write_levels(self, emit_levels, gain_levels):
        """Writes a given set of emitter and gain levels to the headset.

        Emitter levels are per emitter/wavelength, and must all be between
        0 and 512, inclusive. The order of emitter levels should match the
        order of measurement names as per ``AxemHeadset.info.measurements``.

        Gain levels are per path, and must all be between 0 and 5, inclusive.
        The order of gain levels should match the order of path names as per
        ``AxemHeadset.info.paths``.

        Args:
            emit_levels (list or int): The emitter power levels to use for
                each emitter/wavelength combination on the headset. If a single
                value is provided it will be used for all emitters.
            gain_levels (list or int): The gain levels to use for each path
                on the headset. If a single value is provided it will be used
                for all path gains.

        Raises:
            ValueError: If the emitter or gain levels do not match their expected
                lengths, or contain an out-of-range value.

        """
        self._check_init()
        if not isiterable(emit_levels):
            emit_levels = [emit_levels] * self.info.num_measurements
        if not isiterable(gain_levels):
            gain_levels = [gain_levels] * self.info.num_paths
        validate_levels(
            emit_levels, gain_levels, self.info.num_measurements, self.info.num_paths
        )
        cal_bytes = encode_levels(emit_levels, gain_levels, self.info.measurements)
        resp = self._send_cmd(CMD_MEASURE_WRITE_CAL,RSP_MEASURE_WRITE_CAL,cal_bytes)
        if resp.result != RESULT_SUCCESS:
            raise_headset_err(resp.result, "writing levels data to the headset")
        self._levels_set = True

    def calibrate(self):
        """Initiates the headset's self-calibration process.

        Self-calibration can take up to 20 seconds to complete. Calling this method
        will set :attr:`levels_set` to False and :attr:`calibrating` to True.

        """
        self._check_init()
        resp = self._send_cmd(CMD_MEASURE_BEGIN_CAL,RSP_MEASURE_BEGIN_CAL)
        if resp.result != RESULT_SUCCESS:
            raise_headset_err(resp.result, "starting the calibration process")
        self._calibrating = True
        # EVT_CALIBRATION_COMPLETE is sent when calibration finished

    def start_recording(self):
        """Initiates a new recording session with the headset.

        This method can only be called after the headset has had levels set,
        either using self-calibration via :meth:`calibrate` or manually using
        :meth:`write_levels`.

        To end a recording session, use :meth:`stop_recording`.

        """
        self._check_init()
        if self.recording:
            return  # NOTE: does it make sense to raise an error in this case?
        if not self.levels_set:
            raise RuntimeError("Headset must have levels set before recording.")
        resp = self._send_cmd(CMD_MEASURE_BEGIN_SESS,RSP_MEASURE_BEGIN_SESS)
        if resp.result != RESULT_SUCCESS:
            raise_headset_err(resp.result, "starting the recording session")
        self._recording = True

    def stop_recording(self):
        """Ends the current recording session.

        Once this method has been called, you will need to initiate a new session
        using :meth:`start_recording` in order to fetch new path data from the
        headset.

        """
        self._check_init()
        if not self.recording:
            return  # NOTE: does it make sense to raise an error in this case?
        resp = self._send_cmd(CMD_MEASURE_END_SESS,RSP_MEASURE_END_SESS)
        if resp.result != RESULT_SUCCESS:
            raise_headset_err(resp.result, "terminating the recording session")
        self._recording = False

    def get_path_data(self):
        """Retrieves the latest path measurement data from the headset.

        Returns:
            np.recarray: A 2D structured numpy array containing all measurement
            data received since the function was last called.
    
        """
        self._check_init()
        if not self.recording:
            raise RuntimeError("Cannot fetch data unless headset is recording.")
        self._pump() # Check for any new measurement packets from the device
        parsed = parse_data_packets(self._data_packets, self._data_struct)
        self._data_packets = [] # Clear processed packets from queue
        return parsed

    def disconnect(self):
        atexit.unregister(self.disconnect) # Avoid infinite exception loop
        self._check_init()
        if self.recording:
            self._send_cmd(CMD_MEASURE_END_SESS)        
        # Signal communication thread to terminate and wait for confirmation
        shutdown_start = time.time()
        self._to_device.put(b"\x00")
        while self._ble_thread.is_alive():
            time.sleep(0.01)
            if (time.time() - shutdown_start) > 5.0:
                break
        if self._ble_thread.is_alive():
            raise RuntimeError("Communication thread did not shut down sucessfully.")

        # Reset class attributes that shouldn't persist after disconnect
        self._from_device = Queue()
        self._to_device = Queue()
        self._ble_thread = None
        self._data_packets = []
        self._levels_set = False
        self._calibrating = False
        self._recording = False

    @property
    def info(self):
        return self._info

    @property
    def levels_set(self):
        """bool: Whether the headset has levels set and is ready for recording.

        This will be False if the headset is in the process of self-calibration,
        as the headset cannot record until self-calibration is complete.

        """
        self._pump() # Check for EVT_CALIBRATION_COMPLETE in received queue
        return self._levels_set and not self._calibrating

    @property
    def recording(self):
        """bool: Whether the headset is currently recording data.

        """
        return self._recording
