import datetime as dt
import unittest
from unittest.mock import patch
import agent
import plans
import test_agent


class Calendar(unittest.TestCase):
    def test_month_end_returns_to_original_day_after_short_month(self):
        stamp=lambda y,m,d:int(dt.datetime(y,m,d,12,tzinfo=dt.timezone.utc).timestamp())
        anchor=stamp(2024,1,31)
        self.assertEqual(plans.boundary(anchor,1,'months',anchor),stamp(2024,2,29))
        self.assertEqual(plans.boundary(anchor,1,'months',stamp(2024,2,29)),stamp(2024,3,31))
        self.assertEqual(plans.boundary(anchor,3,'months',anchor),stamp(2024,4,30))

    def test_missed_daily_cycles_keep_anchor(self):
        self.assertEqual(plans.boundary(100,7,'days',100+20*86400),100+21*86400)
        self.assertIsNone(plans.boundary(100,None,'days',100))


class Subscriptions(test_agent.Transactions):
    def setUp(self):
        super().setUp()
        self.runtime=patch.object(agent,'sync_runtime');self.runtime.start()
        self.qos=patch.object(agent,'apply_qos');self.qos.start()
        self.clock=patch('time.time',return_value=1_800_000_000);self.clock.start()
        self.plan=agent.dispatch({'op':'plan_create','data':{'name':'Plan Prueba','duration':7,'unit':'days','quota_bytes':1_000_000_000}})['id']
    def tearDown(self):
        self.clock.stop();self.qos.stop();self.runtime.stop();super().tearDown()
    def change(self,op,**data):
        return agent.mutate('subscription',{'id':self.id,'operation':op,**data})
    def state(self):
        with agent.db() as c:
            row=c.execute('SELECT * FROM clients WHERE id=?',(self.id,)).fetchone()
            return dict(row),plans.status(c,row)
    def test_imported_client_stays_unlimited(self):
        row,sub=self.state();self.assertIsNone(sub);self.assertFalse(row['plan_blocked'])
    def test_sum_both_directions_blocks_and_topup_restores_same_calendar(self):
        self.change('assign',plan_id=self.plan)
        _,before=self.state()
        with agent.db() as c:c.execute('UPDATE clients SET total_rx=600000000,total_tx=500000000')
        agent.enforce()
        row,sub=self.state();self.assertTrue(row['plan_blocked']);self.assertEqual(sub['blocked_reason'],'exhausted')
        self.assertNotIn('[Peer]',agent.WG.read_text())
        with self.assertRaises(ValueError):agent.mutate('activate',{'id':self.id})
        self.change('topup',bytes=500_000_000)
        row,sub=self.state();self.assertFalse(row['plan_blocked']);self.assertEqual(sub['remaining_bytes'],400_000_000)
        self.assertEqual((sub['anchor'],sub['expires']),(before['anchor'],before['expires']))
        self.assertIn('PresharedKey = fake-test-only',agent.WG.read_text())
    def test_expiry_renewal_keeps_anchor_and_excludes_previous_topups(self):
        self.change('assign',plan_id=self.plan);self.change('topup',bytes=1_000_000_000)
        _,before=self.state()
        with self.assertRaises(ValueError):self.change('renew')
        with patch('time.time',return_value=before['expires']+86400):
            agent.enforce();self.assertTrue(self.state()[0]['plan_blocked'])
            self.change('topup',bytes=1_000_000_000);self.assertTrue(self.state()[0]['plan_blocked'])
            self.change('renew');row,sub=self.state()
            self.assertFalse(row['plan_blocked']);self.assertEqual(sub['anchor'],before['anchor'])
            self.assertEqual(sub['expires'],before['expires']+7*86400)
            self.assertEqual(sub['quota_bytes'],1_000_000_000)
    def test_manual_suspension_survives_topup(self):
        self.change('assign',plan_id=self.plan)
        agent.mutate('suspend',{'id':self.id})
        self.change('topup',bytes=1_000_000_000)
        self.assertTrue(self.state()[0]['suspended']);self.assertNotIn('[Peer]',agent.WG.read_text())
    def test_catalog_edit_is_not_retroactive_change_keeps_cadence(self):
        self.change('assign',plan_id=self.plan);_,before=self.state()
        agent.dispatch({'op':'plan_update','data':{'id':self.plan,'name':'Nuevo','duration':3,'unit':'months','quota_bytes':2_000_000_000}})
        self.assertEqual(self.state()[1]['name'],'Plan Prueba')
        self.change('change',plan_id=self.plan);_,sub=self.state()
        self.assertEqual((sub['anchor'],sub['expires'],sub['duration']),(before['anchor'],before['expires'],7))
        self.assertEqual(sub['quota_bytes'],2_000_000_000)
    def test_cancel_and_new_contract_reset_anchor_and_persist(self):
        self.change('assign',plan_id=self.plan);_,before=self.state()
        with self.assertRaises(ValueError):self.change('assign',plan_id=self.plan)
        self.change('cancel');self.assertTrue(self.state()[0]['plan_blocked'])
        with patch('time.time',return_value=before['anchor']+86400):self.change('assign',plan_id=self.plan)
        agent.initialize();_,sub=self.state()
        self.assertEqual(sub['anchor'],before['anchor']+86400)
        self.assertEqual(len(agent.dispatch({'op':'subscription_history','data':{'id':self.id}})),3)
    def test_failed_subscription_apply_rolls_back_contract_and_peer(self):
        original=agent.WG.read_text()
        with patch.object(agent,'sync_runtime',side_effect=[RuntimeError('injected'),None]):
            with self.assertRaises(RuntimeError):self.change('assign',plan_id=self.plan)
        self.assertIsNone(self.state()[1]);self.assertEqual(agent.WG.read_text(),original)
    def test_gb_only_renewal_and_time_only_expiry(self):
        quota=agent.dispatch({'op':'plan_create','data':{'name':'GB','quota_bytes':1_000_000}})['id']
        self.change('assign',plan_id=quota)
        with agent.db() as c:c.execute('UPDATE clients SET total_tx=1000000')
        agent.enforce();self.assertTrue(self.state()[0]['plan_blocked'])
        self.change('renew');self.assertFalse(self.state()[0]['plan_blocked'])
        self.change('cancel')
        timed=agent.dispatch({'op':'plan_create','data':{'name':'Diario','duration':1}})['id']
        self.change('assign',plan_id=timed);_,sub=self.state()
        with patch('time.time',return_value=sub['expires']):
            agent.enforce()
            self.assertEqual(self.state()[1]['blocked_reason'],'expired')
            self.assertTrue(self.state()[0]['plan_blocked'])
