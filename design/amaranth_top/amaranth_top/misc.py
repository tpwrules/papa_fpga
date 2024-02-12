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

class SignalConveyor(Elaboratable):
    """Convey signals down a conveyor belt through time.

    A particular Amaranth Signal can be "put" onto the conveyor at time t. One
    can then "get" that Signal at a future time T >= t. This produces another
    Signal, which has the original Signal's value, but delayed by T-t cycles.

    All Signals used/produced by the conveyor are identified by Python object
    identity. The conveyor knows whether each particular Signal was put or
    gotten, and at what time.

    Does not implement or otherwise foster processing logic. Put/get actions are
    processed in program execution order.

    Parameters
    ----------
    *signals : tuple of Signal(), in
        Signals to put onto the conveyor at t=0. This is purely a convenience;
        Signals given here have no special significance.
    """
    def __init__(self, *signals):
        self._elaborated = False

        # all dicts keyed by put Signal identity
        self._put_signals = {} # Signals that have been put
        self._put_times = {} # times those Signals have been put on
        self._get_signal_vals = {} # list of Signals having value at each time
        self._sig_times = {} # time each Signal has been put/got

        self._get_signal_ids = set() # set of Signal IDs that have been got
        self._get_signal_dsts = [] # list of (dst, sig) pairs for got Signals

        for signal in signals:
            self.put(0, src=signal) # put the given Signals onto the conveyor

    def put(self, t, src, *, rel=None):
        """Put the Signal `src` onto the conveyor at the given time t.

        The Signal must not have been previously put onto the conveyor, nor be
        one returned from `get`.

        Parameters
        ----------
        t : int
            Time t to put the Signal. Signal is gettable at all T >= t.
        src : Signal(), in
            Signal to put.
        rel : Signal(), optional
            Signal from whose put/get time the given t is relative. If None,
            then relative to time 0. Any Signal that was previously
            passed to/returned from put or get is valid here.
        """
        if self._elaborated:
            raise RuntimeError("already elaborated")
        if not isinstance(src, Signal):
            raise TypeError("src must be Signal")
        if not isinstance(t, int):
            raise TypeError(f"t must be integer, not {t}")

        sid = id(src)
        if sid in self._get_signal_ids:
            raise ValueError("signal is one that has been previously gotten")
        if sid in self._put_signals:
            raise ValueError("signal has previously been put")
        if rel is not None:
            rel_t = self._sig_times.get(id(rel))
            if rel_t is None:
                raise ValueError("relative signal not known")
            t += rel_t

        self._put_signals[sid] = src
        self._put_times[sid] = t
        self._sig_times[sid] = t

    def get(self, T, src, *, dst=None, rel=None):
        """Get the Signal `src`'s value from the conveyor at the given time T.

        That Signal must have been previously put onto the conveyor at time t.
        The gotten Signal has `src`'s value, delayed by T-t cycles. This delay
        must be non-negative.

        Parameters
        ----------
        T : int
            Time T at which to get the Signal.
        src : Signal(), in
            Signal originally put on whose delayed value will be gotten.
        dst : Signal(), out, optional
            Signal to combinationally assign the gotten value to.
        rel : Signal(), optional
            Signal from whose put/get time the given T is relative. If None,
            then relative to time 0. Any Signal that was previously
            passed to/returned from put or get is valid here.

        Returns
        -------
        A Signal like `src` having `src`'s value at the gotten time. This is
        `dst` if supplied; otherwise it's an internally generated Signal.
        """
        if self._elaborated:
            raise RuntimeError("already elaborated")
        if not isinstance(src, Signal):
            raise TypeError("src must be Signal")
        if not isinstance(T, int):
            raise TypeError(f"T must be integer, not {t}")

        sid = id(src)
        if sid not in self._put_signals:
            raise ValueError("signal has not previously been put")
        if rel is not None:
            rel_t = self._sig_times.get(id(rel))
            if rel_t is None:
                raise ValueError("relative signal not known")
            T += rel_t
        put_time = self._put_times[sid]
        if T < put_time:
            raise ValueError(f"signal got at {T} but was put at {put_time}")

        time_vals = self._get_signal_vals.setdefault(sid, [])
        while len(time_vals) < T-put_time+1:
            # generate signals up to the requested time
            sig = Signal.like(src, name=src.name+f"_t{len(time_vals)+put_time}")
            time_vals.append(sig)
            # remember it in case someone tries to put it again
            self._get_signal_ids.add(id(sig))

        # return the signal at the desired time
        desired = time_vals[T-put_time]
        if dst is None:
            dst = desired
        else:
            self._get_signal_dsts.append((dst, desired))
            self._sig_times[id(desired)] = T
        self._sig_times[id(dst)] = T
        return dst

    def elaborate(self, platform):
        m = Module()

        self._elaborated = True # lock out future changes

        # hook up put Signals to their initial times
        for sid, sig in self._put_signals.items():
            m.d.comb += self._get_signal_vals[sid][0].eq(sig)

        # hook up gotte Signals through time
        for get_sigs in self._get_signal_vals.values():
            for sig_prev, sig_curr in zip(get_sigs[:-1], get_sigs[1:]):
                m.d.sync += sig_curr.eq(sig_prev)

        # hook up Signal get requests
        for dst, sig in self._get_signal_dsts:
            m.d.comb += dst.eq(sig)

        return m
