# IIAE Unified Test Namespace
# Importing all tests to allow pytest to collect and execute them directly via:
# pytest run_all_tests.py

from tests.test_annex_r import *
from tests.test_ds_accuracy import *
from tests.test_r4_immutability import *
from tests.test_r5_replay_resistance import *
from tests.test_r6_reconstructibility import *
from tests.test_use_cases import *
from SLT.SLT_pyTest import *
