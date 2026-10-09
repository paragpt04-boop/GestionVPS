"""No host network mutations: validate failure recovery against a fake runtime."""
import pathlib
import tempfile
import unittest
from unittest.mock import patch
import agent

class Transactions(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        root=pathlib.Path(self.temp.name)
        self.patches=[patch.object(agent,'ROOT',root/'state'),patch.object(agent,'WG',root/'wg0.conf'),patch.object(agent,'QOS',root/'qos.txt'),patch.object(agent,'CLIENTS',root/'clients'),patch.object(agent,'collect')]
        for p in self.patches:p.start()
        agent.CLIENTS.mkdir()
        agent.WG.write_text('[Interface]\nPrivateKey = fake-server\nAddress = 10.5.0.1/24\n\n[Peer]\nPublicKey = fake-client\nAllowedIPs = 10.5.0.2/32\n')
        agent.QOS.write_text('10.5.0.2\n')
        (agent.CLIENTS/'jesus.conf').write_text('[Interface]\nPrivateKey = fake\nAddress = 10.5.0.2/32\n')
        agent.initialize()
        with agent.db() as c:self.id=c.execute('SELECT id FROM clients').fetchone()[0]
    def tearDown(self):
        for p in reversed(self.patches):p.stop()
        self.temp.cleanup()
    def test_failed_runtime_restores_files_and_database(self):
        before=agent.WG.read_text(),agent.QOS.read_text()
        with patch.object(agent,'apply_qos'),patch.object(agent,'sync_runtime',side_effect=[RuntimeError('injected failure'),None]):
            with self.assertRaises(RuntimeError):agent.mutate('update',{'id':self.id,'name':'changed','download_mbps':7,'upload_mbps':4})
        self.assertEqual((agent.WG.read_text(),agent.QOS.read_text()),before)
        with agent.db() as c:self.assertEqual(c.execute('SELECT name FROM clients').fetchone()[0],'jesus')
        self.assertFalse((agent.ROOT/'pending.json').exists())
    def test_success_persists_and_survives_reinitialize(self):
        with patch.object(agent,'apply_qos'),patch.object(agent,'sync_runtime'):
            agent.mutate('update',{'id':self.id,'name':'Nombre libre ñ','download_mbps':7,'upload_mbps':4})
        agent.initialize()
        with agent.db() as c:
            row=c.execute('SELECT * FROM clients').fetchone()
            self.assertEqual((row['name'],row['down'],row['up']),('Nombre libre ñ',7,4))
        self.assertIn('10.5.0.2 7 4',agent.QOS.read_text())
