import logging
import os
from unittest import TestCase

from randrctl.model import Profile, Rule, Viewport, Output, XrandrConnection, Display
from randrctl.profile import ProfileManager, ProfileMatcher, hash


class Test_ProfileManager(TestCase):
    manager = ProfileManager(["."], ".")

    TEST_PROFILE_FILE = os.path.join(os.path.dirname(__file__), 'profile_example')
    TEST_SIMPLE_PROFILE_FILE = os.path.join(os.path.dirname(__file__), 'simple_profile_example')

    def test_read(self):
        with open(self.TEST_PROFILE_FILE) as f:
            p = self.manager.read_file(f)

            self.assertIsNotNone(p)

            expected = [
                Output("LVDS1", mode="1366x768"),
                Output("DP1", "1920x1080", pos="1366x0"),
                Output("VGA1", "800x600", pos="3286x0", rotate="inverted", panning="800x1080", rate=80)
            ]
            self.assertOutputs(expected, p.outputs)
            self.assertDictEqual(Rule("d8578edf8458ce06fbc5bb76a58c5ca4", "1920x1200", "1920x1080").__dict__,
                             p.rules["DP1"].__dict__)
            self.assertDictEqual(Rule().__dict__, p.rules["LVDS1"].__dict__)

    def test_simple_read(self):
        with open(self.TEST_SIMPLE_PROFILE_FILE) as f:
            p = self.manager.read_file(f)

            self.assertIsNotNone(p)
            self.assertOutputs([Output("LVDS1", mode="1366x768")], p.outputs)
            self.assertEqual(0, len(p.rules))

    def assertOutputs(self, expected_outputs: list, profile_outputs: list):
        self.assertEqual(len(expected_outputs), len(profile_outputs))
        for eo in expected_outputs:
            matching_output = next(filter(lambda po: po.name == eo.name, profile_outputs), None)
            self.assertIsNotNone(matching_output, "Expected {} among {}".format(eo.name, profile_outputs))
            self.assertDictEqual(eo.__dict__, matching_output.__dict__)

    def test_profile_from_xrandr(self):
        xc = [XrandrConnection("LVDS1", Display(), Viewport("1366x768"), False),
              XrandrConnection("DP1", Display(), Viewport("1920x1080", pos="1366x0"), True),
              XrandrConnection("HDMI1", None, Viewport("1366x768"), False)]

        p = self.manager.profile_from_xrandr(xc)

        self.assertEqual("profile", p.name)
        self.assertEqual(2, len(p.outputs))

    def test_to_dict(self):
        with open(self.TEST_PROFILE_FILE) as f:
            p = self.manager.read_file(f)

            d = self.manager.to_dict(p)
            self.maxDiff = None
            self.assertDictEqual(
                {'primary': 'LVDS1',
                 'priority': 100,
                 'match': {'LVDS1': {},
                           'DP1': {'edid': "d8578edf8458ce06fbc5bb76a58c5ca4",
                                   'supports': "1920x1080",
                                   'prefers': "1920x1200"}},
                 'outputs': {'DP1': {'mode': "1920x1080", 'pos': "1366x0", 'rotate': "normal", 'panning': "0x0",
                                     'scale': "1x1"},
                             'LVDS1': {'mode': "1366x768", 'pos': "0x0", 'rotate': "normal", 'panning': "0x0",
                                       'scale': "1x1"},
                             'VGA1': {'mode': "800x600", 'pos': "3286x0", 'rotate': "inverted",
                                      'panning': "800x1080", 'rate': 80, 'scale': "1x1"}}}, d)

    def test_to_dict_no_rules(self):
        with open(self.TEST_PROFILE_FILE) as f:
            p = self.manager.read_file(f)
            p.rules = None

            d = self.manager.to_dict(p)
            self.maxDiff = None
            self.assertDictEqual(
                {'primary': 'LVDS1',
                 'priority': 100,
                 'outputs': {'DP1': {'mode': "1920x1080", 'pos': "1366x0", 'rotate': "normal", 'panning': "0x0",
                                     'scale': "1x1"},
                             'LVDS1': {'mode': "1366x768", 'pos': "0x0", 'rotate': "normal", 'panning': "0x0",
                                       'scale': "1x1"},
                             'VGA1': {'mode': "800x600", 'pos': "3286x0", 'rotate': "inverted",
                                      'panning': "800x1080", 'rate': 80, 'scale': "1x1"}}}, d)

    def test_to_dict_no_edid_rule(self):
        with open(self.TEST_PROFILE_FILE) as f:
            p = self.manager.read_file(f)
            p.rules['DP1'].edid = None

            d = self.manager.to_dict(p)
            self.maxDiff = None
            self.assertDictEqual(
                {'primary': 'LVDS1',
                 'priority': 100,
                 'match': {'LVDS1': {},
                           'DP1': {'supports': "1920x1080", 'prefers': "1920x1200"}},
                 'outputs': {'DP1': {'mode': "1920x1080", 'pos': "1366x0", 'rotate': "normal", 'panning': "0x0",
                                     'scale': "1x1"},
                             'LVDS1': {'mode': "1366x768", 'pos': "0x0", 'rotate': "normal", 'panning': "0x0",
                                       'scale': "1x1"},
                             'VGA1': {'mode': "800x600", 'pos': "3286x0", 'rotate': "inverted",
                                      'panning': "800x1080", 'rate': 80, 'scale': "1x1"}}}, d)


