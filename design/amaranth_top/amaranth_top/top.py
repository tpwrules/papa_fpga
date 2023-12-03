import pathlib

from amaranth import *
from amaranth.lib import wiring, data
from amaranth.lib.wiring import In, Out, Member, Interface, connect, flipped
from amaranth.lib.cdc import ResetSynchronizer, FFSynchronizer
from amaranth.lib.fifo import AsyncFIFO

from amaranth_soc import csr

import numpy as np

from .bus import AudioRAMBus
from .constants import MIC_FREQ_HZ, NUM_TAPS, NUM_MICS, NUM_CHANS
from .mic import MicCapture, MicCaptureRegs
from .convolve import Convolver
from .stream import SampleStream, SampleStreamFIFO, SampleWriter

class Blinker(wiring.Component):
    button_raw: In(1)
    blink: Out(1)

    def elaborate(self, platform):
        m = Module()

        button_sync = Signal() # active low
        m.submodules += FFSynchronizer(self.button_raw, button_sync)

        MAX_COUNT = int(25e6)
        counter = Signal(range(0, MAX_COUNT-1))
        with m.If(counter == MAX_COUNT-1):
            m.d.sync += counter.eq(0)
            m.d.sync += self.blink.eq(~self.blink & button_sync)
        with m.Else():
            m.d.sync += counter.eq(counter + 1)

        return m

class Top(wiring.Component):
    button_raw: In(1)
    blink: Out(1)

    status_leds: Out(3)

    audio_ram: Out(AudioRAMBus())
    csr_bus: In(csr.Signature(addr_width=8, data_width=32))

    mic_sck: Out(1) # microphone data bus
    mic_ws: Out(1)
    mic_data_raw: In(NUM_MICS//2)

    def __init__(self):
        # TODO: gross and possibly illegal (is the memory map always the same?)
        csr_sig = self.__annotations__["csr_bus"].signature
        self._csr_decoder = csr.Decoder(
            addr_width=csr_sig.addr_width, data_width=csr_sig.data_width)
        csr_sig.memory_map = self._csr_decoder.bus.memory_map

        self._sample_writer = SampleWriter()
        self._mic_capture_regs = MicCaptureRegs(o_domain="mic_capture")

        # add subordinate buses to decoder
        # fix addresses for now for program consistency
        self._csr_decoder.add(self._sample_writer.csr_bus, addr=0)
        self._csr_decoder.add(self._mic_capture_regs.csr_bus, addr=4)

        super().__init__() # initialize component and attributes from signature

    def elaborate(self, platform):
        m = Module()

        m.submodules.blinker = blinker = Blinker()
        m.d.comb += [
            blinker.button_raw.eq(self.button_raw),
            self.blink.eq(blinker.blink),
        ]

        # decode busses for all the subordinate components
        m.submodules.csr_decoder = self._csr_decoder
        connect(m, flipped(self.csr_bus), self._csr_decoder.bus)

        # instantiate mic capture unit in its domain
        m.submodules.mic_capture = mic_capture = \
            DomainRenamer("mic_capture")(MicCapture())
        m.d.comb += [
            self.mic_sck.eq(mic_capture.mic_sck),
            self.mic_ws.eq(mic_capture.mic_ws),
            mic_capture.mic_data_raw.eq(self.mic_data_raw),
        ]

        # instantiate and hook up mic capture registers
        m.submodules.mic_capture_regs = cap_regs = self._mic_capture_regs
        m.d.comb += [
            mic_capture.gain.eq(cap_regs.gain),
            mic_capture.use_fake_mics.eq(cap_regs.use_fake_mics)
        ]

        # FIFO to cross domains from mic capture to the convolver
        m.submodules.mic_fifo = mic_fifo = \
            SampleStreamFIFO(w_domain="mic_capture", r_domain="convolver")
        connect(m, mic_capture.samples, mic_fifo.samples_w)

        # load prepared coefficient data
        coeff_path = pathlib.Path(__file__).parent/"coefficients.txt"
        coefficients = np.loadtxt(coeff_path)
        coefficients = coefficients.reshape(NUM_CHANS, NUM_TAPS, NUM_MICS)

        # instantiate convolver in its domain
        m.submodules.convolver = convolver = \
            DomainRenamer("convolver")(Convolver(coefficients))
        connect(m, mic_fifo.samples_r, convolver.samples_i)
        m.d.comb += convolver.samples_i_count.eq(mic_fifo.samples_count)

        # FIFO to cross domains from convolver to the writer
        m.submodules.conv_fifo = conv_fifo = \
            SampleStreamFIFO(w_domain="convolver")
        connect(m, convolver.samples_o, conv_fifo.samples_w)

        # writer to save sample data to memory
        m.submodules.sample_writer = sample_writer = self._sample_writer
        connect(m, conv_fifo.samples_r, sample_writer.samples)
        connect(m, sample_writer.audio_ram, flipped(self.audio_ram))
        m.d.comb += [
            sample_writer.samples_count.eq(conv_fifo.samples_count),

            self.status_leds.eq(sample_writer.status_leds),
        ]

        return m
