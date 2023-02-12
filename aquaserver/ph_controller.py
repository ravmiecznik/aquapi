#!/usr/bin/python3
import json
import os
import threading
import time
import traceback
import signal
import struct
import requests
import serial
import tempfile
import traceback
import sys
from dataclasses import dataclass, asdict
from enum import IntEnum, Enum, auto
from collections import OrderedDict
from datetime import datetime
import logging
from queue import Queue

LOCK = threading.Lock()

DEPLOY_VERSION = True

SERVER_COMMUNICATION_IPC_NAME = "server_controller.ipc"

class IPC_COMMANDS(Enum):
    PAUSE_CONTROLLER = auto()
    RESUME_CONTROLLER = auto()

    @staticmethod
    def get_by_value(value: int):
        logger.warning(list(IPC_COMMANDS))
        logger.warning(list(IPC_COMMANDS)[value])
        return list(IPC_COMMANDS)[value]


if DEPLOY_VERSION:
    import RPi.GPIO as gpio
else:
    import RPi_fake.GPIO as gpio
    from fake_serial import FakeSerial

logging.basicConfig(format='[%(asctime)s %(levelname)s %(funcName)s t:%(threadName)s p:%(process)d l:%(lineno)d] %(message)s', level=logging.INFO)

logger = logging.getLogger('main')
logger.setLevel(logging.DEBUG)

relay_mapping = [5, 6, 16, 17, 22, 25, 26, 27]

gpio.setmode(gpio.BCM)

for gpio_pin in relay_mapping:
    logger.info(f"setting gpio pin {gpio_pin} as OUT")
    gpio.setup(gpio_pin, gpio.OUT)


def get_relay_pin(relay_num):
    return relay_mapping[relay_num - 1]


CO2_relay_control_pin = 5
CO2_gpio_pin = get_relay_pin(CO2_relay_control_pin)
dir_path = os.path.dirname(os.path.abspath(__file__))
settings_file = os.path.join(dir_path, 'settings.json')
log_file = os.path.join(dir_path, 'log.csv')


