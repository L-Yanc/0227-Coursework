"""Input pacing preserves source timestamps and counts processing toward each interval."""
import math

def playback_delay(previous_start,previous_timestamp,timestamp,speed,now):
    if not math.isfinite(speed) or speed<0:
        raise ValueError('Playback speed must be finite and non-negative (0 means unpaced)')
    if previous_start is None or previous_timestamp is None or speed==0:
        return 0.
    interval=timestamp-previous_timestamp
    if interval<=0: raise ValueError('Source timestamps must increase')
    return max(0.,interval/speed-(now-previous_start))
