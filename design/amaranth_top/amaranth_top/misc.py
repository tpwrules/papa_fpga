from amaranth import *

# delay (by default the same length as FFSynchronizer) that doesn't do any CDC
class FFDelay(Elaboratable):
    def __init__(self, i, o, *, reset=0, cycles=2):
        self.i = i
        self.o = o

        self._reset = reset
        self._cycles = cycles

    def elaborate(self, platform):
        m = Module()

        flops = [Signal(self.i.shape(), name=f"stage{index}", reset=self._reset)
            for index in range(self._cycles)]
        for i, o in zip((self.i, *flops), flops):
            m.d.sync += o.eq(i)
        m.d.comb += self.o.eq(flops[-1])

        return m

class SignalPipeline(Elaboratable):
    """Convey signals down a pipeline through time.

    Does not implement or otherwise foster processing logic. Actions are
    processed in program order. Signals used are processed by Python object
    identity.

    Parameters
    ----------
    *signals : tuple of Signal(n), in
        Signals to be put into the pipeline at t=0.
    """
    def __init__(self, *signals):
        self._elaborated = False

        # all dicts keyed by put signal identity
        self._put_signals = {} # dict of signals that have been put
        self._put_times = {} # times those signals have been put in
        self._get_signal_vals = {} # list of signal values at each time
        self._get_signal_ids = set() # set of signal IDs that have been got

        self._get_signal_dsts = [] # list of (dst, sig) pairs for got signals

        for signal in signals:
            self.put(0, src=signal) # put the given signals into the pipeline

    def put(self, t, src):
        """Put the Signal `src` into the pipeline at the given time.

        The signal must not have been previously put into the pipeline or gotten
        from it.

        Parameters
        ----------
        t : int
            Non-negative integer representing time the signal is to be put.
            Signal will be available to get at all times >= t.
        src : Signal(), in
            Signal to be put.
        """
        if self._elaborated:
            raise RuntimeError("already elaborated")
        if not isinstance(src, Signal):
            raise TypeError("src must be Signal")
        if not isinstance(t, int) or t < 0:
            raise TypeError(f"t must be non-negative integer, not {t}")

        sid = id(src)
        if sid in self._get_signal_ids:
            raise ValueError("signal is one that has been previously gotten")
        if sid in self._put_signals:
            raise ValueError("signal has previously been put")

        self._put_signals[sid] = src
        self._put_times[sid] = t

    def get(self, t, src, *, dst=None):
        """Get the Signal `src`'s value from the pipeline at the given time.

        The signal must have been previously put into the pipeline.

        Parameters
        ----------
        t : int
            Time the signal is to be gotten.
        src : Signal(), in
            Signal originally put in whose eventual value is to be gotten.
        dst : Signal(), out, optional
            Signal to combinationally assign the value to.
        
        Returns
        -------
        A Signal() the same shape as `src` representing the value at the gotten
        time, which will be `dst` if supplied and an internal signal otherwise.
        """
        if self._elaborated:
            raise RuntimeError("already elaborated")
        if not isinstance(src, Signal):
            raise TypeError("src must be Signal")
        if not isinstance(t, int) or t < 0:
            raise TypeError(f"t must be non-negative integer, not {t}")

        sid = id(src)
        if sid not in self._put_signals:
            raise ValueError("signal has not previously been put")
        put_time = self._put_times[sid]
        if t < put_time:
            raise ValueError(f"signal got at {t} but was put at {put_time}")

        time_vals = self._get_signal_vals.setdefault(sid, [])
        while len(time_vals) < t-put_time+1:
            # generate signals up to the requested time
            sig = Signal.like(src, name=src.name+f"_t{len(time_vals)+put_time}")
            time_vals.append(sig)
            # remember it in case someone tries to put it again
            self._get_signal_ids.add(id(sig))

        # return the signal at the desired time
        if dst is None:
            dst = time_vals[t-put_time]
        else:
            self._get_signal_dsts.append((dst, time_vals[t-put_time]))
        return dst

    def elaborate(self, platform):
        m = Module()

        self._elaborated = True # lock out future changes

        # hook up put signals to their initial times
        for sid, sig in self._put_signals.items():
            m.d.comb += self._get_signal_vals[sid][0].eq(sig)

        # hook up get signal values through time
        for get_sigs in self._get_signal_vals.values():
            for sig_prev, sig_curr in zip(get_sigs[:-1], get_sigs[1:]):
                m.d.sync += sig_curr.eq(sig_prev)

        # hook up signal get requests
        for dst, sig in self._get_signal_dsts:
            m.d.comb += dst.eq(sig)

        return m
