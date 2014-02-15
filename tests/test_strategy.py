"""

"""
import time
from datetime import datetime
import unittest
from flask.ext.limiter.limits import PER_SECOND, PER_DAY, PER_HOUR, PER_MONTH, \
    PER_MINUTE, PER_YEAR
from flask.ext.limiter.util import find_windows


class WindowTests(unittest.TestCase):
    def setUp(self):
        self.ref_time = 1392347512.400
        t = datetime.fromtimestamp(self.ref_time)
        self.year, self.month, self.day, self.hour, self.minute, self.second, _, _, _ = t.timetuple()

    def test_second_window(self):
        self.assertEqual(find_windows(self.ref_time, PER_SECOND(1, 3)),
                         [(datetime(self.year, self.month, self.day, self.hour,
                                    self.minute, self.second)),
                          (datetime(self.year, self.month, self.day, self.hour,
                                    self.minute, self.second - 1)),
                          (datetime(self.year, self.month, self.day, self.hour,
                                    self.minute, self.second - 2)),
                         ]
        )
    def test_minute_window(self):
        self.assertEqual(find_windows(self.ref_time, PER_MINUTE(1, 3)),
                         [(datetime(self.year, self.month, self.day, self.hour,
                                    self.minute, 0)),
                          (datetime(self.year, self.month, self.day, self.hour,
                                    self.minute - 1, 0)),
                          (datetime(self.year, self.month, self.day, self.hour,
                                    self.minute - 2, 0))
                          ]
        )
    def test_hour_window(self):
        self.assertEqual(find_windows(self.ref_time, PER_HOUR(1, 3)),
                         [(datetime(self.year, self.month, self.day, self.hour,
                                    0, 0)),
                          (datetime(self.year, self.month, self.day,
                                    self.hour - 1,
                                    0, 0)),
                          (datetime(self.year, self.month, self.day,
                                    self.hour - 2,
                                    0, 0)),
                         ]
        )
