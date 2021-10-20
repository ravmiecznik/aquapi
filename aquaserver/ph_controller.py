#!/usr/bin/python3
import json
import os
import threading
import time
import traceback
import struct
import requests
import serial
import tempfile
import traceback
from dataclasses import dataclass, asdict
from enum import IntEnum
from collections import OrderedDict
from datetime import datetime
import logging

LOCK = threading.Lock()

DEPLOY_VERSION = True

if DEPLOY_VERSION:
    import RPi.GPIO as gpio
else:
    import RPi_fake.GPIO as gpio
    from fake_serial import FakeSerial

logging.basicConfig(format='%(asctime)s::%(levelname)s::%(funcName)s::%(lineno)d:%(message)s', level=logging.INFO)

logger = logging.getLogger('main')


def get_relay_pin(relay_num):
    return relay_mapping[relay_num - 1]


relay_mapping = [5, 6, 16, 17, 22, 25, 26, 27]
CO2_relay_control_pin = 5
CO2_gpio_pin = get_relay_pin(CO2_relay_control_pin)
dir_path = os.path.dirname(os.path.abspath(__file__))
settings_file = os.path.join(dir_path, 'settings.json')
log_file = os.path.join(dir_path, 'log.csv')
gpio.setmode(gpio.BCM)

default_settings = {
    'ph_max': 6.9,
    'ph_min': 6.8,
    'interval': 60,
    'kh': 6,
    'ph_calibration': {
        7: 394,
        4: 337,
    }
}


class Relay(IntEnum):
    ON = gpio.LOW
    OFF = gpio.HIGH


class AttrDict(dict):
    def __getattr__(self, item):
        if item in self:
            if issubclass(type(self[item]), dict):
                return AttrDict(self[item])
            else:
                return self[item]
        else:
            raise AttributeError(f"No such item: {item}")


def tstamp():
    return f"{datetime.now():%Y-%m-%d %H:%M:%S}"


def get_settings():
    try:
        with open(settings_file) as f:
            return json.loads(f.read())
    except FileNotFoundError:
        with open(settings_file, 'w') as f:
            json.dump(default_settings, f, indent=4)
            return get_settings()


def map_ph(inval, in_min, in_max, out_min, out_max):
    return (inval - in_min) * (out_max - out_min) / (in_max - in_min) + out_min


def log_ph(ph, t, log_msg=''):
    print(f"{tstamp()} | PH: {ph} | temperature: {t} | {log_msg} ")


if DEPLOY_VERSION is False:
    temp = 0


def get_temperature():
    if DEPLOY_VERSION:
        # TODO: make w1 device id automatic detection
        return int(open('/sys/bus/w1/devices/28-0117c1365eff/temperature').read()) / 1000
    else:
        global temp
        temp = (temp + 1) % 10
        return 20 + (temp + 1)


class CSVLog:
    def __init__(self, csv_path: str, data: OrderedDict = None, sep=';'):
        logger.info("Init of CSVLog")
        mean_log_line_len = 30
        self.__sep = sep
        self.__file_path = csv_path
        self.__log_fd = open(self.__file_path, 'a', buffering=mean_log_line_len * 100)
        self.__keep_log_sync = False
        self.__was_header_checked = False
        if data:
            with LOCK:
                self.header = self.__sep.join(data.keys()) + os.linesep
                self.check_header()
                self.log_data(data)

    def check_header(self, data):
        if not self.__was_header_checked:
            self.header = self.__sep.join(data.keys()) + os.linesep
            self.__log_fd.close()
            self.__log_fd = open(self.__file_path, 'r')
            header = self.__log_fd.readline()
            if header != self.header:
                self.__log_fd.seek(0)
                content = self.__log_fd.read()
                self.__log_fd.close()
                self.__log_fd = open(self.__file_path, 'w')
                self.__log_fd.write(self.header)
                self.__log_fd.write(content)
        self.__log_fd.close()
        self.__log_fd = open(self.__file_path, 'a')
        self.__was_header_checked = True

    def stop_log_sync(self):
        self.__keep_log_sync = False

    def log_data(self, data: OrderedDict):
        logger.info("log add")
        self.check_header(data)
        self.__log_fd.write(self.__sep.join(f"{v}" for v in data.values()) + os.linesep)

    def flush(self):
        self.__log_fd.flush()


