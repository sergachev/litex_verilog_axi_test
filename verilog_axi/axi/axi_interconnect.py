#
# This file is part of LiteX-Verilog-AXI-Test
#
# Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# LiteX wrapper around Alex Forencich Verilog-AXI's axi_interconnect.v.

import os
import math

from migen import *

from litex.soc.interconnect.axi import *

from verilog_axi.axi_common import *

# AXI Interconnect Interface -----------------------------------------------------------------------

class AXIInterconnectInterface:
    def __init__(self, axi, origin=None, size=None):
        self.axi    = axi
        self.origin = origin
        self.size   = size

# AXI Interconnect ---------------------------------------------------------------------------------

class AXIInterconnect(Module):
    def __init__(self, platform):
        self.logger = logging.getLogger("AXIInterconnect")
        self.s_axis = {}
        self.m_axis = {}

        # Add Sources.
        # ------------
        self.add_sources(platform)

    def get_if_name(self, axi):
        axi_ifs = {**self.s_axis, **self.m_axis}
        for name, axi_if in axi_ifs.items():
            if axi is axi_if.axi:
                return name
        return None

    def add_slave(self, name=None, s_axi=None):
        # Get/Check Name.
        name = f"s_axi{len(self.s_axis)}" if name is None else name
        if name in self.s_axis.keys():
            raise ValueError # FIXME: Add error message.

        # Add Slave.
        assert isinstance(s_axi, AXIInterface)
        s_axi = AXIInterconnectInterface(axi=s_axi)
        self.s_axis[name] = s_axi

        # Info.
        self.logger.info(f"Add AXI Slave {name} interface.")

        # Check.
        self.get_check_parameters(show=False)

    def add_master(self, name=None, m_axi=None, origin=None, size=None):

        # Get/Check Name.
        name = f"m_axi{len(self.m_axis)}" if name is None else name
        if name in self.m_axis.keys():
            raise ValueError # FIXME: Add error message.

        # Add Master.
        assert isinstance(m_axi, AXIInterface)
        assert origin is not None
        assert size   is not None
        m_axi = AXIInterconnectInterface(
            axi    = m_axi,
            origin = origin,
            size   = size,
        )
        self.m_axis[name] = m_axi

        # Info.
        self.logger.info(f"Add AXI Master {name} interface.")
        self.logger.info(f"  Origin: 0x{origin:08x}.")
        self.logger.info(f"  Size:   0x{size:0x}.")

        # Check.
        self.get_check_parameters(show=False)

    def get_check_parameters(self, show=True):
        axi_ifs = {**self.s_axis, **self.m_axis}
        axis    = [axi_if.axi for name, axi_if in axi_ifs.items()]

        # Clock Domain.
        self.clock_domain = clock_domain = axis[0].clock_domain
        for i, axi in enumerate(axis):
            if i == 0:
                continue
            else:
                if axi.clock_domain != clock_domain:
                    self.logger.error("{} on {} ({}: {} / {}: {}), should be {}.".format(
                        colorer("Different Clock Domain", color="red"),
                        colorer("AXI interfaces."),
                        self.get_if_name(axis[0]),
                        colorer(clock_domain),
                        self.get_if_name(axi),
                        colorer(axi.clock_domain),
                        colorer("the same")))
                    raise AXIError()
        if show:
            self.logger.info(f"Clock Domain: {colorer(clock_domain)}")

        # Address width.
        self.address_width = address_width = len(axis[0].aw.addr)
        for i, axi in enumerate(axis):
            if i == 0:
                continue
            else:
                if len(axi.aw.addr) != address_width:
                    self.logger.error("{} on {} ({}: {} / {}: {}), should be {}.".format(
                        colorer("Different Address Width", color="red"),
                        colorer("AXI interfaces."),
                        self.get_if_name(axis[0]),
                        colorer(address_width),
                        self.get_if_name(axi),
                        colorer(len(axi.aw.addr)),
                        colorer("the same")))
                    raise AXIError()
        if show:
            self.logger.info(f"Address Width: {colorer(address_width)}")

        # Data width.
        self.data_width = data_width = len(axis[0].w.data)
        for i, axi in enumerate(axis):
            if i == 0:
                continue
            else:
                if len(axi.w.data) != data_width:
                    self.logger.error("{} on {} ({}: {} / {}: {}), should be {}.".format(
                        colorer("Different Data Width", color="red"),
                        colorer("AXI interfaces."),
                        self.get_if_name(axis[0]),
                        colorer(data_width),
                        self.get_if_name(axi),
                        colorer(len(axi.w.data)),
                        colorer("the same")))
                    raise AXIError()
        if show:
            self.logger.info(f"Data Width: {colorer(data_width)}")

        # ID width.
        # FIXME: Add check.
        self.id_width = id_width = len(axis[0].aw.id)
        if show:
            self.logger.info(f"ID Width: {colorer(id_width)}")

        # Burst.
        # FIXME: Add check.

    def do_finalize(self):
        # Get/Check Parameters.
        # ---------------------
        self.get_check_parameters()


        # Get/Check Parameters.
        # ---------------------
        self.logger.info(f"Finalized {len(self.s_axis)}X{len(self.m_axis)} Interconnect:")
        self.logger.info(f"  Slaves:")
        for s_name, s_axi in self.s_axis.items():
            self.logger.info(f"  - {s_name}.")
        self.logger.info(f"  Masters:")
        for m_name, m_axi in self.m_axis.items():
            self.logger.info(f"  - {m_name}, Origin: 0x{m_axi.origin:08x}, Size: 0x{m_axi.size:0x}.")


        # Module instance.
        # ----------------

        s_axis    = [axi_if.axi                        for axi_if in self.s_axis.values()]
        m_axis    = [axi_if.axi                        for axi_if in self.m_axis.values()]
        m_origins = [axi_if.origin                     for axi_if in self.m_axis.values()]
        m_widths  = [math.ceil(math.log2(axi_if.size)) for axi_if in self.m_axis.values()]

        def format_m_params(params, width):
            value = 0
            for param in reversed(params):
                value <<= width
                value |= param
            return Constant(value, len(params)*width)

        self.specials += Instance("axi_interconnect",
            # Parameters.
            # -----------
            p_S_COUNT    = len(s_axis),
            p_M_COUNT    = len(m_axis),
            p_DATA_WIDTH = self.data_width,
            p_ADDR_WIDTH = self.address_width,
            p_ID_WIDTH   = self.id_width,

            # FIXME: Enable it in LiteX's AXIInterface and add support.
            p_AWUSER_ENABLE = 0,
            p_AWUSER_WIDTH  = 1,
            p_WUSER_ENABLE  = 0,
            p_WUSER_WIDTH   = 1,
            p_BUSER_ENABLE  = 0,
            p_BUSER_WIDTH   = 1,
            p_ARUSER_ENABLE = 0,
            p_ARUSER_WIDTH  = 1,
            p_RUSER_ENABLE  = 0,
            p_RUSER_WIDTH   = 1,

            # Masters Origin/Size.
            p_M_BASE_ADDR  = format_m_params(m_origins, self.address_width),
            p_M_ADDR_WIDTH = format_m_params(m_widths,  32),

            # FIXME: Expose other parameters.

            # Clk / Rst.
            # ----------
            i_clk = ClockSignal(self.clock_domain),
            i_rst = ResetSignal(self.clock_domain),

            # AXI Slave Interfaces.
            # --------------------
            # AW.
            i_s_axi_awid     = Cat(*[s_axi.aw.id    for s_axi in s_axis]),
            i_s_axi_awaddr   = Cat(*[s_axi.aw.addr  for s_axi in s_axis]),
            i_s_axi_awlen    = Cat(*[s_axi.aw.len   for s_axi in s_axis]),
            i_s_axi_awsize   = Cat(*[s_axi.aw.size  for s_axi in s_axis]),
            i_s_axi_awburst  = Cat(*[s_axi.aw.burst for s_axi in s_axis]),
            i_s_axi_awlock   = Cat(*[s_axi.aw.lock  for s_axi in s_axis]),
            i_s_axi_awcache  = Cat(*[s_axi.aw.cache for s_axi in s_axis]),
            i_s_axi_awprot   = Cat(*[s_axi.aw.prot  for s_axi in s_axis]),
            i_s_axi_awqos    = Cat(*[s_axi.aw.qos   for s_axi in s_axis]),
            i_s_axi_awuser   = 0, # FIXME.
            i_s_axi_awvalid  = Cat(*[s_axi.aw.valid for s_axi in s_axis]),
            o_s_axi_awready  = Cat(*[s_axi.aw.ready for s_axi in s_axis]),

            # W.
            i_s_axi_wdata    = Cat(*[s_axi.w.data   for s_axi in s_axis]),
            i_s_axi_wstrb    = Cat(*[s_axi.w.strb   for s_axi in s_axis]),
            i_s_axi_wlast    = Cat(*[s_axi.w.last   for s_axi in s_axis]),
            i_s_axi_wuser    = 0, # FIXME.
            i_s_axi_wvalid   = Cat(*[s_axi.w.valid  for s_axi in s_axis]),
            o_s_axi_wready   = Cat(*[s_axi.w.ready  for s_axi in s_axis]),

            # B.
            o_s_axi_bid      = Cat(*[s_axi.b.id     for s_axi in s_axis]),
            o_s_axi_bresp    = Cat(*[s_axi.b.resp   for s_axi in s_axis]),
            o_s_axi_buser    = Open(), # FIXME.
            o_s_axi_bvalid   = Cat(*[s_axi.b.valid  for s_axi in s_axis]),
            i_s_axi_bready   = Cat(*[s_axi.b.ready  for s_axi in s_axis]),

            # AR.
            i_s_axi_arid     = Cat(*[s_axi.ar.id    for s_axi in s_axis]),
            i_s_axi_araddr   = Cat(*[s_axi.ar.addr  for s_axi in s_axis]),
            i_s_axi_arlen    = Cat(*[s_axi.ar.len   for s_axi in s_axis]),
            i_s_axi_arsize   = Cat(*[s_axi.ar.size  for s_axi in s_axis]),
            i_s_axi_arburst  = Cat(*[s_axi.ar.burst for s_axi in s_axis]),
            i_s_axi_arlock   = Cat(*[s_axi.ar.lock  for s_axi in s_axis]),
            i_s_axi_arcache  = Cat(*[s_axi.ar.cache for s_axi in s_axis]),
            i_s_axi_arprot   = Cat(*[s_axi.ar.prot  for s_axi in s_axis]),
            i_s_axi_arqos    = Cat(*[s_axi.ar.qos   for s_axi in s_axis]),
            i_s_axi_aruser   = 0, # FIXME.
            i_s_axi_arvalid  = Cat(*[s_axi.ar.valid for s_axi in s_axis]),
            o_s_axi_arready  = Cat(*[s_axi.ar.ready for s_axi in s_axis]),

            # R.
            o_s_axi_rid      = Cat(*[s_axi.r.id     for s_axi in s_axis]),
            o_s_axi_rdata    = Cat(*[s_axi.r.data   for s_axi in s_axis]),
            o_s_axi_rresp    = Cat(*[s_axi.r.resp   for s_axi in s_axis]),
            o_s_axi_rlast    = Cat(*[s_axi.r.last   for s_axi in s_axis]),
            o_s_axi_ruser    = Open(), # FIXME.
            o_s_axi_rvalid   = Cat(*[s_axi.r.valid  for s_axi in s_axis]),
            i_s_axi_rready   = Cat(*[s_axi.r.ready  for s_axi in s_axis]),

            # AXI Master Interfaces.
            # ----------------------
            # AW.
            o_m_axi_awid     = Cat(*[m_axi.aw.id    for m_axi in m_axis]),
            o_m_axi_awaddr   = Cat(*[m_axi.aw.addr  for m_axi in m_axis]),
            o_m_axi_awlen    = Cat(*[m_axi.aw.len   for m_axi in m_axis]),
            o_m_axi_awsize   = Cat(*[m_axi.aw.size  for m_axi in m_axis]),
            o_m_axi_awburst  = Cat(*[m_axi.aw.burst for m_axi in m_axis]),
            o_m_axi_awlock   = Cat(*[m_axi.aw.lock  for m_axi in m_axis]),
            o_m_axi_awcache  = Cat(*[m_axi.aw.cache for m_axi in m_axis]),
            o_m_axi_awprot   = Cat(*[m_axi.aw.prot  for m_axi in m_axis]),
            o_m_axi_awqos    = Cat(*[m_axi.aw.qos   for m_axi in m_axis]),
            o_m_axi_awregion = Open(),
            o_m_axi_awuser   = Open(),
            o_m_axi_awvalid  = Cat(*[m_axi.aw.valid for m_axi in m_axis]),
            i_m_axi_awready  = Cat(*[m_axi.aw.ready for m_axi in m_axis]),

            # W.
            o_m_axi_wdata    = Cat(*[m_axi.w.data   for m_axi in m_axis]),
            o_m_axi_wstrb    = Cat(*[m_axi.w.strb   for m_axi in m_axis]),
            o_m_axi_wlast    = Cat(*[m_axi.w.last   for m_axi in m_axis]),
            o_m_axi_wuser    = Open(), # FIXME.
            o_m_axi_wvalid   = Cat(*[m_axi.w.valid  for m_axi in m_axis]),
            i_m_axi_wready   = Cat(*[m_axi.w.ready  for m_axi in m_axis]),

            # B.
            i_m_axi_bid      = Cat(*[m_axi.b.id     for m_axi in m_axis]),
            i_m_axi_bresp    = Cat(*[m_axi.b.resp   for m_axi in m_axis]),
            i_m_axi_buser    = 0, # FIXME.
            i_m_axi_bvalid   = Cat(*[m_axi.b.valid  for m_axi in m_axis]),
            o_m_axi_bready   = Cat(*[m_axi.b.ready  for m_axi in m_axis]),

            # AR.
            o_m_axi_arid     = Cat(*[m_axi.ar.id    for m_axi in m_axis]),
            o_m_axi_araddr   = Cat(*[m_axi.ar.addr  for m_axi in m_axis]),
            o_m_axi_arlen    = Cat(*[m_axi.ar.len   for m_axi in m_axis]),
            o_m_axi_arsize   = Cat(*[m_axi.ar.size  for m_axi in m_axis]),
            o_m_axi_arburst  = Cat(*[m_axi.ar.burst for m_axi in m_axis]),
            o_m_axi_arlock   = Cat(*[m_axi.ar.lock  for m_axi in m_axis]),
            o_m_axi_arcache  = Cat(*[m_axi.ar.cache for m_axi in m_axis]),
            o_m_axi_arprot   = Cat(*[m_axi.ar.prot  for m_axi in m_axis]),
            o_m_axi_arqos    = Cat(*[m_axi.ar.qos   for m_axi in m_axis]),
            o_m_axi_arregion = Open(),
            o_m_axi_aruser   = Open(),
            o_m_axi_arvalid  = Cat(*[m_axi.ar.valid for m_axi in m_axis]),
            i_m_axi_arready  = Cat(*[m_axi.ar.ready for m_axi in m_axis]),

            # R.
            i_m_axi_rid      = Cat(*[m_axi.r.id     for m_axi in m_axis]),
            i_m_axi_rdata    = Cat(*[m_axi.r.data   for m_axi in m_axis]),
            i_m_axi_rresp    = Cat(*[m_axi.r.resp   for m_axi in m_axis]),
            i_m_axi_rlast    = Cat(*[m_axi.r.last   for m_axi in m_axis]),
            i_m_axi_ruser    = 0, # FIXME.
            i_m_axi_rvalid   = Cat(*[m_axi.r.valid  for m_axi in m_axis]),
            o_m_axi_rready   = Cat(*[m_axi.r.ready  for m_axi in m_axis]),
        )

    @staticmethod
    def add_sources(platform):
        rtl_dir = os.path.join(os.path.dirname(__file__), "..", "verilog", "rtl")
        platform.add_source(os.path.join(rtl_dir, "arbiter.v"))
        platform.add_source(os.path.join(rtl_dir, "priority_encoder.v"))
        platform.add_source(os.path.join(rtl_dir, "axi_interconnect.v"))


class AXIInterconnectWrapper(Module):
    def __init__(self, masters, slaves, register=False, timeout_cycles=1e6, *args, **kwargs):
        ic = AXIInterconnect(kwargs['platform'])
        for m in masters:
            ic.add_slave(s_axi=m)
        for region, s in slaves:
            ic.add_master(m_axi=s, origin=region.origin, size=region.size)
        self.submodules += ic
