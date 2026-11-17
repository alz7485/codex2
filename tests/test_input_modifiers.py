import unittest
from unittest.mock import patch,MagicMock
from catalog_studio.input_modifiers import physical_alt_down

class InputModifiersTests(unittest.TestCase):
 def test_windows_only_uses_physical_high_bit(self):
  query=MagicMock();library=MagicMock();library.GetAsyncKeyState=query
  with patch('sys.platform','win32'),patch('ctypes.WinDLL',return_value=library,create=True):
   for result,expected in [(0,False),(1,False),(0x8000,True),(-32768,True)]:
    query.return_value=result
    self.assertEqual(physical_alt_down(),expected)
    query.assert_called_with(0x12)
 def test_non_windows_does_not_load_windows_library(self):
  with patch('sys.platform','linux'),patch('ctypes.WinDLL',create=True) as load:
   self.assertIsNone(physical_alt_down());load.assert_not_called()