class Test_ProfileMatcher(TestCase):
    logging.basicConfig()

    matcher = ProfileMatcher()

    def test_should_match_profile_with_empty_rule(self):
        # given
        expected = profile("should_match", {"LVDS1": Rule()})
        profiles = [
            profile("different_output_in_rule", {"DP1": Rule(prefers="1920x1080")}),
            profile("no_rules"),
            expected
        ]
        outputs = [
            XrandrConnection("LVDS1", Display(preferred_mode="1920x1080"))
        ]

        # when
        best = self.matcher.find_best(profiles, outputs)

        # then
        self.assertEqual(expected, best)

    def test_should_not_match_profile_without_rules(self):
        # given
        profiles = [
            profile("no_rules1"),
            profile("no_rules2"),
            profile("no_rules3")
        ]
        outputs = [
            XrandrConnection("LVDS1", Display(preferred_mode="1920x1080"))
        ]

        # when
        best = self.matcher.find_best(profiles, outputs)

        # then
        self.assertIsNone(best)

    def test_should_prefer_edid_over_mode(self):
        # given
        edid = "some_edid"
        expected = profile("with_edid", {"LVDS1": Rule(hash(edid))})
        profiles = [
            expected,
            profile("with_supported_mode", {"LVDS1": Rule(supports="1920x1080")}),
            profile("with_preferred_mode", {"LVDS1": Rule(prefers="1920x1080")})
        ]
        outputs = [
            XrandrConnection("LVDS1", Display(["1920x1080"], "1920x1080", edid=edid))
        ]

        # when
        best = self.matcher.find_best(profiles, outputs)

        # then
        self.assertEqual(expected, best)

    def test_should_prefer_rule_prefers_over_supports(self):
        # given
        expected = profile("with_prefers", {"LVDS1": Rule(prefers="1920x1080")})
        profiles = [
            expected,
            profile("with_supports", {"LVDS1": Rule(supports="1920x1080")})
        ]
        outputs = [
            XrandrConnection("LVDS1", Display(["1920x1080"], "1920x1080"))
        ]

        # when
        best = self.matcher.find_best(profiles, outputs)

        # then
        self.assertEqual(expected, best)

    # TODO use-case of this is frankly not clear. We can set priority by file name. Clarify
    def test_should_pick_profile_with_higher_prio_if_same_score(self):
        # given
        expected = profile("highprio", {"LVDS1": Rule()}, prio=999)
        profiles = [
            profile("default", {"LVDS1": Rule()}),
            expected
        ]
        outputs = [
            XrandrConnection("LVDS1", Display()),
        ]

        # when
        best = self.matcher.find_best(profiles, outputs)

        # then
        self.assertEqual(expected, best)

    def test_should_pick_first_profile_if_same_score(self):
        # given
        edid = "office"
        edidhash = hash(edid)
        profiles = [
            profile("p1", {"LVDS1": Rule(), "DP1": Rule(edidhash)}),
            profile("p2", {"LVDS1": Rule(), "DP1": Rule(edidhash)})
        ]
        outputs = [
            XrandrConnection("LVDS1", Display()),
            XrandrConnection("DP1", Display(["1920x1080"], edid=edid))
        ]

        # when
        best = self.matcher.find_best(profiles, outputs)

        # then
        self.assertEqual(profiles[0], best)

    def test_should_match_profiles_and_list_descending(self):
        # given
        edid = "office"
        edidhash = hash(edid)
        profiles = [
            profile("match4", {"LVDS1": Rule(), "DP1": Rule()}),
            profile("match1", {"LVDS1": Rule(), "DP1": Rule(edidhash)}),
            profile("match3", {"LVDS1": Rule(), "DP1": Rule(supports="1920x1080")}),
            profile("match2", {"LVDS1": Rule(), "DP1": Rule(prefers="1920x1080")}),
            profile("match5", {"LVDS1": Rule()}),
            profile("missing_output", {"LVDS1": Rule(), "DP1": Rule(), "HDMI1": Rule()}),
            profile("no_rules")
        ]
        outputs = [
            XrandrConnection("LVDS1", Display()),
            XrandrConnection("DP1", Display(["1920x1080"], "1920x1080", edid=edid))
        ]

        # when
        matches = self.matcher.match(profiles, outputs)

        # then
        self.assertEqual(5, len(matches))
        self.assertEqual("match1", matches[0][1].name)
        self.assertEqual("match2", matches[1][1].name)
        self.assertEqual("match3", matches[2][1].name)
        self.assertEqual("match4", matches[3][1].name)
        self.assertEqual("match5", matches[4][1].name)


def profile(name: str, rules: dict = None, prio: int = 100):
    # we do not care about actual outputs in these tests, only rules matters
    return Profile(name, [], rules, priority=prio)

