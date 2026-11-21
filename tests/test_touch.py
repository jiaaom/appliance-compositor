"""Decision tests for compositor/appliance-touch (no hardware needed).

    python3 -m unittest discover -s tests
"""
import importlib.machinery
import importlib.util
import os
import unittest

_path = os.path.join(os.path.dirname(__file__), "..", "compositor", "appliance-touch")
_loader = importlib.machinery.SourceFileLoader("appliance_touch", _path)
_spec = importlib.util.spec_from_loader("appliance_touch", _loader)
at = importlib.util.module_from_spec(_spec)
_loader.exec_module(at)

NONE = at.NO_OUTPUT


def dev(name, ident, foreign=None, usb=None):
    return {"root": "/sys/devices/" + ident, "name": name, "id": ident, "usb": usb,
            "foreign": foreign, "nodes": [{"name": name, "touch": True}]}


def out(ident, monitor="M"):
    return {"id": ident, "monitor": monitor}


class Together:
    """A Seen stand-in: everything appeared together."""
    def together(self, *a):
        return True


def run(devs, outs, rules=(), memory=None, seen=Together()):
    devs = {d["root"]: d for d in devs}
    learned, _ = at.decide(devs, outs, list(rules), memory or {}, seen)
    return {d["id"]: d["output"] for d in devs.values()}, learned


PANEL = dev("FT8722 Touchscreen", "dev:i2c-PFT8722:00", foreign="HDMI-A-1")
EXT = dev("wch.cn TouchScreen", "usb:27c0:0859:S1", usb={"vid": "27c0", "pid": "0859", "serial": "S1"})
EXT2 = dev("Other Touch", "usb:1111:2222:S2", usb={"vid": "1111", "pid": "2222", "serial": "S2"})


class Decide(unittest.TestCase):
    def test_elimination_pairs_and_remembers(self):
        got, learned = run([PANEL, EXT], {"HDMI-A-1": out("ITE:1"), "DP-2": out("CRX:1", "EDGE")})
        self.assertEqual(got, {PANEL["id"]: "HDMI-A-1", EXT["id"]: "DP-2"})
        self.assertEqual(learned[EXT["id"]]["monitor"], "CRX:1")

    def test_no_edid_pairs_but_does_not_remember(self):
        got, learned = run([EXT], {"DP-1": out(None)})
        self.assertEqual(got[EXT["id"]], "DP-1")
        self.assertEqual(learned, {})

    def test_ambiguous_left_to_weston(self):
        got, learned = run([EXT], {"DP-1": out("A:1"), "HDMI-A-2": out("B:1")})
        self.assertIsNone(got[EXT["id"]])
        self.assertEqual(learned, {})

    def test_two_loose_devices_ambiguous(self):
        got, _ = run([EXT, EXT2], {"DP-1": out("A:1")})
        self.assertEqual(got, {EXT["id"]: None, EXT2["id"]: None})

    def test_no_free_display_binds_to_nothing(self):
        # monitor off: only the built-in panel, which has its touchscreen
        got, _ = run([PANEL, EXT], {"HDMI-A-1": out("ITE:1")})
        self.assertEqual(got[EXT["id"]], NONE)

    def test_remembered_follows_monitor_to_another_connector(self):
        mem = {EXT["id"]: {"monitor": "CRX:1", "connector": "DP-2"}}
        got, learned = run([EXT], {"DP-1": out("CRX:1"), "HDMI-A-2": out("TV:1")}, memory=mem)
        self.assertEqual(got[EXT["id"]], "DP-1")
        self.assertEqual(learned[EXT["id"]]["connector"], "DP-1")

    def test_remembered_monitor_absent_binds_to_nothing(self):
        mem = {EXT["id"]: {"monitor": "CRX:1"}}
        got, learned = run([EXT], {"HDMI-A-2": out("TV:1")}, memory=mem)
        self.assertEqual(got[EXT["id"]], NONE)
        self.assertEqual(learned, {})

    def test_config_by_usb_beats_memory_and_claims_output(self):
        rules = [{"name": None, "usb": "27c0:0859", "output": "HDMI-A-2", "file": "x.ini"}]
        mem = {EXT["id"]: {"monitor": "CRX:1"}}
        got, _ = run([EXT, EXT2], {"DP-1": out("CRX:1"), "HDMI-A-2": out("TV:1")}, rules, mem)
        self.assertEqual(got[EXT["id"]], "HDMI-A-2")
        self.assertEqual(got[EXT2["id"]], "DP-1")   # the only free one left

    def test_config_by_name_glob_and_none(self):
        rules = [{"name": "Other *", "usb": None, "output": "none", "file": "x.ini"}]
        got, _ = run([EXT2], {"DP-1": out("A:1")}, rules)
        self.assertEqual(got[EXT2["id"]], NONE)

    def test_config_usb_serial_mismatch(self):
        rules = [{"name": None, "usb": "27c0:0859:OTHER", "output": "DP-9", "file": "x.ini"}]
        got, _ = run([EXT], {"DP-1": out("A:1")}, rules)
        self.assertEqual(got[EXT["id"]], "DP-1")    # rule not matched; DP-9 still claimed

    def test_memory_loses_to_config_claim(self):
        rules = [{"name": "nothing-here", "usb": None, "output": "DP-1", "file": "x.ini"}]
        mem = {EXT["id"]: {"monitor": "CRX:1"}}
        got, _ = run([EXT], {"DP-1": out("CRX:1"), "DP-2": out("B:1")}, rules, mem)
        self.assertEqual(got[EXT["id"]], "DP-2")