def column_to_json_friendly(col):
    try:
        return round(float(col), 2)
    except ValueError:
        return col


class CSVParser:
    def __init__(self, csv_path, sep=';', step=1, reduce_lines=None, samples_range=None):
        if type(csv_path) == tempfile._TemporaryFileWrapper:
            self.__temp_file = csv_path  # keep it alive
            csv_path = self.__temp_file.name
        self.__csv_path = csv_path
        self.__sep = sep
        self.header = self.get_header()
        if reduce_lines:
            self.__step = self.lines_count() // reduce_lines
        else:
            self.__step = step
        self.__slice = slice(0, None)
        if samples_range:
            if ':' in samples_range:
                start, stop = list(map(int, samples_range.split(':')))
            else:
                start = int(samples_range)
                stop = None
            self.__slice = slice(start, stop)

    @classmethod
    def from_bytes(cls, content, **kwargs):
        temp_file = tempfile.NamedTemporaryFile(mode='w+b')
        temp_file.write(content)
        return cls(temp_file, **kwargs)

    def lines_count(self):
        count = 0
        with open(self.__csv_path) as f:
            f.readline()
            for _ in f:
                count += 1
        return count

    def get_header(self):
        with open(self.__csv_path) as f:
            header = f.readline().strip()
        return header.split(self.__sep)

    def get_rows(self):
        rows = list()
        with open(self.__csv_path) as f:
            f.readline()
            for i, line in enumerate(f):
                if not (i % self.__step):
                    rows.append(line.split(self.__sep))
        return rows[self.__slice]

    def get_column(self, index):
        column = list()
        with open(self.__csv_path) as f:
            f.readline()
            for i, line in enumerate(f):
                if not (i % self.__step):
                    column.append(line.strip().split(self.__sep)[index])
        return column[self.__slice]

    def get_columns(self, *indexes):
        columns = [list() for _ in indexes]
        with open(self.__csv_path) as f:
            f.readline()
            lines = f.readlines()[self.__slice]
            for i, line in enumerate(lines):
                if not (i % self.__step):
                    cols = line.strip().split(self.__sep)
                    cols = list(map(column_to_json_friendly, cols))
                    [columns[i].append(cols[j]) for i, j in enumerate(indexes)]
        return columns

    def get_columns_by_name(self, *columns):
        indexes = [self.header.index(column_name) for column_name in columns]
        columns_by_indexes = self.get_columns(*indexes)
        columns_by_name = dict()
        for i, column in enumerate(columns):
            columns_by_name[column] = columns_by_indexes[i]
        return columns_by_name

    def __getattr__(self, item):
        col_index = self.header.index(item)
        return self.get_column(col_index)

    def __getitem__(self, item):
        col_index = self.header.index(item)
        return self.get_column(col_index)

    def get_data_as_dict(self):
        return self.get_columns_by_name(*self.header)

    def jsonify(self):
        return json.dumps(self.get_columns_by_name(*self.header))


def crc(buffer):
    _crc = 0
    for i in buffer:
        _crc = crc_xmodem(_crc, i)
    return struct.pack('H', _crc)


def crc_xmodem(_crc, data):
    _crc = 0xffff & (_crc ^ (data << 8))
    for i in range(0, 8):
        if _crc & 0x8000:
            _crc = 0xffff & ((_crc << 1) ^ 0x1021)
        else:
            _crc = (0xffff & (_crc << 1))
    return _crc


"""
https://docs.python.org/3/library/struct.html

FORMAT      C Type          Python Type         Standard Size
-------------------------------------------------------------
h           short           integer             2
H           unsigned short  integer             2
b           signed char     integer             1
B           unsigned char   integer             1
...and more
"""


class CStructMapper:
    def __init__(self, raw_buffer, crc_len=2):
        self.__raw_buffer = raw_buffer
        self.__data = raw_buffer[0:-crc_len]
        self.__crc = raw_buffer[-crc_len:]

    def check_crc(self):
        return crc(self.__data) == self.__crc

    @property
    def raw_data(self):
        return self.__data


class PhDecoder(CStructMapper):
    """
    PH sample struct:
    uint16_t samples_sum;  LOW_BYTE|HI_BYTE
    uint8_t samples_count;
    """
    frame_size = 2 + 1 + 2

    @property
    def samples_sum(self):
        return struct.unpack('H', self.raw_data[0:2])[0]

    @property
    def samples_count(self):
        return self.raw_data[2]

    def get(self):
        return self.samples_sum / self.samples_count


