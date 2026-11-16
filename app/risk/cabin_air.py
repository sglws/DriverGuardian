"""What the risk engine makes of the Arduino Uno's MQ-3 (alcohol) and MQ-2 (smoke) readings."""

from app import config


def _ready(cabin):
    return bool(cabin and cabin.get("warm") and cabin.get("mq3_rel") is not None
                and cabin.get("mq2_rel") is not None)


def _over_raw(cabin, key, limit):
    """Raw reading at the fixed ceiling."""
    return limit is not None and cabin[key] >= limit


class BreathTest:
    """The pre-drive breath test with the MQ-3.

    update() returns ((case, message) while the drive must wait, or None, skip_reason).
    A breath is a rise of ALCOHOL_BREATH_RISE that stops rising for
    ALCOHOL_BREATH_SETTLE_SEC; the decision is made on that peak.
    """

    def __init__(self):
        self.events = []
        self.reset()

    def reset(self):
        self.started = None
        self.blow_since = None
        self.peak = None
        self.failed_at = None
        self.asked_again = False

    def update(self, now, cabin, uno_status):
        if not config.ALCOHOL_CHECK_ENABLED:
            return None, None
        if self.started is None:
            self.started = now
        if uno_status != "connected":
            if uno_status == "searching" and now - self.started < config.ALCOHOL_UNO_WAIT_SEC:
                return ("ALCOHOL_CHECK", "Looking for the alcohol sensor"), None
            return None, "no alcohol sensor (Arduino Uno not connected)"
        base = cabin.get("baseline") if cabin else None
        if base and base["mq3"] < config.ALCOHOL_SENSOR_MIN_RAW:
            return None, f"no alcohol sensor (MQ-3 reads {base['mq3']:.0f})"
        if not _ready(cabin):
            self.blow_since = None
            left = cabin.get("warmup_left_s") if cabin else None
            return ("ALCOHOL_CHECK", f"Alcohol sensor warming up, {left:.0f} s left" if left
                         else "Preparing the alcohol test"), None

        if self.failed_at is not None:
            if now - self.failed_at < config.ALCOHOL_RETEST_SEC:
                return ("ALCOHOL", f"Alcohol detected ({self._peak_text()}) - "
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
            return ("ALCOHOL", f"Alcohol detected ({self._peak_text()})"), None
        breath = self.peak[0] >= config.ALCOHOL_BREATH_RISE and now - self.peak[2] >= config.ALCOHOL_BREATH_SETTLE_SEC
        if not breath:
            if now - self.blow_since >= config.ALCOHOL_BLOW_MAX_SEC:
                if not self.asked_again:
                    self.events.append(("warning", "Alcohol test: no breath",
                                        f"no breath seen in {config.ALCOHOL_BLOW_MAX_SEC:.0f} s - asking again"))
                self.blow_since, self.asked_again = None, True
            if self.asked_again:
                return ("ALCOHOL_BLOW_AGAIN", "No breath detected - blow towards the sensor"), None
            return ("ALCOHOL_BLOW", "Alcohol test: blow towards the sensor"), None
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
    """During the drive: update() returns (alcohol, smoke).

    The two sensors are compared: whichever rose more names the gas.
    """

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
            now, on=(r3 >= config.ALCOHOL_RATIO and r3 > r2) or raw3,
            off=r3 < config.ALCOHOL_DRIVE_CLEAR_RATIO and not raw3, confirm=config.ALCOHOL_DRIVE_CONFIRM_SEC)
        smoke = self.smoke.update(
            now, on=(r2 >= config.SMOKE_RATIO_ON and r2 >= r3) or raw2,
            off=r2 < config.SMOKE_RATIO_OFF and not raw2, confirm=config.SMOKE_CONFIRM_SEC)
        return alcohol, smoke