class Timing(unittest.TestCase):
    def setUp(self):
        self.outs1 = {"HDMI-A-1": out("ITE:1")}
        self.outs2 = {"HDMI-A-1": out("ITE:1"), "DP-2": out("CRX:1")}

    def test_present_at_start_pairs_but_does_not_remember(self):
        seen = at.Seen()
        seen.update({PANEL["root"]: PANEL, EXT["root"]: EXT}, self.outs2, now=0)
        got, learned = run([PANEL, EXT], self.outs2, seen=seen)
        self.assertEqual(got[EXT["id"]], "DP-2")
        self.assertEqual(learned, {})

    def test_monitor_plugged_in_remembers(self):
        seen = at.Seen()
        seen.update({PANEL["root"]: PANEL}, self.outs1, now=0)
        seen.update({PANEL["root"]: PANEL, EXT["root"]: EXT}, self.outs1, now=100)  # USB first
        seen.update({PANEL["root"]: PANEL, EXT["root"]: EXT}, self.outs2, now=101)  # then video
        got, learned = run([PANEL, EXT], self.outs2, seen=seen)
        self.assertEqual(got[EXT["id"]], "DP-2")
        self.assertIn(EXT["id"], learned)

    def test_coincidence_far_apart_not_remembered(self):
        # touch USB on, monitor's video elsewhere; a TV is turned on later
        tv = {"HDMI-A-2": out("TV:1")}
        seen = at.Seen()
        seen.update({}, {}, now=0)
        seen.update({EXT["root"]: EXT}, {}, now=10)
        seen.update({EXT["root"]: EXT}, tv, now=10 + at.TOGETHER + 1)
        got, learned = run([EXT], tv, seen=seen)
        self.assertEqual(got[EXT["id"]], "HDMI-A-2")   # used for now...
        self.assertEqual(learned, {})                  # ...but not kept

    def test_replugged_display_gets_new_time(self):
        seen = at.Seen()
        seen.update({EXT["root"]: EXT}, self.outs2, now=0)
        seen.update({EXT["root"]: EXT}, self.outs1, now=50)     # DP-2 unplugged
        seen.update({EXT["root"]: EXT}, self.outs2, now=60)     # back, but USB old
        self.assertFalse(seen.together(EXT["id"], "DP-2", "CRX:1"))


class Standby(unittest.TestCase):
    def test_absent_remembered_usb_gets_identity_rule(self):
        mem = {EXT["id"]: {"monitor": "CRX:1", "device_name": "wch"},
               "dev:i2c-X": {"monitor": "CRX:1"}}           # not USB: no standby
        devs = {}
        _, sb = at.decide(devs, {"DP-2": out("CRX:1")}, [], mem)
        self.assertEqual([(s["id"], s["output"]) for s in sb], [(EXT["id"], "DP-2")])
        text = at.render_rules(devs, sb)
        self.assertIn('ATTRS{idVendor}=="27c0", ATTRS{idProduct}=="0859", ATTRS{serial}=="S1"', text)
        self.assertIn('ENV{WL_OUTPUT}="DP-2"', text)

    def test_absent_and_monitor_off(self):
        _, sb = at.decide({}, {}, [], {EXT["id"]: {"monitor": "CRX:1"}})
        self.assertEqual(sb[0]["output"], NONE)

    def test_present_device_has_no_standby(self):
        d = dict(EXT, nodes=[{"name": EXT["name"], "touch": True}])
        _, sb = at.decide({d["root"]: d}, {"DP-2": out("CRX:1")}, [], {EXT["id"]: {"monitor": "CRX:1"}})
        self.assertEqual(sb, [])


class Edid(unittest.TestCase):
    def test_xeneon(self):
        e = bytearray(128)
        e[:8] = b"\x00\xff\xff\xff\xff\xff\xff\x00"
        e[8:10] = bytes([0x0E, 0x58])            # "CRX"
        e[10:12] = bytes([0x00, 0xED])
        e[72:90] = b"\x00\x00\x00\xfc\x00XENEON EDGE\n "
        e[90:108] = b"\x00\x00\x00\xff\x00072326305698\x00"
        self.assertEqual(at.edid_info(bytes(e)), ("CRX:ed00:072326305698", "XENEON EDGE"))

    def test_garbage(self):
        self.assertEqual(at.edid_info(b"\x00" * 10), (None, None))


if __name__ == "__main__":
    unittest.main()