@dataclass
class LogRecord:
    timestamp: str
    ph: float
    temperature: float
    relay: Relay


class AquapiController:
    def __init__(self, settings=AttrDict(get_settings())):
        self.settings = settings
        self.ph_probe_dev = AttrDict(dict(dev='/dev/ttyS0', baudrate=9600, timeout=2))
        self.get_samples_cmd = b'r'  # raw reading
        gpio.setup(CO2_gpio_pin, gpio.OUT)
        self.ph_prev = self.get_ph()
        self.ph_averaging_array = [self.ph_prev, self.ph_prev]
        self.ph_averaging_index = 0
        self.csv_log = CSVLog(csv_path=log_file)
        self.collect_data()
        self.csv_log.flush()
        self.__run = True

    def get_ph(self):
        ph_callib = self.settings.ph_calibration
        if DEPLOY_VERSION:
            serial_opts = dict(**self.ph_probe_dev)
            ph_serial = serial.Serial(serial_opts.pop('dev'), **serial_opts)
        else:
            ph_serial = FakeSerial()
        ph_serial.write(self.get_samples_cmd)
        resp = ph_serial.read(PhDecoder.frame_size)
        samples_avg = PhDecoder(resp).get()
        ph = map_ph(samples_avg, ph_callib["4"], ph_callib["7"], 4, 7)
        ph_serial.close()
        return ph

    def check_ph(self):
        relay_status = Relay(gpio.input(CO2_gpio_pin))
        ph_new = self.get_ph()
        if ph_new < 14:
            ph_avg = sum(self.ph_averaging_array) / len(self.ph_averaging_array)
            self.ph_averaging_array[self.ph_averaging_index] = ph_new
            self.ph_averaging_index += 1
            self.ph_averaging_index %= len(self.ph_averaging_array)
        else:
            ph_avg = self.ph_averaging_array[self.ph_averaging_index]

        if ph_avg <= self.settings.ph_min and relay_status == Relay.ON:
            gpio.output(CO2_gpio_pin, Relay.OFF)
        elif ph_avg >= self.settings.ph_max and relay_status == Relay.OFF:
            gpio.output(CO2_gpio_pin, Relay.ON)
        if DEPLOY_VERSION:
            return ph_avg
        else:
            return 7.1

    def update_settings(self):
        self.settings = AttrDict(get_settings())

    def stop(self):
        self.__run = False

    @staticmethod
    def post_data_to_server():
        tries = 5
        while tries:
            try:
                data = CSVParser(log_file).jsonify()
                data['relay'] = [(1-d)*6.5 for d in data['relay']]
                # data = json.dumps(data)
                resp = requests.post('http://0.0.0.0:5000/postaquapidata', json=data)
                logger.info(resp.status_code)
                with open('resp.html', 'w') as f:
                    f.write(resp.content.decode())
                return True
            except (ConnectionError, KeyError) as e:
                time.sleep(5)
                tries -= 1
                traceback.print_exc()
        else:
            raise Exception("Post data failure")

    def collect_data(self):
        temperature = get_temperature()
        ph_avg = self.check_ph()
        relay_status = Relay(gpio.input(CO2_gpio_pin))
        log_record = LogRecord(tstamp(), ph_avg, temperature, relay_status)
        logger.info(f"relay {relay_status}")
        logger.info(log_record)

        self.csv_log.log_data(data=dict(timestamp=log_record.timestamp,
                                               ph=f"{log_record.ph:.2f}",
                                               temperature=log_record.temperature,
                                               relay=1 - log_record.relay))
        log_record = LogRecord(tstamp(), ph_avg, temperature, (1 - relay_status) * 6.5)
        return log_record

    def run(self):
        self.post_data_to_server()
        while self.__run:
            try:
                log_record = self.collect_data()
                requests.post('http://0.0.0.0:5000/post_data_frame', json=json.dumps(asdict(log_record)))
            except Exception as e:
                print(e)
                traceback.print_exc()
            time.sleep(self.settings.interval)
            self.update_settings()


def main():
    AquapiController().run()


if __name__ == "__main__":
    main()
