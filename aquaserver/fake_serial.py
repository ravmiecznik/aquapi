#!/usr/bin/python
"""
author: Rafal Miecznik
contact: ravmiecznk@gmail.com
created: 16.10.2021$
"""


class FakeSerial:

    def write(self, *args, **kwargs):
        pass

    def read(self, *args, **kwargs):
        return b'11111'

    def close(self):
        pass