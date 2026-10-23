"""
cabin_air.py
------------
What the risk engine makes of the Arduino Uno's MQ-3 (alcohol) and MQ-2
(smoke) readings. Readings come from arduino.UnoLink.state(): raw values and
mq3_rel / mq2_rel, each a multiple of the clean-air reference (which follows
clean air, see AIR_REF_* in config.py). A fixed raw ceiling backs that up in
case the reference was taken in bad air.

  BreathTest    before the drive: the driver blows towards the sensor and the
                MQ-3's peak decides, like an alcohol interlock.
  AirWatch      during the drive: alcohol in the cabin (MEDIUM risk) and smoke
                (one of the two ways smoking is detected, LOW risk).

Telling the gases apart: each sensor is most sensitive to its own gas, so
alcohol vapour makes the MQ-3 rise more than the MQ-2, and smoke makes the
MQ-2 rise more than the MQ-3 - each alarm needs its own sensor to lead.
Slow changes (outside air or exhaust drifting in, temperature) are absorbed
by the moving reference, so only a fast rise, like a cigarette lit in the
car, gets this far. It's a heuristic: the camera seeing the cigarette is the
reliable source, the MQ-2 the backup.
"""

from app import config


def _ready(cabin):
    return bool(cabin and cabin.get("warm") and cabin.get("mq3_rel") is not None
                and cabin.get("mq2_rel") is not None)


def _over_raw(cabin, key, limit):
    """Raw reading at the fixed ceiling. It always applies - that is its job
    when the reference was taken in bad air - so set it above what your
    sensor reads in clean air (UnoLink warns when the reference gets close)."""
    return limit is not None and cabin[key] >= limit


def _wait(case, message):
    return case, message