default_settings = {
    'day_scheme': {
        'ph_max': 6.9,
        'ph_min': 6.8,
        'start': '07:00',   # datetime format: datetime.strptime('07:00', '%H:%M')
        'end': '19:00'      # datetime format: datetime.strptime('19:00', '%H:%M')
    },
    'night_scheme': {       # night scheme is any other time range than day scheme
        'ph_max': 6.9,
        'ph_min': 6.8,
    },
    'interval': 5,
    "log_flush_period": 600,
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


def dump_settings(settings):
    with open(settings_file, 'w') as f:
        json.dump(settings, f, indent=4)


def set_ph_calibration_values(values: dict):
    settings = get_settings()
    for key in values:
        try:
            settings['ph_calibration'][key] = int(float(values[key]))
        except ValueError as e:
            pass
        else:
            dump_settings(settings)
    



def map_ph(inval, in_min, in_max, out_min, out_max):
    try:
        return (inval - in_min) * (out_max - out_min) / (in_max - in_min) + out_min
    except TypeError:
        return 0


def log_ph(ph, t, log_msg=''):
    print(f"{tstamp()} | PH: {ph} | temperature: {t} | {log_msg} ")


def mkfifo(name):
    os.mkfifo(name)


def ipc_put(data: str):
    if not os.path.exists(SERVER_COMMUNICATION_IPC_NAME):
        mkfifo(SERVER_COMMUNICATION_IPC_NAME)

    # try:
    #     fd = os.open(SERVER_COMMUNICATION_IPC_NAME, os.O_WRONLY | os.O_NONBLOCK)
    #     os.write(bytes(data))
    #     os.close(fd)
    # except BlockingIOError as e:
    #     logger.warning(e)    

    with open(SERVER_COMMUNICATION_IPC_NAME, 'wb') as fifo:
        # logger.info(f"Writing {bytes(data)} {type(data)}")
        fifo.write(bytes(data, encoding='utf-8'))


def ipc_pop():
    data = None
    try:
        fd = os.open(SERVER_COMMUNICATION_IPC_NAME, os.O_RDONLY | os.O_NONBLOCK)
        data = os.read(fd, 100)
        os.close(fd)
    except BlockingIOError as e:
        logger.warning(e)
    return data


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


def get_relays_status():
    return [Relay(gpio.input(relay_number)) for relay_number in relay_mapping ]


class CSVLog:
    def __init__(self, csv_path: str, data: OrderedDict = None, sep=';'):
        logger.info("Init of CSVLog")
        self.__sep = sep
        self.__file_path = csv_path
        self.__log_fd = None
        self.open_log_file_append_mode()
        self.__keep_log_sync = False
        self.__was_header_checked = False
        if data:
            self.header = self.__sep.join(data.keys()) + os.linesep
            self.check_header()
            self.log_data(data)

    def open_log_file_append_mode(self):
        # mean_log_line_len = 30
        # log_fd_buffer_size = mean_log_line_len * 2
        self.__log_fd = open(self.__file_path, 'a')

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
            self.open_log_file_append_mode()
        self.__was_header_checked = True

    def stop_log_sync(self):
        self.__keep_log_sync = False

    def log_data(self, data: dict):
        with LOCK:
            self.check_header(data)
            log_line = self.__sep.join(f"{v}" for v in data.values()) + os.linesep
            self.__log_fd.write(log_line)

    def flush(self):
        logger.info("log flushed")
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
    Decodes PH reading from atmega.
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


class AThread(threading.Thread):
    """Aquapi thread"""
    id = 0

    def __init__(self, target, args=tuple(), kwargs=dict(), period=0, delay=0, verbose=True):
        self.__target = target
        self.__args = args
        self.__kwargs = kwargs
        self.__period = period
        self.__delay = delay
        self.__work_flag = threading.Event()
        self.__work_flag.set()
        self._verbose = verbose
        threading.Thread.__init__(self)
        self.name = target.__name__ + f"_{self.id}"
        self.id += 1

    def call_target(self):
        if self._verbose:
            logger.info(f"{self.__target.__name__, self.__args, self.__kwargs}")
        self.__target(*self.__args, **self.__kwargs)

    def set_period(self, period):
        self.__period = period

    def run(self) -> None:
        time.sleep(self.__delay)
        self.call_target()
        while self.__period and self.__work_flag.isSet():
            self.call_target()
            for _ in range(self.__period):
                time.sleep(1)
                if not self.__period:
                    break
    
    def pause(self):
        self.__work_flag.clear()

    def resume(self):
        self.__work_flag.set()

    def kill(self):
        self.__period = None


class AquapiController:
    """Checks and controls PH with CO2 relay"""

    def __init__(self, settings=AttrDict(get_settings())):
        self.settings = settings
        self.ph_probe_dev = AttrDict(dict(dev='/dev/ttyS0', baudrate=9600, timeout=2))
        self.get_samples_cmd = b'r'  # raw reading
        self.ph_prev = self.get_ph_human_readable()
        self.ph_averaging_array = [self.ph_prev, self.ph_prev]
        self.ph_averaging_index = 0
        self.csv_log = CSVLog(csv_path=log_file)
        self.collect_data()

        self.sync_job = True
        self.interval = self.settings.interval
        self.sync_log_file_thread = AThread(self.csv_log.flush, period=self.settings.log_flush_period, delay=10)
        self.main_loop_thread = AThread(self.aquapi_main, period=self.interval)
        self.poll_ipc_pipe_thread = AThread(self.poll_ipc, period=1, verbose=False)
        self.poll_ipc_pipe_thread.start()

    def kill(self, *args, **kwargs):
        logger.info(f"caught signal: {args, kwargs}")
        self.sync_log_file_thread.kill()
        self.main_loop_thread.kill()
        self.csv_log.flush()
        self.poll_ipc_pipe_thread.kill()
        sys.exit(0)

    def start_sync_threads(self):
        self.sync_log_file_thread.start()
        self.main_loop_thread.start()
    
    def get_ph_human_readable(self):
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

    def pause_controller_threads(self):
        logger.info("Pause threads")
        self.sync_log_file_thread.pause()
        self.main_loop_thread.pause()

    def resume_controller_threads(self):
        logger.info("Resume threads")
        self.sync_log_file_thread.resume()
        self.main_loop_thread.resume()

    def get_ph_raw(self):
        if DEPLOY_VERSION:
            serial_opts = dict(**self.ph_probe_dev)
            ph_serial = serial.Serial(serial_opts.pop('dev'), **serial_opts)
        else:
            ph_serial = FakeSerial()
        ph_serial.write(self.get_samples_cmd)
        resp = ph_serial.read(PhDecoder.frame_size)
        samples_avg = PhDecoder(resp).get()
        ph_serial.close()
        return samples_avg

    def get_ph(self):
        ph_callib = self.settings.ph_calibration
        samples_avg = self.get_ph_raw()
        ph = map_ph(samples_avg, ph_callib["4"], ph_callib["7"], 4, 7)
        return ph

    def get_ph_average(self):
        """Calculates average PH with use of averaging array"""
        ph_new = self.get_ph_human_readable()
        if ph_new <= 14:
            ph_avg = sum(self.ph_averaging_array) / len(self.ph_averaging_array)
            self.ph_averaging_array[self.ph_averaging_index] = ph_new
            self.ph_averaging_index += 1
            self.ph_averaging_index %= len(self.ph_averaging_array)
        else:
            # get last sample only, ph > 14 means measurement error, don't use this !
            ph_avg = self.ph_averaging_array[self.ph_averaging_index]
        return ph_avg

    @staticmethod
    def __switch_co2_relay(relay_value: Relay):
        relay_status = Relay(gpio.input(CO2_gpio_pin))
        if relay_value != relay_status:
            gpio.output(CO2_gpio_pin, relay_value)

    def __get_expected_ph(self):
        now = datetime.now()
        now_format = '%H:%M'
        datetime_now = datetime.strptime(f'{now.hour}:{now.minute}', now_format)
        datetime_day_scheme_start = datetime.strptime(self.settings.day_scheme.start, now_format)
        datetime_day_scheme_end = datetime.strptime(self.settings.day_scheme.end, now_format)
        logger.info(f"now: {datetime_now:%H:%M}, day start: {datetime_day_scheme_start:%H:%M}, day end: {datetime_day_scheme_end:%H:%M}")
        if datetime_now > datetime_day_scheme_start and datetime_now < datetime_day_scheme_end:
            ph_min, ph_max = self.settings.day_scheme.ph_min, self.settings.day_scheme.ph_max
            logger.info('day scheme in use')
        else:
            ph_min, ph_max = self.settings.night_scheme.ph_min, self.settings.night_scheme.ph_max
            logger.info('day scheme not in use')
        return ph_min, ph_max

    def monitor_ph(self):
        """Measure PH and control CO2 relay based on PH min and max values in settings file."""
        ph_avg = self.get_ph_average()
        ph_min, ph_max = self.__get_expected_ph()
        logger.info(f"ph_min:{ph_min}, ph_max{ph_max}")
        if ph_avg <= ph_min:
            self.__switch_co2_relay(Relay.OFF)
        elif ph_avg >= ph_max:
            self.__switch_co2_relay(Relay.ON)
        if DEPLOY_VERSION:
            return round(ph_avg, 2)
        else:
            return 7.1

    def update_settings(self):
        self.settings = AttrDict(get_settings())
        if self.settings.interval != self.interval:
            self.interval = self.settings.interval
            self.main_loop_thread.set_period(self.interval)

    def stop(self):
        self.__run = False

    def collect_data(self):
        temperature = get_temperature()
        ph_avg = self.monitor_ph()
        relay_status = 1-Relay(gpio.input(CO2_gpio_pin))
        log_record = LogRecord(tstamp(), ph_avg, temperature, relay_status)
        logger.info(log_record)

        self.csv_log.log_data(data=dict(timestamp=log_record.timestamp,
                                               ph=f"{log_record.ph:.2f}",
                                               temperature=log_record.temperature,
                                               relay=log_record.relay))
        log_record = LogRecord(tstamp(), ph_avg, temperature, relay_status * 6.5)
        return log_record


    def poll_ipc(self):
        """
        Get data from inter process communication pipe: server -> ph_controller
        """
        # if self.communication_queue.qsize():
        #     data = self.communication_queue.get(block=True, timeout=2)
        #     logger.info(f"got data: {data}")

        data = ipc_pop()
        if data:
            data = data.decode("utf-8")
            logger.info(f"got data {data}")
            self.handle_ipc_command(data)
            # self.communication_queue.put(data_as_int, block=True, timeout=2)

    def handle_ipc_command(self, command: IPC_COMMANDS):
        logger.info(f"got data {command}")
        try:
            {
                IPC_COMMANDS.PAUSE_CONTROLLER.name: self.pause_controller_threads,
                IPC_COMMANDS.RESUME_CONTROLLER.name: self.resume_controller_threads,
            }[command]()
        except KeyError as e:
            logger.error(e)



    def aquapi_main(self):
        """
        aquapi main
        :return:
        """
        try:
            log_record = self.collect_data()
            requests.post('http://0.0.0.0:5000/post_data_frame', json=json.dumps(asdict(log_record)))
        except Exception as e:
            print(e)
            traceback.print_exc()
        self.update_settings()


def controller_get_calibration_data():
    ac = AquapiController()
    return json.dumps(
        {
            'ph': round(ac.get_ph(), 2),
            'ph_raw': round(ac.get_ph_raw())
        }
    )

def main():
    aquapi_controller = AquapiController()
    aquapi_controller.start_sync_threads()
    signal.signal(signal.SIGINT, aquapi_controller.kill)
    signal.signal(signal.SIGTERM, aquapi_controller.kill)


if __name__ == "__main__":
    main()
