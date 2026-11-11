"""v0.4.9.30 hardware-neutral controller recovery frontier contracts."""
import unittest
from analysis_integration.recovery_frontier import Frontier, FrontierError, RecoveryFrontiers

class RecoveryFrontierTests(unittest.TestCase):
    def setUp(self):
        self.obs = {'pc': 0x1234, 'physical_offset': 0x81234, 'mapper': [0, 1, 2, 3]}

    def test_reserve_and_confirm_does_not_implicitly_commit(self):
        guard = RecoveryFrontiers(3)
        index, frontier = guard.request(self.obs)
        self.assertEqual((index, guard.attempts, guard.confirmed), (1, 1, 0))
        guard.confirm(index, frontier)
        self.assertEqual(guard.confirmed, 1)

    def test_duplicate_frontier_fails_closed_without_consuming_attempt(self):
        guard = RecoveryFrontiers(3)
        guard.request(self.obs)
        with self.assertRaisesRegex(FrontierError, '^REPEATED_LIVE_GAP_NO_NEW_CODE$'):
            guard.request(dict(self.obs))
        self.assertEqual(guard.attempts, 1)

    def test_changed_mapper_identity_is_independent(self):
        guard = RecoveryFrontiers(2)
        first = guard.request(self.obs)[1]
        second = guard.request(dict(self.obs, mapper=[0, 1, 4, 3]))[1]
        self.assertNotEqual(first, second)

    def test_changed_source_offset_is_independent(self):
        guard = RecoveryFrontiers(2)
        first = guard.request(self.obs)[1]
        second = guard.request(dict(self.obs, physical_offset=0x91234))[1]
        self.assertNotEqual(first, second)

    def test_bounded_attempts(self):
        guard = RecoveryFrontiers(1)
        guard.request(self.obs)
        with self.assertRaisesRegex(FrontierError, '^LIVE_RECOVERY_LIMIT$'):
            guard.request(dict(self.obs, pc=0x1235))

    def test_no_early_or_repeated_activation_acknowledgment(self):
        guard = RecoveryFrontiers(2)
        index, frontier = guard.request(self.obs)
        with self.assertRaisesRegex(FrontierError, '^RECOVERY_ACTIVATION_SEQUENCE_MISMATCH$'):
            guard.confirm(index + 1, frontier)
        guard.confirm(index, frontier)
        with self.assertRaisesRegex(FrontierError, '^RECOVERY_ACTIVATION_ALREADY_CONFIRMED$'):
            guard.confirm(index, frontier)

    def test_invalid_observations_rejected(self):
        for bad in (dict(self.obs, pc=True), dict(self.obs, mapper=[-1]),
                    dict(self.obs, physical_offset='4'), dict(self.obs, mapper=[0]*65)):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(FrontierError, '^RECOVERY_FRONTIER_INVALID$'):
                    Frontier.from_observation(bad)

    def test_not_hardwired_to_sms_or_z80(self):
        obs={'pc': 0x123456789, 'physical_offset': 0x123456789ab, 'mapper': []}
        index, frontier=RecoveryFrontiers(1).request(obs)
        self.assertEqual((index, frontier.address, frontier.mapping), (1, obs['pc'], ()))

    def test_bad_limits_fail_closed(self):
        for limit in (0, 513, -1, True, 1.0):
            with self.subTest(limit=limit):
                with self.assertRaisesRegex(FrontierError, '^RECOVERY_BUDGET_INVALID$'):
                    RecoveryFrontiers(limit)

if __name__ == '__main__':
    unittest.main()