class BreathTest:
    """The alcohol part of the pre-drive gate. update() returns
    (waiting, skipped): `waiting` is the (case, message) to report as WAITING
    until the test is passed (then None); `skipped` says why the test can't
    run (no alcohol sensor), in which case only the seatbelt counts.

    The driver blows freely - no set duration. The test passes once a breath
    is seen (the MQ-3 rose to ALCOHOL_BREATH_RISE and then stopped rising for
    ALCOHOL_BREATH_SETTLE_SEC: alcohol makes the reading climb for a few
    seconds, so passing on the first small rise would judge too early). With
    no breath within ALCOHOL_BLOW_MAX_SEC it asks again - skipping the breath
    never starts the drive. Alcohol at any moment fails it."""

    def __init__(self):
        self.events = []        # (level, title, detail) for the session log
        self.reset()

    def reset(self):
        self.started = None     # when the pre-drive check began
        self.blow_since = None  # when the driver was asked to blow
        self.peak = None        # (rel, raw, when) highest MQ-3 reading since then
        self.failed_at = None
        self.asked_again = False  # no breath in the last window

    def update(self, now, cabin, uno_status):
        if not config.ALCOHOL_CHECK_ENABLED:
            return None, None
        if self.started is None:
            self.started = now
        if uno_status != "connected":
            # "searching" right after start-up: the Uno takes a few seconds to
            # answer, so give it ALCOHOL_UNO_WAIT_SEC before deciding it's absent.
            if uno_status == "searching" and now - self.started < config.ALCOHOL_UNO_WAIT_SEC:
                return _wait("ALCOHOL_CHECK", "Looking for the alcohol sensor"), None
            return None, "no alcohol sensor (Arduino Uno not connected)"
        base = cabin.get("baseline") if cabin else None
        if base and base["mq3"] < config.ALCOHOL_SENSOR_MIN_RAW:
            return None, f"no alcohol sensor (MQ-3 reads {base['mq3']:.0f})"
        if not _ready(cabin):
            self.blow_since = None
            left = cabin.get("warmup_left_s") if cabin else None
            return _wait("ALCOHOL_CHECK", f"Alcohol sensor warming up, {left:.0f} s left" if left
                         else "Preparing the alcohol test"), None

        if self.failed_at is not None:
            if now - self.failed_at < config.ALCOHOL_RETEST_SEC:
                return _wait("ALCOHOL", f"Alcohol detected ({self._peak_text()}) - "
                             f"new test in {config.ALCOHOL_RETEST_SEC - (now - self.failed_at):.0f} s"), None
            self.failed_at = None
        rel, raw = cabin["mq3_rel"], cabin["mq3"]
        if self.blow_since is None:
            self.blow_since, self.peak = now, (rel, raw, now)
        elif rel > self.peak[0] or raw > self.peak[1]:
            self.peak = (max(rel, self.peak[0]), max(raw, self.peak[1]), now)

        limit_raw = config.ALCOHOL_RAW_LIMIT
        if self.peak[0] >= config.ALCOHOL_RATIO or (limit_raw is not None and self.peak[1] >= limit_raw):
            self.failed_at, self.blow_since = now, None
            self.events.append(("critical", "Alcohol test failed",
                                f"{self._peak_text()} (limit {config.ALCOHOL_RATIO}x or raw {limit_raw})"))
            return _wait("ALCOHOL", f"Alcohol detected ({self._peak_text()})"), None
        breath = self.peak[0] >= config.ALCOHOL_BREATH_RISE and now - self.peak[2] >= config.ALCOHOL_BREATH_SETTLE_SEC
        if not breath:
            if now - self.blow_since >= config.ALCOHOL_BLOW_MAX_SEC:
                if not self.asked_again:
                    self.events.append(("warning", "Alcohol test: no breath",
                                        f"no breath seen in {config.ALCOHOL_BLOW_MAX_SEC:.0f} s - asking again"))
                self.blow_since, self.asked_again = None, True   # a new window from the next reading
            if self.asked_again:
                return _wait("ALCOHOL_BLOW_AGAIN", "No breath detected - blow towards the sensor"), None
            return _wait("ALCOHOL_BLOW", "Alcohol test: blow towards the sensor"), None
        self.asked_again = False
        self.events.append(("good", "Alcohol test passed", f"{self._peak_text()} (limit {config.ALCOHOL_RATIO}x)"))
        return None, None

    def _peak_text(self):
        return f"MQ-3 peak {self.peak[0]:.2f}x clean air, raw {self.peak[1]}"


class _Alarm:
    """On once `on` has held for `confirm` seconds, off as soon as `off` holds."""

    def __init__(self):
        self.active, self.since = False, None

    def update(self, now, on, off, confirm):
        if self.active:
            if off:
                self.active, self.since = False, None
        elif on:
            if self.since is None:
                self.since = now
            self.active = now - self.since >= confirm
        else:
            self.since = None
        return self.active


class AirWatch:
    """During the drive: update() returns (alcohol, smoke)."""

    def __init__(self):
        self.alcohol, self.smoke = _Alarm(), _Alarm()

    def update(self, now, cabin):
        if not _ready(cabin):
            self.alcohol, self.smoke = _Alarm(), _Alarm()
            return False, False
        r3, r2 = cabin["mq3_rel"], cabin["mq2_rel"]
        raw3 = _over_raw(cabin, "mq3", config.ALCOHOL_RAW_LIMIT)
        raw2 = _over_raw(cabin, "mq2", config.SMOKE_RAW_LIMIT)
        alcohol = self.alcohol.update(
            now, on=(r3 >= config.ALCOHOL_RATIO and r3 - 1 > r2 - 1) or raw3,
            off=r3 < config.ALCOHOL_DRIVE_CLEAR_RATIO and not raw3, confirm=config.ALCOHOL_DRIVE_CONFIRM_SEC)
        smoke = self.smoke.update(
            now, on=(r2 >= config.SMOKE_RATIO_ON and r2 - 1 >= r3 - 1) or raw2,
            off=r2 < config.SMOKE_RATIO_OFF and not raw2, confirm=config.SMOKE_CONFIRM_SEC)
        return alcohol, smoke
