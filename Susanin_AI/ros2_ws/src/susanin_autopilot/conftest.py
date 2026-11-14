"""Позволяет запускать тесты пакета обычным pytest без сборки colcon."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
