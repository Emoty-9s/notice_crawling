"""Provisional KISTA contract tests; raw HTTP fixtures remain a blocker."""
import unittest
from _m16_cases import M16ContractCases


class KistaContractTests(M16ContractCases, unittest.TestCase):
    source = 'kista_ippro'
