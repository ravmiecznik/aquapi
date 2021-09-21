#!/usr/bin/python3 -u

import json
import os
import time
import traceback
from collections import OrderedDict
from datetime import datetime
from enum import IntEnum

import serial

import RPi.GPIO as gpio
# from RPi import GPIO as gpio
from serial_read import read_till_eot


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


def get_temperature():
    return int(open('/sys/bus/w1/devices/28-0117c1365eff/temperature').read()) / 1000


class CSVLog:
    def __init__(self, csv_path: str, data: OrderedDict, sep=';'):
        self.__sep = sep
        self.header = self.__sep.join(data.keys()) + os.linesep
        self.__file_path = csv_path
        self.check_header()
        self.log_data(data)

    def init_file(self):
        with open(self.__file_path, 'w') as f:
            f.write(self.header)

    def check_header(self):
        if not os.path.isfile(self.__file_path):
            self.init_file()
        with open(self.__file_path) as f:
            header = f.readline(5000)
        if header != self.header:
            with open(self.__file_path) as f:
                content = (line for line in f.readlines() if len(line) > 2)
            self.init_file()
            with open(self.__file_path, 'a') as f:
                f.write(os.linesep.join(content))

    def log_data(self, data: OrderedDict):
        with open(self.__file_path, 'a') as f:
            f.write(self.__sep.join(f"{v}" for v in data.values()) + os.linesep)


class AquapiController:
    def __init__(self, settings=AttrDict(get_settings())):
        self.settings = settings
        self.ph_probe_dev = AttrDict(dict(dev='/dev/ttyS0', baudrate=9600, timeout=2))
        self.get_samples_cmd = b's'
        gpio.setup(CO2_gpio_pin, gpio.OUT)
        self.ph_prev = self.get_ph()
        self.ph_averaging_array = [self.ph_prev, self.ph_prev]
        self.ph_averaging_index = 0
        self.__run = True

    def get_ph(self):
        ph_callib = self.settings.ph_calibration
        serial_opts = dict(**self.ph_probe_dev)
        ph_serial = serial.Serial(serial_opts.pop('dev'), **serial_opts)
        ph_serial.write(self.get_samples_cmd)
        samples_sum = int(read_till_eot(ph_serial))
        samples_avg = samples_sum / 20
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
        return ph_avg

    def update_settings(self):
        self.settings = AttrDict(get_settings())

    def stop(self):
        self.__run = False

    def run(self):
        while self.__run:
            try:
                temperature = get_temperature()
                ph_avg = self.check_ph()
                relay_status = Relay(gpio.input(CO2_gpio_pin))
                CSVLog(csv_path=log_file,
                       data=OrderedDict(timestamp=tstamp(),
                                        ph=f"{ph_avg:.2f}",
                                        temperature=temperature,
                                        relay=1-relay_status))
            except Exception as e:
                traceback.print_exc()
            time.sleep(self.settings.interval)
            self.update_settings()


def main():
    AquapiController().run()


if __name__ == "__main__":
    main()
