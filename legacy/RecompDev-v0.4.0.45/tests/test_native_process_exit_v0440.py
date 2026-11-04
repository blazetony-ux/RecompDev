"""Persistent process exit diagnoses must survive missing stdout/stderr."""
import unittest
from nativepilot.engine import classify_native_process_exit

class NativeProcessExitTests(unittest.TestCase):
 def test_windows_stack_overflow_signed(self):
  msg=classify_native_process_exit(-1073741571,'','')
  self.assertIn('HOST_STACK_OVERFLOW',msg)
  self.assertIn('exit_hex=0xC00000FD',msg)
  self.assertIn('exit_signed=-1073741571',msg)
 def test_windows_stack_overflow_unsigned(self):
  self.assertIn('HOST_STACK_OVERFLOW',classify_native_process_exit(0xc00000fd))
 def test_ordinary_nonzero(self):
  self.assertIn('NATIVE_PROCESS_NONZERO_EXIT',classify_native_process_exit(7,'','bad'))
  self.assertIn('output=bad',classify_native_process_exit(7,'','bad'))
 def test_zero_exit_no_error(self):
  self.assertIsNone(classify_native_process_exit(0,'',''))

if __name__=='__main__': unittest.main()
