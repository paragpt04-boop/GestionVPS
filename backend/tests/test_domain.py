import unittest
from domain import delta, validate_client, safe_filename
from qos import parse

class Validation(unittest.TestCase):
    def test_names_do_not_become_paths(self):
        self.assertEqual(validate_client({'name':'Jesús / Miami 😎'})[0],'Jesús / Miami 😎')
        self.assertNotIn('/',safe_filename('../../Jesús'))
    def test_bad_rates(self):
        for rate in [0,-1,1001,True,'2',2.5]:
            with self.assertRaises(ValueError): validate_client({'name':'test','download_mbps':rate})
    def test_control_characters(self):
        with self.assertRaises(ValueError): validate_client({'name':'hola\nPrivateKey = x'})
    def test_legacy_and_independent_qos(self):
        self.assertEqual(parse('10.5.0.2\n10.5.0.3 10 4\n'),[('10.5.0.2',2,1),('10.5.0.3',10,4)])
    def test_invalid_qos_rejected_before_apply(self):
        for text in ['10.5.0.1','10.5.0.255','10.5.1.2','10.5.0.2\n10.5.0.2','10.5.0.2 2 0','10.5.0.2;reboot','10.5.0.2 5']:
            with self.assertRaises(ValueError): parse(text)
    def test_counter_reset(self):
        self.assertEqual(delta(100,150),50)
        self.assertEqual(delta(100,20),20)
        self.assertEqual(delta(100,150,False),150)

if __name__=='__main__': unittest.main()
