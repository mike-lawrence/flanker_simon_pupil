import numpy as np
from .constants import *


# BLEAPIFrameHeaderTypeDef
header_struct = np.dtype([
    ('preamble', np.uint16),
    ('len', np.uint8),
    ('ptype', np.uint8),
    ('pclass', np.uint8),
    ('pcmd', np.uint8),
])

# sequence_object_t
pod_struct = np.dtype([
    ('pod', np.uint8),
    ('active', np.uint8),
    ('location', np.uint8),
    ('wavelength', np.uint8),
    ('detectors', np.uint8, (2, )),
])

# SBDATBatteryDataTypeDef
battery_data_struct = np.dtype([
    ('remaining_mah', np.uint16),
    ('remaining_mins', np.uint16),
    ('voltage', np.uint16),
    ('avg_current', np.int16),
    ('status', np.uint16),
    ('cycle_count', np.uint16),
])


packet_types = {}

# SystemInfoTypeDef
packet_types['sysinfo'] = np.dtype([
    ('version', np.uint16),
    ('uuid', np.uint8, (12, )),
    ('num_boots', np.uint32),
    ('fw_major', np.uint8),
    ('fw_minor', np.uint8),
    ('fw_build', np.uint32),
    ('sequence', pod_struct, (NUM_MEASUREMENTS, )),
    ('num_paths', np.uint8),
    ('num_measurements', np.uint8),
])

# bleapi_cmd_meas_write_cal_t
packet_types['calibration'] = np.dtype([
    ('attenuations', np.uint16, (NUM_MEASUREMENTS, )),
    ('gains', np.uint8, (NUM_MEASUREMENTS, 2)),
])

# bleapi_evt_batt_status_t
packet_types['battery_event'] = np.dtype([
    ('voltage', np.uint16),
    ('current', np.int16),
    ('repsoc', np.uint16),
    ('tte', np.uint16),
    ('cycles', np.uint16),
    ('age', np.uint16),
    ('temp', np.int16),
])

# imu_data_t
packet_types['accelerometer'] = np.dtype([
    ('quaternion', np.int16, (4, )),  # (w, x, y, z)
    ('linaccel', np.int16, (3, )),    # (x, y, z)
    ('gravity', np.int16, (3, )),     # (x, y, z)
])

packet_types['data'] = {
    MEASUREMENT_PACKET_V1: np.dtype([
        ('sample', np.uint32),
        ('paths', np.int16, (NUM_PATHS, )),
        ('checksum', np.uint16),
    ]),
    MEASUREMENT_PACKET_V2: np.dtype([
        ('sample', np.uint32),
        ('paths', np.int16, (NUM_PATHS, )),
        ('overflow_flags', np.uint64),
        ('heartbeat_flags', np.uint64),
        ('checksum', np.uint16),
    ]),
    MEASUREMENT_PACKET_V3: np.dtype([
        ('sample', np.uint32),
        ('paths', np.int16, (NUM_PATHS, )),
        ('overflow_flags', np.uint64),
        ('heartbeat_flags', np.uint64),
        ('batt_info', battery_data_struct),
        ('checksum', np.uint16),
    ]),
    MEASUREMENT_PACKET_V7: np.dtype([
        ('sample', np.uint32),
        ('paths', np.int16, (NUM_PATHS, )),
        ('overflow_flags', np.uint64),
        ('heartbeat_flags', np.uint64),
        ('cal_updates_pod1', np.uint8),
        ('cal_updates_pod2', np.uint8),
        ('checksum', np.uint16),
    ]),
}

# FIXME: Hack to support older WIP firmware, remove when no longer needed
packet_types['data'][0x0010] = packet_types['data'][MEASUREMENT_PACKET_V7]
